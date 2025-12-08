from django.db import models
from uuid import uuid4
from servers.rider.models import Rider
from servers.driver.models import Vehicle,Driver
# Create your models here.
class Ride(models.Model):
    id=models.UUIDField(default=uuid4,editable=False,primary_key=True)
    src_lat=models.FloatField()
    src_lng=models.FloatField()
    dest_lat=models.FloatField()
    dest_lng=models.FloatField()
    vehicle_id=models.ForeignKey(Vehicle,on_delete=models.DO_NOTHING,related_name='vehicle')
    driver_id=models.ForeignKey(Driver,on_delete=models.DO_NOTHING,related_name='driver')
    rider_id=models.ManyToManyField(Rider,related_name='riders')
    is_shared=models.BooleanField()
    estimated_amount=models.FloatField()
    actual_amount=models.FloatField()
    surge_mult=models.DecimalField(max_digits=3,decimal_places=2)
    
