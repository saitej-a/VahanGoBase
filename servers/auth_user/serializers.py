from rest_framework.serializers import ModelSerializer
from django.contrib.auth import get_user_model

class UserModelSerializer(ModelSerializer):
    class Meta:
        model=get_user_model()
        fields=['id','username','email','name','phone','role','avatar_url','updated_at','created_at','is_verified']