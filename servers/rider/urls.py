from django.urls import path
from .views import (
    save_favorite_locations, get_favorite_locations, get_nearby_drivers,
    list_notifications, mark_notification_read, mark_all_notifications_read
)

urlpatterns=[
    path('locations/',save_favorite_locations),
    path('locations/all/',get_favorite_locations),
    path('nearby/',get_nearby_drivers),
    # Notifications
    path('notifications/', list_notifications),
    path('notifications/<int:notif_id>/read/', mark_notification_read),
    path('notifications/read-all/', mark_all_notifications_read),
]