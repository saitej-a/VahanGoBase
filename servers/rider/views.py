import copy
import logging
from rest_framework import status
from base.utils import success_response, error_response
from rest_framework.decorators import api_view, permission_classes
from .serializers import FavoriteLocationSerializer
from rest_framework.permissions import IsAuthenticated
from .models import FavoriteLocation
from ..redis import nearby_drivers

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_favorite_locations(request):
    """
    Save a favorite location for the rider.
    
    Expected request data:
    {
        "name": str,
        "address": str,
        "lng": float,
        "lat": float
    }
    """
    try:
        data = copy.copy(request.data)
        data['rider_id'] = request.user.rider.id
        instance = FavoriteLocationSerializer(data=data)
        
        if instance.is_valid():
            instance.save()
            return success_response(
                {"location": instance.data},
                status.HTTP_201_CREATED
            )
        else:
            logger.warning(f"Validation errors: {instance.errors}")
            return error_response(
                code='VALIDATION_ERROR',
                message='Failed to save favorite location',
                field='location',
                issue=str(instance.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
    except AttributeError as e:
        logger.error(f"Rider profile error: {str(e)}")
        return error_response(
            code='PROFILE_ERROR',
            message='Rider profile not found',
            field='user',
            issue='User does not have a rider profile',
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error saving favorite location: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_favorite_locations(request):
    """
    Retrieve all favorite locations for the authenticated rider.
    """
    try:
        query_set = FavoriteLocation.objects.filter(rider_id=request.user.rider.id)
        data = FavoriteLocationSerializer(query_set, many=True)
        return success_response(data.data, status.HTTP_200_OK)
    except AttributeError as e:
        logger.error(f"Rider profile error: {str(e)}")
        return error_response(
            code='PROFILE_ERROR',
            message='Rider profile not found',
            field='user',
            issue='User does not have a rider profile',
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching favorite locations: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_drivers(request):
    """
    Get nearby drivers for the rider.
    
    Query parameters:
    - lng: Longitude (float)
    - lat: Latitude (float)
    - radius: Search radius in meters (int, optional, default: 1000)
    - count: Maximum number of results (int, optional, default: 10)
    """
    try:
        # Get parameters from query_params for GET request
        lng = request.query_params.get('lng')
        lat = request.query_params.get('lat')
        radius = request.query_params.get('radius', 1000)
        count = request.query_params.get('count', 10)
        
        # Validate required fields
        if lng is None or lat is None:
            logger.warning("Missing coordinates in nearby drivers request")
            return error_response(
                code='MISSING_FIELDS',
                message='Longitude and latitude are required',
                field='coordinates',
                issue='lng and lat query parameters must be provided',
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Try to convert to proper types
        try:
            lng = float(lng)
            lat = float(lat)
            radius = int(radius)
            count = int(count)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid parameter types: {str(e)}")
            return error_response(
                code='INVALID_TYPE',
                message='Invalid parameter types',
                field='coordinates',
                issue='lng and lat must be floats, radius and count must be integers',
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Call Redis function
        drivers = nearby_drivers(lng=lng, lat=lat, radius=radius, count=count)
        
        if drivers is None:
            logger.error("Redis operation failed for nearby drivers")
            return error_response(
                code='REDIS_ERROR',
                message='Failed to retrieve nearby drivers',
                field='general',
                issue='Database query failed',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return success_response(drivers, status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Unexpected error getting nearby drivers: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )