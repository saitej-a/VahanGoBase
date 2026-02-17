import logging
from base.utils import success_response, error_response
from servers.redis import add_driver_location,remove_driver
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .utils import update_driver_location
from .permissions import IsDriver
logger = logging.getLogger(__name__)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_driver(request):
    """
    Add or update driver location.
    
    Expected request data:
    {
        "lng": float,
        "lat": float
    }
    """
    try:
        driver_id = request.user.driver.id
        lng = request.data.get('lng')
        lat = request.data.get('lat')
        
        # Validate required fields
        if lng is None or lat is None:
            logger.warning(f"Missing coordinates for driver {driver_id}")
            return error_response(
                code='MISSING_FIELDS',
                message='Longitude and latitude are required',
                field='coordinates',
                issue='lng and lat must be provided',
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Dual-write: geo (spatial index) + stream (event log)
        result = add_driver_location(driver_id,lat=lat,lng=lng)
        if result.get('success'):
            return success_response(
                {'message': result.get('message')},
                status.HTTP_200_OK
            )
        else:
            logger.error(f"Failed to add driver location: {result.get('error')}")
            return error_response(
                code='LOCATION_ERROR',
                message=result.get('error', 'Failed to add location'),
                field='coordinates',
                issue='Could not save driver location to cache',
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except AttributeError as e:
        logger.error(f"Driver profile error: {str(e)}")
        return error_response(
            code='PROFILE_ERROR',
            message='Driver profile not found',
            field='user',
            issue='User does not have a driver profile',
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error adding driver location: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsDriver])
def update_location(request):
    """
    Update driver location.
    
    Expected request data:
    {
        "lng": float,
        "lat": float
    }
    """
    try:
        driver_id = request.user.driver.id
        lng = request.data.get('lng')
        lat = request.data.get('lat')
        
        # Validate required fields
        if lng is None or lat is None:
            logger.warning(f"Missing coordinates for driver {driver_id}")
            return error_response(
                code='MISSING_FIELDS',
                message='Longitude and latitude are required',
                field='coordinates',
                issue='lng and lat must be provided',
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Call Redis function
        result = update_driver_location(driver_id, lng=lng, lat=lat)
        return success_response(
            {'message': 'Driver location updated successfully'},
            status.HTTP_200_OK
        )
        
    
    except AttributeError as e:
        logger.error(f"Driver profile error: {str(e)}")
        return error_response(
            code='PROFILE_ERROR',
            message='Driver profile not found',
            field='user',
            issue='User does not have a driver profile',
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error adding driver location: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@api_view(['DELETE'])
@permission_classes([IsDriver])
def remove_driver_view(request):
    try:
        driver_id = request.user.driver.id
        result = remove_driver(driver_id)
        return success_response(
            {'message': 'Driver location removed successfully'},
            status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Unexpected error removing driver location: {str(e)}")
        return error_response(
            code='INTERNAL_ERROR',
            message='An unexpected error occurred',
            field='general',
            issue=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )