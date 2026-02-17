import logging

logger = logging.getLogger(__name__)

# Base fare constants (can be moved to DB via VehicleFarePricing later)
BASE_FARE = 30.00        # Base fare in INR
PER_KM_FARE = 12.00      # Per kilometer fare
PER_MIN_FARE = 2.00       # Per minute fare
MIN_FARE = 50.00          # Minimum fare


def estimate_amount(distance_km, duration_min):
    """
    Estimate the fare for a trip based on distance and duration.
    
    Args:
        distance_km: Estimated distance in kilometers
        duration_min: Estimated duration in minutes
    
    Returns:
        Decimal: Estimated fare amount
    
    Note:
        This is a placeholder implementation. In production, integrate
        with a routing API (Google Maps, OSRM) to get actual distance
        and duration, and use VehicleFarePricing from the database.
    """
    try:
        distance_km = max(float(distance_km), 0)
        duration_min = max(float(duration_min), 0)

        fare = BASE_FARE + (distance_km * PER_KM_FARE) + (duration_min * PER_MIN_FARE)
        fare = max(fare, MIN_FARE)

        return round(fare, 2)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error estimating fare: {str(e)}, returning minimum fare")
        return MIN_FARE
