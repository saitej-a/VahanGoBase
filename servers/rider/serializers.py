from rest_framework.serializers import ModelSerializer
from .models import FavoritePlace
class FavoritePlaceSerializer(ModelSerializer):
    class Meta:
        model=FavoritePlace
        fields='__all__'
