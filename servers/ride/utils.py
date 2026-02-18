import math
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Fallback fare constants (used when VehicleFarePricing not found in DB)
DEFAULT_BASE_FARE = Decimal('30.00')
DEFAULT_PER_KM_FARE = Decimal('12.00')
DEFAULT_PER_MIN_FARE = Decimal('2.00')
DEFAULT_MIN_FARE = Decimal('50.00')
DEFAULT_NIGHT_SURGE = Decimal('1.50')

# Distance sanity check: max allowed ratio of reported distance to straight-line distance
MAX_DISTANCE_RATIO = 3.0
# Minimum straight-line distance (km) to apply sanity check (skip for very short trips)
MIN_STRAIGHT_LINE_KM = 0.5


def _haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate straight-line distance between two lat/lng points using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def validate_distance(distance_km, pickup_lat, pickup_long, dest_lat, dest_long):
    """
    Sanity-check the frontend-reported distance against straight-line distance.
    
    Returns:
        tuple: (is_valid: bool, straight_line_km: float, message: str)
    """
    try:
        distance_km = float(distance_km)
        straight_line = _haversine_km(pickup_lat, pickup_long, dest_lat, dest_long)

        # Skip check for very short trips
        if straight_line < MIN_STRAIGHT_LINE_KM:
            return True, round(straight_line, 2), 'OK'

        # Reported distance must be >= straight-line (can't be shorter than bird-flies)
        if distance_km < straight_line * 0.8:
            return False, round(straight_line, 2), (
                f'Reported distance ({distance_km:.1f} km) is less than '
                f'straight-line distance ({straight_line:.1f} km)'
            )

        # Reported distance shouldn't be absurdly more than straight-line
        if distance_km > straight_line * MAX_DISTANCE_RATIO:
            return False, round(straight_line, 2), (
                f'Reported distance ({distance_km:.1f} km) is more than '
                f'{MAX_DISTANCE_RATIO}x the straight-line distance ({straight_line:.1f} km)'
            )

        return True, round(straight_line, 2), 'OK'
    except (ValueError, TypeError) as e:
        logger.warning(f"Distance validation error: {e}")
        return False, 0, f'Invalid coordinates or distance: {e}'


def _is_night_hours():
    """Check if current time is within night surge hours (11 PM - 5 AM)."""
    current_hour = timezone.localtime(timezone.now()).hour
    return current_hour >= 23 or current_hour < 5


def estimate_amount(distance_km, duration_min, vehicle_type=None):
    """
    Estimate fare using VehicleFarePricing from DB.
    Falls back to default constants if vehicle type pricing not found.
    
    Args:
        distance_km: Distance in kilometers (from frontend/Google Maps)
        duration_min: Duration in minutes (from frontend/Google Maps)
        vehicle_type: Vehicle type name (e.g. 'sedan', 'suv') or None for defaults
    
    Returns:
        dict: {
            'total_fare': Decimal,
            'base_fare': Decimal,
            'distance_fare': Decimal,
            'time_fare': Decimal,
            'surge_multiplier': Decimal,
            'min_fare_applied': bool,
            'vehicle_type': str,
            'source': str  ('db' or 'default')
        }
    """
    try:
        distance_km = max(Decimal(str(distance_km)), Decimal('0'))
        duration_min = max(Decimal(str(duration_min)), Decimal('0'))
    except (ValueError, TypeError, ArithmeticError) as e:
        logger.warning(f"Invalid fare input: {e}, returning defaults with zero distance")
        distance_km = Decimal('0')
        duration_min = Decimal('0')

    # Try DB lookup
    base_fare = DEFAULT_BASE_FARE
    per_km = DEFAULT_PER_KM_FARE
    per_min = DEFAULT_PER_MIN_FARE
    min_fare = DEFAULT_MIN_FARE
    night_surge = DEFAULT_NIGHT_SURGE
    source = 'default'

    if vehicle_type:
        try:
            from servers.ride.models import VehicleFarePricing
            from servers.driver.models import VehicleType

            vt = VehicleType.objects.filter(type__iexact=vehicle_type).first()
            if vt:
                pricing = VehicleFarePricing.objects.filter(vehicle_type_id=vt).first()
                if pricing:
                    base_fare = pricing.base_fare
                    per_km = pricing.per_km_fare
                    per_min = pricing.per_min_fare
                    min_fare = pricing.min_fare
                    night_surge = pricing.night_surge_multiplier
                    source = 'db'
                else:
                    logger.info(f"No fare pricing found for vehicle type '{vehicle_type}', using defaults")
            else:
                logger.info(f"Vehicle type '{vehicle_type}' not found, using defaults")
        except Exception as e:
            logger.warning(f"DB lookup failed for vehicle type '{vehicle_type}': {e}, using defaults")

    # Calculate fare components
    distance_fare = per_km * distance_km
    time_fare = per_min * duration_min
    subtotal = base_fare + distance_fare + time_fare

    # Apply night surge
    surge_multiplier = Decimal('1.00')
    if _is_night_hours():
        surge_multiplier = night_surge
        subtotal = subtotal * surge_multiplier

    # Apply minimum fare
    min_fare_applied = False
    if subtotal < min_fare:
        subtotal = min_fare
        min_fare_applied = True

    total_fare = round(subtotal, 2)

    return {
        'total_fare': total_fare,
        'base_fare': round(base_fare, 2),
        'distance_fare': round(distance_fare, 2),
        'time_fare': round(time_fare, 2),
        'surge_multiplier': surge_multiplier,
        'min_fare_applied': min_fare_applied,
        'vehicle_type': vehicle_type or 'default',
        'source': source,
    }
