import logging
from decimal import Decimal
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from base.utils import success_response, error_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from servers.ride.models import Trip, FarePricing
from servers.ride.serializers import TripListSerializer, TripDetailSerializer
from servers.ride.utils import estimate_amount, validate_distance
from servers.driver.permissions import IsDriver
from servers.redis import nearby_drivers, publish_ride_request
from django.db import transaction

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def estimate_fare(request):
    """
    Estimate fare for a trip before rider confirms.
    
    Expected request data:
    {
        "pickup_lat": float,
        "pickup_long": float,
        "destination_lat": float,
        "destination_long": float,
        "distance_km": float,
        "duration_min": float,
        "vehicle_type": str (e.g. "sedan", "suv")
    }
    """
    pickup_lat = request.data.get('pickup_lat')
    pickup_long = request.data.get('pickup_long')
    destination_lat = request.data.get('destination_lat')
    destination_long = request.data.get('destination_long')
    distance_km = request.data.get('distance_km')
    duration_min = request.data.get('duration_min')
    vehicle_type = request.data.get('vehicle_type')

    # Validate required fields
    required = {
        'pickup_lat': pickup_lat, 'pickup_long': pickup_long,
        'destination_lat': destination_lat, 'destination_long': destination_long,
        'distance_km': distance_km, 'duration_min': duration_min,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        return error_response(
            code='MISSING_FIELDS',
            message=f'Missing required fields: {", ".join(missing)}',
            field='request_body',
            issue='All coordinate, distance, and duration fields are required',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate numeric types
    try:
        pickup_lat = float(pickup_lat)
        pickup_long = float(pickup_long)
        destination_lat = float(destination_lat)
        destination_long = float(destination_long)
        distance_km = float(distance_km)
        duration_min = float(duration_min)
    except (ValueError, TypeError):
        return error_response(
            code='INVALID_TYPE',
            message='All numeric fields must be valid numbers',
            field='coordinates',
            issue='pickup_lat, pickup_long, destination_lat, destination_long, distance_km, duration_min must be floats',
            status=status.HTTP_400_BAD_REQUEST
        )

    if distance_km <= 0 or duration_min <= 0:
        return error_response(
            code='INVALID_VALUE',
            message='Distance and duration must be positive values',
            field='distance_km / duration_min',
            issue='Values must be greater than 0',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Distance sanity check
    is_valid, straight_line_km, msg = validate_distance(
        distance_km, pickup_lat, pickup_long, destination_lat, destination_long
    )
    if not is_valid:
        return error_response(
            code='DISTANCE_MISMATCH',
            message=msg,
            field='distance_km',
            issue=f'Straight-line distance: {straight_line_km} km',
            status=status.HTTP_400_BAD_REQUEST
        )

    # Estimate fare
    fare = estimate_amount(distance_km, duration_min, vehicle_type=vehicle_type)

    return success_response({
        'estimated_fare': str(fare['total_fare']),
        'fare_breakdown': {
            'base_fare': str(fare['base_fare']),
            'distance_fare': str(fare['distance_fare']),
            'time_fare': str(fare['time_fare']),
            'surge_multiplier': str(fare['surge_multiplier']),
            'min_fare_applied': fare['min_fare_applied'],
        },
        'vehicle_type': fare['vehicle_type'],
        'pricing_source': fare['source'],
        'distance_km': distance_km,
        'duration_min': duration_min,
        'straight_line_km': straight_line_km,
    }, status.HTTP_200_OK)


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
        "destination_address": str (optional),
        "distance_km": float,
        "duration_min": float,
        "vehicle_type": str (optional, e.g. "sedan")
    }
    """
    pickup_lat = request.data.get('pickup_lat')
    pickup_long = request.data.get('pickup_long')
    destination_lat = request.data.get('destination_lat')
    destination_long = request.data.get('destination_long')
    pickup_address = request.data.get('pickup_address', '')
    destination_address = request.data.get('destination_address', '')
    distance_km = request.data.get('distance_km')
    duration_min = request.data.get('duration_min')
    vehicle_type = request.data.get('vehicle_type')

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

    # Parse distance and duration (optional but recommended)
    try:
        distance_km = float(distance_km) if distance_km is not None else None
        duration_min = float(duration_min) if duration_min is not None else None
    except (ValueError, TypeError):
        distance_km = None
        duration_min = None

    # Estimate fare
    fare = estimate_amount(
        distance_km=distance_km or 0,
        duration_min=duration_min or 0,
        vehicle_type=vehicle_type
    )
    estimated_fare = fare['total_fare']

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
                estimated_fare=estimated_fare,
                estimated_distance_km=Decimal(str(distance_km)) if distance_km else None,
                surge_multiplier=fare['surge_multiplier'],
            )

            # Create FarePricing breakdown record
            FarePricing.objects.create(
                trip_id=trip_obj,
                base_fare=fare['base_fare'],
                distance_fare=fare['distance_fare'],
                time_fare=fare['time_fare'],
                surge_multiplier=fare['surge_multiplier'],
                total_fare=fare['total_fare'],
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
                'fare_breakdown': {
                    'base_fare': str(fare['base_fare']),
                    'distance_fare': str(fare['distance_fare']),
                    'time_fare': str(fare['time_fare']),
                    'surge_multiplier': str(fare['surge_multiplier']),
                },
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


class TripPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ride_history(request):
    """
    Get ride history for the authenticated rider.
    Returns paginated list of past trips, newest first.
    
    Query params:
        ?page=1         - Page number
        ?page_size=10   - Items per page (max 50)
        ?status=completed - Filter by status (optional)
    """
    trips = Trip.objects.filter(
        user_id=request.user
    ).select_related(
        'status_id', 'driver_id', 'driver_id__user_id', 'vehicle_id', 'vehicle_id__vehicle_type_id'
    ).order_by('-requested_at')

    # Optional status filter
    status_filter = request.query_params.get('status')
    if status_filter:
        trips = trips.filter(status_id__status_code=status_filter)

    paginator = TripPagination()
    page = paginator.paginate_queryset(trips, request)
    serializer = TripListSerializer(page, many=True)

    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDriver])
def driver_history(request):
    """
    Get trip history for the authenticated driver.
    Returns paginated list of past trips, newest first.
    
    Query params:
        ?page=1         - Page number
        ?page_size=10   - Items per page (max 50)
        ?status=completed - Filter by status (optional)
    """
    try:
        driver = request.user.driver
    except Exception:
        return error_response(
            code='NOT_DRIVER',
            message='No driver profile found for this user',
            field='user',
            issue='User does not have a driver profile',
            status=status.HTTP_403_FORBIDDEN
        )

    trips = Trip.objects.filter(
        driver_id=driver
    ).select_related(
        'status_id', 'user_id', 'vehicle_id', 'vehicle_id__vehicle_type_id'
    ).order_by('-requested_at')

    # Optional status filter
    status_filter = request.query_params.get('status')
    if status_filter:
        trips = trips.filter(status_id__status_code=status_filter)

    paginator = TripPagination()
    page = paginator.paginate_queryset(trips, request)
    serializer = TripListSerializer(page, many=True)

    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trip_detail(request, trip_id):
    """
    Get detailed info for a single trip, including fare breakdown and ratings.
    Only the rider or assigned driver can view.
    """
    try:
        trip = Trip.objects.select_related(
            'status_id', 'driver_id', 'driver_id__user_id',
            'vehicle_id', 'vehicle_id__vehicle_type_id'
        ).prefetch_related(
            'fare_pricing', 'ratings', 'ratings__rater_id'
        ).get(id=trip_id)
    except Trip.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Trip not found',
            field='trip_id',
            issue=f'No trip with id {trip_id}',
            status=status.HTTP_404_NOT_FOUND
        )

    # Access check: must be the rider or the assigned driver
    is_rider = trip.user_id_id == request.user.id
    is_driver = (
        trip.driver_id and
        hasattr(request.user, 'driver') and
        trip.driver_id_id == request.user.driver.id
    )
    if not is_rider and not is_driver:
        return error_response(
            code='FORBIDDEN',
            message='You do not have access to this trip',
            field='trip_id',
            issue='Only the rider or assigned driver can view this trip',
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = TripDetailSerializer(trip)
    return success_response(serializer.data, status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_trip(request):
    """
    Submit a rating for a completed trip.

    Expected: {
        "trip_id": int,
        "score": int (1-5),
        "comments": str (optional)
    }

    - Riders rate drivers, drivers rate riders.
    - One rating per user per trip.
    - Auto-updates the rated user's average rating.
    """
    from servers.ride.models import Rating
    from servers.driver.models import Driver
    from servers.rider.models import Rider
    from django.db.models import Avg

    trip_id = request.data.get('trip_id')
    score = request.data.get('score')
    comments = request.data.get('comments', '')

    if not trip_id or score is None:
        return error_response(
            code='MISSING_FIELDS',
            message='trip_id and score are required',
            field='trip_id,score',
            issue='Both trip_id and score must be provided',
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        score = int(score)
    except (ValueError, TypeError):
        return error_response(
            code='INVALID_SCORE',
            message='Score must be an integer',
            field='score',
            issue='Score must be a number between 1 and 5',
            status=status.HTTP_400_BAD_REQUEST
        )

    if score < 1 or score > 5:
        return error_response(
            code='INVALID_SCORE',
            message='Score must be between 1 and 5',
            field='score',
            issue=f'Received {score}, expected 1-5',
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        trip = Trip.objects.select_related('driver_id', 'user_id', 'status_id').get(id=trip_id)
    except Trip.DoesNotExist:
        return error_response(
            code='NOT_FOUND',
            message='Trip not found',
            field='trip_id',
            issue=f'Trip {trip_id} does not exist',
            status=status.HTTP_404_NOT_FOUND
        )

    # Must be completed
    if not trip.status_id or trip.status_id.status_code != 'completed':
        return error_response(
            code='TRIP_NOT_COMPLETED',
            message='You can only rate a completed trip',
            field='trip_id',
            issue='Trip is not in completed status',
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user
    is_rider = str(trip.user_id_id) == str(user.id)
    is_driver = trip.driver_id and str(trip.driver_id.user_id_id) == str(user.id)

    if not is_rider and not is_driver:
        return error_response(
            code='FORBIDDEN',
            message='You are not a participant of this trip',
            field='trip_id',
            issue='Only the rider or driver can rate this trip',
            status=status.HTTP_403_FORBIDDEN
        )

    # Check for duplicate rating
    if Rating.objects.filter(trip_id=trip, rater_id=user).exists():
        return error_response(
            code='ALREADY_RATED',
            message='You have already rated this trip',
            field='trip_id',
            issue='Duplicate rating not allowed',
            status=status.HTTP_409_CONFLICT
        )

    with transaction.atomic():
        rating = Rating.objects.create(
            trip_id=trip,
            rater_id=user,
            score=score,
            comments=comments
        )

        # Update the rated person's average
        if is_rider and trip.driver_id:
            # Rider is rating the driver
            driver = trip.driver_id
            avg = Rating.objects.filter(
                trip_id__driver_id=driver,
                rater_id=trip.user_id
            ).exclude(
                rater_id__in=[driver.user_id]
            ).aggregate(avg_score=Avg('score'))['avg_score']
            if avg:
                driver.ratings = round(Decimal(str(avg)), 2)
                driver.save(update_fields=['ratings'])

        elif is_driver:
            # Driver is rating the rider
            try:
                rider = Rider.objects.get(user_id=trip.user_id)
                avg = Rating.objects.filter(
                    trip_id__user_id=trip.user_id
                ).exclude(
                    rater_id=trip.user_id
                ).aggregate(avg_score=Avg('score'))['avg_score']
                if avg:
                    rider.rating = round(Decimal(str(avg)), 1)
                    rider.save(update_fields=['rating'])
            except Rider.DoesNotExist:
                pass

    return success_response({
        'rating_id': rating.id,
        'trip_id': trip.id,
        'score': rating.score,
        'comments': rating.comments,
        'message': 'Rating submitted successfully',
    }, status.HTTP_201_CREATED)