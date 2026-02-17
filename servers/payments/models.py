from django.db import models
from django.contrib.auth import get_user_model

User=get_user_model()
class Payment(models.Model):
    trip_id=models.ForeignKey('ride.Trip',on_delete=models.CASCADE,related_name='payments')
    user_id=models.ForeignKey(User,on_delete=models.CASCADE,related_name='payments')
    amount=models.DecimalField(max_digits=10,decimal_places=2)
    method=models.CharField(max_length=20,choices=[
        ('cash','Cash'),('online','Online')
    ])
    driver_txn_id=models.CharField(max_length=256,blank=True,null=True)
    driver_name=models.CharField(max_length=256,blank=True,null=True)
    status=models.CharField(max_length=20,choices=[
        ('processing','Processing'),('completed','Completed')
    ],default='processing')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'Payment {self.id} - Trip {self.trip_id.id}'
class TransactionHistory(models.Model):
    trip_id=models.ForeignKey('ride.Trip',on_delete=models.CASCADE,related_name='transactions')
    user_id=models.ForeignKey(User,on_delete=models.CASCADE,related_name='transactions')
    driver_id=models.ForeignKey('driver.Driver',on_delete=models.CASCADE,related_name='transactions')
    amount=models.DecimalField(max_digits=10,decimal_places=2)
    method=models.CharField(max_length=50)
    user_name=models.CharField(max_length=256,blank=True,null=True)
    user_txn_id=models.CharField(max_length=256,blank=True,null=True)
    status=models.CharField(max_length=50,blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'Transaction {self.id} - Trip {self.trip_id.id}'
    class Meta:
        verbose_name_plural='Transaction histories'
