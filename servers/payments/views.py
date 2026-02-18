import json
import logging
from decimal import Decimal
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction
from base.utils import success_response, error_response
from servers.payments.models import Payment, TransactionHistory
from servers.payments.razorpay_utils import (
    create_razorpay_order, verify_payment_signature, verify_webhook_signature
)
from servers.ride.models import Trip

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Create a Razorpay order for a completed trip.
    
    Expected: { "trip_id": int }
    Returns: Razorpay order details to be used by frontend checkout.
    """
    trip_id = request.data.get('trip_id')

    if not trip_id:
        return error_response(
            code='MISSING_FIELDS',
            message='trip_id is required',
            field='trip_id',
            issue='Provide the trip ID to create a payment order',
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        trip = Trip.objects.select_related('status_id', 'driver_id').get(id=trip_id)
    except Trip.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Trip not found',
            field='trip_id',
            issue=f'No trip with id {trip_id}',
            status=status.HTTP_404_NOT_FOUND
        )

    # Verify trip belongs to this user
    if trip.user_id_id != request.user.id:
        return error_response(
            code='FORBIDDEN',
            message='You can only pay for your own trips',
            field='trip_id',
            issue='Trip does not belong to this user',
            status=status.HTTP_403_FORBIDDEN
        )

    # Verify trip is completed
    if not trip.status_id or trip.status_id.status_code != 'completed':
        return error_response(
            code='INVALID_STATE',
            message='Payment can only be made for completed trips',
            field='trip_id',
            issue=f'Trip status: {trip.status_id.status_code if trip.status_id else "pending"}',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if payment already exists
    existing = Payment.objects.filter(trip_id=trip, status='completed').first()
    if existing:
        return error_response(
            code='ALREADY_PAID',
            message='Payment already completed for this trip',
            field='trip_id',
            issue=f'Payment {existing.id} already completed',
            status=status.HTTP_409_CONFLICT
        )

    # Use final_fare if available, otherwise estimated_fare
    amount = trip.final_fare or trip.estimated_fare
    if not amount or amount <= 0:
        return error_response(
            code='INVALID_AMOUNT',
            message='No valid fare amount for this trip',
            field='amount',
            issue='Trip has no estimated or final fare',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create Razorpay order
    order = create_razorpay_order(amount=amount, trip_id=trip.id)
    if not order:
        return error_response(
            code='PAYMENT_GATEWAY_ERROR',
            message='Failed to create payment order. Please try again.',
            field='razorpay',
            issue='Razorpay order creation failed',
            status=status.HTTP_502_BAD_GATEWAY
        )

    # Create or update Payment record
    payment, _ = Payment.objects.update_or_create(
        trip_id=trip,
        user_id=request.user,
        defaults={
            'amount': amount,
            'method': 'online',
            'status': 'processing',
            'razorpay_order_id': order['id'],
        }
    )

    return success_response({
        'payment_id': payment.id,
        'razorpay_order_id': order['id'],
        'razorpay_key_id': order.get('key_id', ''),
        'amount': str(amount),
        'amount_paise': order['amount'],
        'currency': order['currency'],
        'trip_id': trip.id,
        'description': f'Payment for Trip #{trip.id}',
        'prefill': {
            'name': request.user.full_name or '',
            'contact': request.user.phone_number or '',
            'email': request.user.email or '',
        }
    }, status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """
    Client-side payment verification after Razorpay checkout completes.
    
    Expected: {
        "razorpay_order_id": str,
        "razorpay_payment_id": str,
        "razorpay_signature": str
    }
    """
    order_id = request.data.get('razorpay_order_id')
    payment_id = request.data.get('razorpay_payment_id')
    signature = request.data.get('razorpay_signature')

    if not all([order_id, payment_id, signature]):
        return error_response(
            code='MISSING_FIELDS',
            message='razorpay_order_id, razorpay_payment_id, and razorpay_signature are required',
            field='request_body',
            issue='All Razorpay payment fields must be provided',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find the payment
    try:
        payment = Payment.objects.select_related('trip_id', 'trip_id__driver_id').get(
            razorpay_order_id=order_id,
            user_id=request.user
        )
    except Payment.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Payment not found for this order',
            field='razorpay_order_id',
            issue=f'No payment found for order {order_id}',
            status=status.HTTP_404_NOT_FOUND
        )

    if payment.status == 'completed':
        return success_response({
            'message': 'Payment already verified',
            'payment_id': payment.id,
            'status': 'completed',
        }, status.HTTP_200_OK)

    # Verify signature
    is_valid = verify_payment_signature(order_id, payment_id, signature)
    if not is_valid:
        payment.status = 'failed'
        payment.razorpay_payment_id = payment_id
        payment.save()
        return error_response(
            code='SIGNATURE_INVALID',
            message='Payment verification failed',
            field='razorpay_signature',
            issue='Razorpay signature verification failed',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Mark payment as completed
    with transaction.atomic():
        payment.status = 'completed'
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.save()

        # Update trip payment status
        trip = payment.trip_id
        trip.payment_status = 'completed'
        trip.payment_method = 'online'
        trip.save(update_fields=['payment_status', 'payment_method'])

        # Create transaction history
        if trip.driver_id:
            TransactionHistory.objects.create(
                trip_id=trip,
                user_id=request.user,
                driver_id=trip.driver_id,
                amount=payment.amount,
                method='online',
                razorpay_payment_id=payment_id,
                user_name=request.user.full_name or request.user.phone_number,
                status='completed',
            )

    return success_response({
        'message': 'Payment verified successfully',
        'payment_id': payment.id,
        'status': 'completed',
        'amount': str(payment.amount),
    }, status.HTTP_200_OK)


@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay webhook endpoint.
    Handles payment.captured event to auto-confirm payments.
    No JWT auth — verified via Razorpay signature header.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    signature = request.headers.get('X-Razorpay-Signature', '')
    body = request.body

    # Verify webhook signature (skipped in dev if no secret configured)
    if not verify_webhook_signature(body, signature):
        logger.warning("Webhook signature verification failed")
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    try:
        payload = json.loads(body)
        event = payload.get('event', '')

        if event == 'payment.captured':
            payment_entity = payload['payload']['payment']['entity']
            rzp_order_id = payment_entity.get('order_id')
            rzp_payment_id = payment_entity.get('id')

            if not rzp_order_id:
                return JsonResponse({'status': 'skipped', 'reason': 'no order_id'}, status=200)

            try:
                payment = Payment.objects.select_related('trip_id', 'trip_id__driver_id').get(
                    razorpay_order_id=rzp_order_id
                )
            except Payment.DoesNotExist:
                logger.warning(f"Webhook: No payment found for order {rzp_order_id}")
                return JsonResponse({'status': 'skipped', 'reason': 'payment not found'}, status=200)

            if payment.status == 'completed':
                return JsonResponse({'status': 'already_completed'}, status=200)

            with transaction.atomic():
                payment.status = 'completed'
                payment.razorpay_payment_id = rzp_payment_id
                payment.save()

                trip = payment.trip_id
                trip.payment_status = 'completed'
                trip.payment_method = 'online'
                trip.save(update_fields=['payment_status', 'payment_method'])

                if trip.driver_id:
                    TransactionHistory.objects.get_or_create(
                        trip_id=trip,
                        razorpay_payment_id=rzp_payment_id,
                        defaults={
                            'user_id': payment.user_id,
                            'driver_id': trip.driver_id,
                            'amount': payment.amount,
                            'method': 'online',
                            'user_name': payment.user_id.full_name or payment.user_id.phone_number,
                            'status': 'completed',
                        }
                    )

            logger.info(f"Webhook: Payment {payment.id} completed for trip {trip.id}")
            return JsonResponse({'status': 'ok'}, status=200)

        # Log other events but don't process
        logger.info(f"Webhook: Received event {event}, ignoring")
        return JsonResponse({'status': 'ok'}, status=200)

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Webhook: Invalid payload: {e}")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except Exception as e:
        logger.error(f"Webhook: Error processing: {e}")
        return JsonResponse({'error': 'Internal error'}, status=500)


class PaymentPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_history(request):
    """
    Get payment history for the authenticated user.
    
    Query params:
        ?page=1         - Page number
        ?page_size=10   - Items per page (max 50)
        ?status=completed - Filter by status (optional)
    """
    payments = Payment.objects.filter(
        user_id=request.user
    ).select_related('trip_id').order_by('-created_at')

    status_filter = request.query_params.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)

    paginator = PaymentPagination()
    page = paginator.paginate_queryset(payments, request)

    data = [{
        'id': p.id,
        'trip_id': p.trip_id_id,
        'amount': str(p.amount),
        'method': p.method,
        'status': p.status,
        'razorpay_order_id': p.razorpay_order_id,
        'razorpay_payment_id': p.razorpay_payment_id,
        'created_at': p.created_at.isoformat(),
    } for p in page]

    return paginator.get_paginated_response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refund_payment(request):
    """
    Initiate refund for a cancelled trip.

    Expected: { "trip_id": int }
    Only works if the trip is cancelled and payment was completed online.
    """
    from servers.payments.razorpay_utils import create_refund
    from servers.rider.models import Notification

    trip_id = request.data.get('trip_id')
    if not trip_id:
        return error_response(
            code='MISSING_FIELDS',
            message='trip_id is required',
            field='trip_id',
            issue='Provide the trip ID to refund',
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        trip = Trip.objects.select_related('status_id').get(id=trip_id)
    except Trip.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Trip not found',
            field='trip_id',
            issue=f'Trip {trip_id} does not exist',
            status=status.HTTP_404_NOT_FOUND
        )

    # Only the rider can request a refund
    if trip.user_id_id != request.user.id:
        return error_response(
            code='FORBIDDEN',
            message='Only the rider can request a refund',
            field='trip_id',
            issue='Trip does not belong to this user',
            status=status.HTTP_403_FORBIDDEN
        )

    # Trip must be cancelled
    if not trip.status_id or trip.status_id.status_code != 'cancelled':
        return error_response(
            code='INVALID_STATE',
            message='Refund only available for cancelled trips',
            field='trip_id',
            issue=f'Trip status: {trip.status_id.status_code if trip.status_id else "unknown"}',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find the completed online payment
    payment = Payment.objects.filter(
        trip_id=trip,
        method='online',
        status='completed',
    ).first()

    if not payment:
        return error_response(
            code='NO_PAYMENT',
            message='No completed online payment found for this trip',
            field='trip_id',
            issue='No refundable payment exists',
            status=status.HTTP_400_BAD_REQUEST
        )

    if payment.status == 'refunded':
        return error_response(
            code='ALREADY_REFUNDED',
            message='Payment has already been refunded',
            field='trip_id',
            issue='Duplicate refund not allowed',
            status=status.HTTP_409_CONFLICT
        )

    if not payment.razorpay_payment_id:
        return error_response(
            code='NO_RAZORPAY_ID',
            message='No Razorpay payment ID found',
            field='razorpay_payment_id',
            issue='Cannot process refund without Razorpay payment ID',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create refund via Razorpay
    refund = create_refund(payment.razorpay_payment_id)
    if not refund:
        return error_response(
            code='REFUND_FAILED',
            message='Failed to process refund. Please try again.',
            field='razorpay',
            issue='Razorpay refund creation failed',
            status=status.HTTP_502_BAD_GATEWAY
        )

    with transaction.atomic():
        payment.status = 'refunded'
        payment.save(update_fields=['status', 'updated_at'])

        trip.payment_status = 'refunded'
        trip.save(update_fields=['payment_status'])

        Notification.objects.create(
            user_id=request.user,
            title='Refund Processed',
            message=f'Your refund of ₹{payment.amount} for Trip #{trip.id} has been initiated. It may take 5-7 business days to reflect in your account.',
        )

    return success_response({
        'message': 'Refund initiated successfully',
        'refund_id': refund.get('id'),
        'amount': str(payment.amount),
        'trip_id': trip.id,
    }, status.HTTP_200_OK)
