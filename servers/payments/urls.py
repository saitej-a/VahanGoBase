from django.urls import path
from .views import (
    create_order, verify_payment, razorpay_webhook, payment_history, refund_payment
)

urlpatterns = [
    path('create-order/', create_order),
    path('verify/', verify_payment),
    path('webhook/', razorpay_webhook),
    path('history/', payment_history),
    path('refund/', refund_payment),
]
