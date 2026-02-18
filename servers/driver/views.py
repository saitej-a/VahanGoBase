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


# ── Driver Earnings ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsDriver])
def driver_earnings(request):
    """
    Paginated list of driver earnings.

    Query params:
        ?page=1         - Page number
        ?page_size=10   - Items per page (max 50)
    """
    from .models import DriverEarning
    from .serializers import DriverEarningSerializer
    from rest_framework.pagination import PageNumberPagination

    driver = request.user.driver
    earnings = DriverEarning.objects.filter(driver_id=driver).order_by('-id')

    paginator = PageNumberPagination()
    paginator.page_size = 10
    paginator.page_size_query_param = 'page_size'
    paginator.max_page_size = 50
    page = paginator.paginate_queryset(earnings, request)
    serializer = DriverEarningSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsDriver])
def driver_earnings_summary(request):
    """
    Aggregate earnings for the driver.

    Returns: total_earned, total_commission, total_trips, today_earned, today_trips
    """
    from .models import DriverEarning
    from django.db.models import Sum, Count
    from django.utils import timezone

    driver = request.user.driver
    today = timezone.now().date()

    total = DriverEarning.objects.filter(driver_id=driver).aggregate(
        total_earned=Sum('net_amount'),
        total_commission=Sum('commission'),
        total_trips=Count('id'),
    )

    today_qs = DriverEarning.objects.filter(
        driver_id=driver,
        trip_id__completed_at__date=today,
    ).aggregate(
        today_earned=Sum('net_amount'),
        today_trips=Count('id'),
    )

    from django.conf import settings

    return success_response({
        'total_earned': str(total['total_earned'] or 0),
        'total_commission': str(total['total_commission'] or 0),
        'total_trips': total['total_trips'] or 0,
        'today_earned': str(today_qs['today_earned'] or 0),
        'today_trips': today_qs['today_trips'] or 0,
        'commission_percent': settings.PLATFORM_COMMISSION_PERCENT,
    }, status.HTTP_200_OK)


# ── Vehicle CRUD ────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsDriver])
def list_vehicles(request):
    """List all vehicles belonging to the authenticated driver."""
    from .models import Vehicle
    from .serializers import VehicleSerializer

    driver = request.user.driver
    vehicles = Vehicle.objects.filter(driver_id=driver).select_related('vehicle_type_id')
    serializer = VehicleSerializer(vehicles, many=True)
    return success_response(serializer.data, status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsDriver])
def create_vehicle(request):
    """
    Add a new vehicle for the driver.

    Expected: {
        "vehicle_number": str,
        "vehicle_type": str (e.g. "sedan"),
        "brand": str (optional),
        "model": str (optional),
        "color": str (optional),
        "year": int (optional),
        "capacity": int (optional, default 1)
    }
    """
    from .models import Vehicle, VehicleType
    from .serializers import VehicleCreateSerializer, VehicleSerializer

    serializer = VehicleCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            code='VALIDATION_ERROR',
            message='Invalid vehicle data',
            field=list(serializer.errors.keys())[0],
            issue=str(serializer.errors),
            status=status.HTTP_400_BAD_REQUEST
        )

    data = serializer.validated_data
    driver = request.user.driver
    vt = VehicleType.objects.get(type=data['vehicle_type'])

    vehicle = Vehicle.objects.create(
        driver_id=driver,
        vehicle_type_id=vt,
        vehicle_number=data['vehicle_number'],
        brand=data.get('brand', ''),
        model=data.get('model', ''),
        color=data.get('color', ''),
        year=data.get('year'),
        capacity=data.get('capacity', 1),
    )

    return success_response(
        VehicleSerializer(vehicle).data,
        status.HTTP_201_CREATED
    )


@api_view(['PATCH'])
@permission_classes([IsDriver])
def update_vehicle(request, vehicle_id):
    """Update a vehicle belonging to the driver."""
    from .models import Vehicle
    from .serializers import VehicleSerializer

    driver = request.user.driver
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id, driver_id=driver)
    except Vehicle.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Vehicle not found',
            field='vehicle_id',
            issue=f'Vehicle {vehicle_id} not found or does not belong to you',
            status=status.HTTP_404_NOT_FOUND
        )

    allowed_fields = ['brand', 'model', 'color', 'year', 'capacity', 'vehicle_pic', 'vehicle_number']
    for field in allowed_fields:
        if field in request.data:
            setattr(vehicle, field, request.data[field])
    vehicle.save()

    return success_response(VehicleSerializer(vehicle).data, status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsDriver])
def delete_vehicle(request, vehicle_id):
    """Delete a vehicle belonging to the driver."""
    from .models import Vehicle

    driver = request.user.driver
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id, driver_id=driver)
    except Vehicle.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Vehicle not found',
            field='vehicle_id',
            issue=f'Vehicle {vehicle_id} not found or does not belong to you',
            status=status.HTTP_404_NOT_FOUND
        )

    vehicle.delete()
    return success_response({'message': 'Vehicle deleted successfully'}, status.HTTP_200_OK)