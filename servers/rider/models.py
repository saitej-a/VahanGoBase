from django.db import models
from django.contrib.auth import get_user_model

User=get_user_model()
class Rider(models.Model):
    user_id=models.OneToOneField(User,on_delete=models.CASCADE,related_name='rider')
    created_at=models.DateTimeField(auto_now_add=True)
    rating=models.DecimalField(decimal_places=1,max_digits=2,default=5.0)
    def __str__(self):
        return self.user_id.full_name if self.user_id.full_name else self.user_id.phone_number
class FavoritePlace(models.Model):
    user_id=models.ForeignKey(User,on_delete=models.CASCADE,related_name='favorite_places')
    address_text=models.CharField(max_length=512,blank=True,null=True)
    latitude=models.DecimalField(max_digits=10,decimal_places=7)
    longitude=models.DecimalField(max_digits=10,decimal_places=7)
    def __str__(self):
        return f'{self.user_id} - {self.address_text}'
class Wallet(models.Model):
    user_id=models.OneToOneField(User,on_delete=models.CASCADE,related_name='wallet')
    balance=models.DecimalField(max_digits=12,decimal_places=2,default=0.00)
    def __str__(self):
        return f'{self.user_id} - {self.balance}'
class Notification(models.Model):
    user_id=models.ForeignKey(User,on_delete=models.CASCADE,related_name='notifications')
    title=models.CharField(max_length=256)
    message=models.TextField()
    is_read=models.BooleanField(default=False)
    def __str__(self):
        return f'{self.user_id} - {self.title}'