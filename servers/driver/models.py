from django.db import models
from django.contrib.auth import get_user_model
import uuid
# Create your models here.
User=get_user_model()
class Driver(models.Model):
    id=models.UUIDField(editable=False,primary_key=True,default=uuid.uuid4)
    user_id=models.OneToOneField(User,on_delete=models.CASCADE,related_name='driver')
    is_verified=models.BooleanField(default=False)
    is_active=models.BooleanField(default=False)
    total_rides=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    rating=models.FloatField(default=0.0)
    def __str__(self) -> str:
        return self.user_id.name
class Vehicle(models.Model):
    driver_id=models.ForeignKey(Driver,on_delete=models.CASCADE)
    vehicle_type=models.CharField(choices=[
        ('bike','Bike'),('car','Car'),('auto','Auto')
    ])
    model=models.CharField(max_length=100)
    reg_num=models.CharField(max_length=20)
    capacity=models.IntegerField()
    def __str__(self) -> str:
        return f'{self.reg_num} - {self.driver_id}'