from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('online', 'Online'),
    ]

    trip_id = models.ForeignKey('ride.Trip', on_delete=models.CASCADE, related_name='payments')
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=256, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=256, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=512, blank=True, null=True)

    # Legacy fields kept for compatibility
    driver_txn_id = models.CharField(max_length=256, blank=True, null=True)
    driver_name = models.CharField(max_length=256, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Payment {self.id} - Trip {self.trip_id.id} ({self.status})'

    class Meta:
        ordering = ['-created_at']


class TransactionHistory(models.Model):
    trip_id = models.ForeignKey('ride.Trip', on_delete=models.CASCADE, related_name='transactions')
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    driver_id = models.ForeignKey('driver.Driver', on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)
    razorpay_payment_id = models.CharField(max_length=256, blank=True, null=True)
    user_name = models.CharField(max_length=256, blank=True, null=True)
    user_txn_id = models.CharField(max_length=256, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Transaction {self.id} - Trip {self.trip_id.id}'

    class Meta:
        verbose_name_plural = 'Transaction histories'
        ordering = ['-created_at']
