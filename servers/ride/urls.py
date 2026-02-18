from django.urls import path
from .views import ride_request, estimate_fare, ride_history, driver_history, trip_detail, rate_trip

urlpatterns = [
    path('ride-request/', ride_request),
    path('estimate-fare/', estimate_fare),
    path('ride-history/', ride_history),
    path('driver-history/', driver_history),
    path('trip/<int:trip_id>/', trip_detail),
    path('rate-trip/', rate_trip),
]