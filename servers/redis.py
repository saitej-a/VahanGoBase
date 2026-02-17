import redis
import logging
from django.conf import settings
from servers.driver.utils import update_driver_location
logger = logging.getLogger(__name__)

# Initialize Redis client with connection pool and error handling
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL + '/2',
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
        socket_keepalive_options={} if hasattr(redis, 'SOCKET_KEEPALIVE_OPTIONS') else None
    )
    # Test the connection
    redis_client.ping()
    logger.info("Geo connection established successfully")
except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
    redis_client = None

GEO_KEY = 'drivers:geo'


def _validate_coordinates(lng, lat):
    """
    Validate geographic coordinates.
    
    Args:
        lng: Longitude value (-180 to 180)
        lat: Latitude value (-90 to 90)
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        lng = float(lng)
        lat = float(lat)
    except (TypeError, ValueError):
        return False, "Longitude and latitude must be valid numbers"
    
    if not (-180 <= lng <= 180):
        return False, "Longitude must be between -180 and 180"
    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90"
    
    return True, None


def add_driver_location(driver_id, lng, lat):
    """
    Add or update driver location in Redis geospatial index.
    
    Args:
        driver_id: Unique driver identifier
        lng: Longitude coordinate
        lat: Latitude coordinate
    
    Returns:
        dict: Status and message
    
    Raises:
        ValueError: If coordinates are invalid
        redis.RedisError: If Redis operation fails
    """
    if redis_client is None:
        logger.error("Redis client not available")
        return {"success": False, "error": "Redis connection unavailable"}
    
    try:
        # Validate inputs
        if not driver_id:
            raise ValueError("driver_id cannot be empty")
        
        is_valid, error_msg = _validate_coordinates(lng, lat)
        if not is_valid:
            raise ValueError(error_msg)
        
        lng = float(lng)
        lat = float(lat)
        
        member = f'driver:{driver_id}'
        result = redis_client.geoadd(GEO_KEY, [lng, lat, member])
        
        
        res = update_driver_location(driver_id=driver_id, lat=lat, lng=lng)
        print(res)
        
        if result is not None:
            logger.info(f"Driver {driver_id} location updated: lng={lng}, lat={lat}")
            return {"success": True, "message": "Location added successfully"}
        else:
            logger.warning(f"Failed to add driver {driver_id} location")
            return {"success": False, "error": "Failed to add location"}
            
    except ValueError as e:
        logger.warning(f"Validation error for driver {driver_id}: {str(e)}")
        return {"success": False, "error": str(e)}
    except redis.RedisError as e:
        logger.error(f"Redis error while adding driver {driver_id} location: {str(e)}")
        return {"success": False, "error": "Database operation failed"}
    except Exception as e:
        logger.error(f"Unexpected error adding driver {driver_id} location: {str(e)}")
        return {"success": False, "error": "An unexpected error occurred"}


def nearby_drivers(lng, lat, radius=1000, count=10):
    """
    Search for nearby drivers within a specified radius.
    
    Args:
        lng: Longitude coordinate
        lat: Latitude coordinate
        radius: Search radius in meters (default: 1000)
        count: Maximum number of results (default: 10)
    
    Returns:
        list: List of nearby drivers with distance and coordinates
        None: If operation fails
    """
    if redis_client is None:
        logger.error("Redis client not available for nearby_drivers query")
        return None
    
    try:
        # Validate inputs
        is_valid, error_msg = _validate_coordinates(lng, lat)
        if not is_valid:
            raise ValueError(error_msg)
        
        if radius <= 0:
            raise ValueError("Radius must be greater than 0")
        
        if count <= 0:
            raise ValueError("Count must be greater than 0")
        
        drivers = redis_client.geosearch(
            GEO_KEY,
            longitude=lng,
            latitude=lat,
            radius=radius,
            count=count,
            unit='m',
            sort='ASC',
            withdist=True,
            withcoord=True
        )
        
        logger.info(f"Found {len(drivers) if drivers else 0} nearby drivers at lng={lng}, lat={lat}")
        return drivers if drivers else []
        
    except ValueError as e:
        logger.warning(f"Validation error in nearby_drivers: {str(e)}")
        return None
    except redis.RedisError as e:
        logger.error(f"Redis error during nearby drivers search: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during nearby drivers search: {str(e)}")
        return None


def remove_driver(driver_id):
    """
    Remove driver from geospatial index.
    
    Args:
        driver_id: Unique driver identifier
    
    Returns:
        dict: Status and message
    """
    if redis_client is None:
        logger.error("Redis client not available")
        return {"success": False, "error": "Redis connection unavailable"}
    
    try:
        if not driver_id:
            raise ValueError("driver_id cannot be empty")
        
        member = f'driver:{driver_id}'
        result = redis_client.zrem(GEO_KEY, member)
        
        if result > 0:
            logger.info(f"Driver {driver_id} removed from geo index")
            return {"success": True, "message": "Driver removed successfully"}
        else:
            logger.warning(f"Driver {driver_id} not found in geo index")
            return {"success": False, "error": "Driver not found"}
            
    except ValueError as e:
        logger.warning(f"Validation error for driver {driver_id}: {str(e)}")
        return {"success": False, "error": str(e)}
    except redis.RedisError as e:
        logger.error(f"Redis error while removing driver {driver_id}: {str(e)}")
        return {"success": False, "error": "Database operation failed"}
    except Exception as e:
        logger.error(f"Unexpected error removing driver {driver_id}: {str(e)}")
        return {"success": False, "error": "An unexpected error occurred"}


def publish_ride_request(ride_id, rider_id, pickup_lng, pickup_lat, destination_lng, destination_lat):
    """
    Publish a ride request to Redis Stream for future analytics.
    
    NOTE: This stream is NOT used for driver notification — drivers are
    notified in real-time via WebSockets (channel_layer.group_send).
    This serves as a write-only log for future use cases such as:
      - Ride request history & audit trail
      - Demand heatmaps & surge pricing analytics
      - Request pattern analysis
    
    Args:
        ride_id: Trip/ride ID
        rider_id: Rider's user ID
        pickup_lng: Pickup longitude
        pickup_lat: Pickup latitude
        destination_lng: Destination longitude
        destination_lat: Destination latitude
    
    Returns:
        dict: Status and message
    """
    if redis_client is None:
        logger.error("Redis client not available for publishing ride request")
        return {"success": False, "error": "Redis connection unavailable"}

    try:
        message_id = redis_client.xadd('ride_requests', {
            'ride_id': str(ride_id),
            'rider_id': str(rider_id),
            'pickup_lng': str(pickup_lng),
            'pickup_lat': str(pickup_lat),
            'destination_lng': str(destination_lng),
            'destination_lat': str(destination_lat),
            'status': 'pending',
        }, maxlen=50000)

        logger.info(f"Ride request {ride_id} published to stream: {message_id}")
        return {"success": True, "message_id": message_id}

    except redis.RedisError as e:
        logger.error(f"Redis error publishing ride request {ride_id}: {str(e)}")
        return {"success": False, "error": "Failed to publish ride request"}
    except Exception as e:
        logger.error(f"Unexpected error publishing ride request {ride_id}: {str(e)}")
        return {"success": False, "error": "An unexpected error occurred"}
