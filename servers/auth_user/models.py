from django.db import models
import uuid
from .usermanager import customUserManager
from django.contrib.auth.models import AbstractUser
class customUser(AbstractUser):
    full_name = models.CharField(max_length=256, blank=True, null=True)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.CharField(max_length=256, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    house_no = models.CharField(max_length=50, blank=True, null=True)
    street = models.CharField(max_length=256, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=[("rider", "Rider"), ("driver", 'Driver'), ('admin', 'Admin')])
    avatar = models.CharField(max_length=512, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['email']
    
    objects = customUserManager()
    
    def __str__(self) -> str:
        return self.full_name if self.full_name else self.phone_number