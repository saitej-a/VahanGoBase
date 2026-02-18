from rest_framework import serializers
from .models import FavoritePlace, Rider, Notification


class RiderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rider
        fields = '__all__'


class FavoritePlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoritePlace
        fields = ['id', 'user_id', 'address_text', 'latitude', 'longitude']
        read_only_fields = ['user_id']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'is_read']
