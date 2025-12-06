from django.db import models
from django.contrib.auth import get_user_model
import uuid

user_model=get_user_model()
class Rider(models.Model):
    user_id=models.OneToOneField(user_model,on_delete=models.CASCADE,related_name='rider')
    id=models.UUIDField(default=uuid.uuid4,primary_key=True,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)
    rating=models.DecimalField(decimal_places=1,max_digits=2,default=5.0)
    def __str__(self):
        return self.user_id.name
class FavoriteLocation(models.Model):
    label=models.CharField(null=False,blank=False,max_length=100)
    address=models.CharField(null=True,blank=True,max_length=256)
    rider_id=models.ForeignKey(Rider,on_delete=models.CASCADE,related_name='favoritelocation')
    lat=models.FloatField()
    lng=models.FloatField()
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self) -> str:
        return f'{self.rider_id.user_id.name}-{self.label}'

