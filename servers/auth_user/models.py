from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
class customUser(AbstractUser):
    id=models.UUIDField(primary_key=True,unique=True,default=uuid.uuid4,editable=False)
    email=models.CharField(max_length=128,unique=True,blank=False)
    name=models.CharField(max_length=128,blank=False,null=False)
    phone=models.CharField(max_length=20,blank=False,null=False)
    role=models.CharField(choices=[("rider","Rider"),("driver",'Driver'),('admin','Admin')])
    avatar_url=models.CharField(blank=True,null=True)
    updated_at=models.DateTimeField(auto_now_add=True)
    created_at=models.DateTimeField(auto_now=True)
    is_verified=models.BooleanField(default=False)