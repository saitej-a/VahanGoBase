import redis
import logging
from django.conf import settings
from base.utils import success_response, error_response
from rest_framework import status

logger = logging.getLogger(__name__)

# Initialize Redis client with connection pool and error handling
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL + '/3',
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        socket_keepalive_options={} if hasattr(redis, 'SOCKET_KEEPALIVE_OPTIONS') else None
    )
    # Test the connection
    redis_client.ping()
    logger.info("Stream connection established successfully")
except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
    redis_client = None

def update_driver_location(driver_id, lng, lat):
    if redis_client is None:
        return error_response(
            code="REDIS_CONNECTION_ERROR",
            message="Failed to connect to Redis",
            field="redis",
            issue="Redis connection error",
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    redis_client.xadd('driver_location_stream', {'driver_id': driver_id, 'lng': lng, 'lat': lat}, maxlen=100000)

    return success_response(
        data={
            'message': "Driver location updated successfully",
            'driver_id': driver_id,
            'lng': lng,
            'lat': lat
        },
        status_code=status.HTTP_200_OK
    )