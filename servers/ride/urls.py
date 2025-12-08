from django.urls import path
from .views import ride_request
urlpatterns=[
    path('ride-request/',ride_request)
]