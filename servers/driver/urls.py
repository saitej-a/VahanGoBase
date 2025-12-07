from django.urls import path
from .views import add_driver
urlpatterns=[
    path('add/',add_driver)
]