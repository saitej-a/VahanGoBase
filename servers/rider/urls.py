from django.urls import path
from .views import save_favorite_locations,get_favorite_locations

urlpatterns=[
    path('locations/',save_favorite_locations),
    path('locations/all/',get_favorite_locations)
]