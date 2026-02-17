import logging
from rest_framework import status
from base.utils import success_response, error_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from servers.ride.models import Trip
from servers.ride.utils import estimate_amount
from servers.redis import nearby_drivers, publish_ride_request
from django.db import transaction

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ride_request(request):
    """
    Create a new ride request.
    
    Expected request data:
    {
        "pickup_lat": float,
        "pickup_long": float,
        "destination_lat": float,
        "destination_long": float,
        "pickup_address": str (optional),
        "destination_address": str (optional)
    }
    """
    pickup_lat = request.data.get('pickup_lat')
    pickup_long = request.data.get('pickup_long')
    destination_lat = request.data.get('destination_lat')
    destination_long = request.data.get('destination_long')
    pickup_address = request.data.get('pickup_address', '')
    destination_address = request.data.get('destination_address', '')

    # Validate pickup coordinates
    if not pickup_lat or not pickup_long:
        return error_response(
            code='MISSING_FIELDS',
            message='Pickup latitude and longitude are required',
            field='pickup_coordinates',
            issue='pickup_lat and pickup_long must be provided',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate destination coordinates
    if not destination_lat or not destination_long:
        return error_response(
            code='MISSING_FIELDS',
            message='Destination latitude and longitude are required',
            field='destination_coordinates',
            issue='destination_lat and destination_long must be provided',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate coordinate types
    try:
        pickup_lat = float(pickup_lat)
        pickup_long = float(pickup_long)
        destination_lat = float(destination_lat)
        destination_long = float(destination_long)
    except (ValueError, TypeError):
        return error_response(
            code='INVALID_TYPE',
            message='Coordinates must be valid numbers',
            field='coordinates',
            issue='All coordinate fields must be floats',
            status=status.HTTP_400_BAD_REQUEST
        )

    estimated_fare = estimate_amount(0, 0)

    try:
        with transaction.atomic():
            trip_obj = Trip.objects.create(
                user_id=request.user,
                pickup_lat=pickup_lat,
                pickup_long=pickup_long,
                destination_lat=destination_lat,
                destination_long=destination_long,
                pickup_address=pickup_address,
                destination_address=destination_address,
                estimated_fare=estimated_fare
            )

            # Publish ride request to Redis Stream
            publish_ride_request(
                ride_id=trip_obj.id,
                rider_id=request.user.id,
                pickup_lng=pickup_long,
                pickup_lat=pickup_lat,
                destination_lng=destination_long,
                destination_lat=destination_lat,
            )

        # Find nearby drivers (informational for REST response)
        drivers = nearby_drivers(lng=pickup_long, lat=pickup_lat, radius=5000, count=10)

        return success_response(
            {
                'trip_id': trip_obj.id,
                'estimated_fare': str(trip_obj.estimated_fare),
                'nearby_drivers_count': len(drivers) if drivers else 0,
                'message': 'Ride request created successfully',
            },
            status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Error creating ride request: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='Failed to create ride request',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )