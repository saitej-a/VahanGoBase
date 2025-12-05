from django.urls import path
from .views import request_otp
urlpatterns=[
    path('otp/',request_otp)
]