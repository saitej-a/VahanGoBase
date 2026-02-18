import logging
import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def get_razorpay_client():
    """Get or create singleton Razorpay client."""
    global _client
    if _client is None:
        key_id = settings.RAZORPAY_KEY_ID
        key_secret = settings.RAZORPAY_KEY_SECRET
        if not key_id or not key_secret:
            logger.error("Razorpay credentials not configured in settings")
            return None
        _client = razorpay.Client(auth=(key_id, key_secret))
    return _client


def create_razorpay_order(amount, trip_id, currency='INR'):
    """
    Create a Razorpay order.
    
    Args:
        amount: Amount in rupees (will be converted to paise)
        trip_id: Trip ID for the receipt
        currency: Currency code (default: INR)
    
    Returns:
        dict: Razorpay order object or None on failure
    """
    client = get_razorpay_client()
    if not client:
        return None

    try:
        # Razorpay expects amount in paise (smallest currency unit)
        amount_paise = int(float(amount) * 100)

        order_data = {
            'amount': amount_paise,
            'currency': currency,
            'receipt': f'trip_{trip_id}',
            'payment_capture': 1,  # Auto-capture payment
        }

        order = client.order.create(data=order_data)
        logger.info(f"Razorpay order created: {order['id']} for trip {trip_id}")
        return order

    except Exception as e:
        logger.error(f"Failed to create Razorpay order for trip {trip_id}: {e}")
        return None


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify Razorpay payment signature.
    
    Returns:
        bool: True if signature is valid
    """
    client = get_razorpay_client()
    if not client:
        return False

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.warning(f"Signature verification failed for order {razorpay_order_id}")
        return False
    except Exception as e:
        logger.error(f"Error verifying payment signature: {e}")
        return False


def verify_webhook_signature(body, signature):
    """
    Verify Razorpay webhook signature.
    
    Args:
        body: Raw request body (bytes)
        signature: X-Razorpay-Signature header value
    
    Returns:
        bool: True if webhook signature is valid
    """
    client = get_razorpay_client()
    if not client:
        return False

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        logger.warning("Razorpay webhook secret not configured, skipping verification")
        return True  # Allow in dev if no secret configured

    try:
        client.utility.verify_webhook_signature(
            body.decode('utf-8') if isinstance(body, bytes) else body,
            signature,
            webhook_secret
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.warning("Webhook signature verification failed")
        return False
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


def create_refund(payment_id, amount=None):
    """
    Create a refund for a Razorpay payment.

    Args:
        payment_id: Razorpay payment ID (pay_xxx)
        amount: Amount in rupees to refund (None = full refund)

    Returns:
        dict: Razorpay refund object or None on failure
    """
    client = get_razorpay_client()
    if not client:
        return None

    try:
        refund_data = {}
        if amount is not None:
            refund_data['amount'] = int(float(amount) * 100)  # Convert to paise

        refund = client.payment.refund(payment_id, refund_data)
        logger.info(f"Razorpay refund created: {refund['id']} for payment {payment_id}")
        return refund

    except Exception as e:
        logger.error(f"Failed to create refund for payment {payment_id}: {e}")
        return None
