from rest_framework.serializers import ModelSerializer
from .models import FavoriteLocation
class FavoriteLocationSerializer(ModelSerializer):
    class Meta:
        model=FavoriteLocation
        fields='__all__'
