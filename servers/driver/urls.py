from django.urls import path
from .views import add_driver,update_location,remove_driver_view
urlpatterns=[
    path('add/',add_driver),
    path('update_location/',update_location),
    path('remove_driver/',remove_driver_view)
]