from django.urls import path
from .views import request_otp,login as token, refresh
urlpatterns=[
    path('otp/',request_otp),
    path('login/',token),
    path('refresh/',refresh)
]