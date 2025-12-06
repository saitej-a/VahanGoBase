from django.urls import path
from .views import request_otp,login as token, refresh,update_user
urlpatterns=[
    path('otp/',request_otp),
    path('login/',token),
    path('refresh/',refresh),
    path('update/',update_user)
]