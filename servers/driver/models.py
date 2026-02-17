from django.db import models
from django.contrib.auth import get_user_model
# Create your models here.
User=get_user_model()
class Driver(models.Model):
    user_id=models.OneToOneField(User,on_delete=models.CASCADE,related_name='driver')
    license_doc=models.CharField(max_length=512,blank=True,null=True)
    license_expiry=models.DateField(blank=True,null=True)
    status=models.CharField(max_length=20,choices=[
        ('online','Online'),('off','Off'),('active','Active'),
        ('on ride','On Ride'),('off ride','Off Ride'),('blocked','Blocked')
    ],default='off')
    total_trips=models.IntegerField(default=0)
    ratings=models.DecimalField(max_digits=3,decimal_places=2,default=0.00)
    def __str__(self) -> str:
        return self.user_id.full_name if self.user_id.full_name else self.user_id.phone_number
class VehicleType(models.Model):
    type=models.CharField(max_length=50,unique=True)
    description=models.TextField(blank=True,null=True)
    def __str__(self):
        return self.type
class Vehicle(models.Model):
    driver_id=models.ForeignKey(Driver,on_delete=models.CASCADE)
    rc_doc=models.CharField(max_length=512,blank=True,null=True)
    vehicle_type_id=models.ForeignKey(VehicleType,on_delete=models.CASCADE,related_name='vehicles')
    brand=models.CharField(max_length=100,blank=True,null=True)
    model=models.CharField(max_length=100,blank=True,null=True)
    color=models.CharField(max_length=50,blank=True,null=True)
    year=models.IntegerField(blank=True,null=True)
    vehicle_number=models.CharField(max_length=20)
    capacity=models.IntegerField(default=1)
    vehicle_pic=models.CharField(max_length=512,blank=True,null=True)
    status=models.CharField(max_length=20,choices=[
        ('active','Active'),('inactive','Inactive'),
        ('under_maintenance','Under Maintenance')
    ],default='active')
    def __str__(self) -> str:
        return f'{self.vehicle_number} - {self.driver_id}'
class DriverEarning(models.Model):
    driver_id=models.ForeignKey(Driver,on_delete=models.CASCADE,related_name='earnings')
    trip_id=models.ForeignKey('ride.Trip',on_delete=models.CASCADE,related_name='driver_earnings')
    commission=models.DecimalField(max_digits=10,decimal_places=2)
    net_amount=models.DecimalField(max_digits=10,decimal_places=2)
    def __str__(self):
        return f'Earning for Driver {self.driver_id} - Trip {self.trip_id.id}'