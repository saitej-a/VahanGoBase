import boto3
from django.utils import timezone
import random
from rest_framework.response import Response
from django.conf import settings
from celery import shared_task
def get_sns_client():
    return boto3.client(
        "sns",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
def success_response(data,status):
    return Response({
        "status": "success",
        "data": data,
        "meta": {
            "timestamp": timezone.localtime(timezone.now())
        }
    },status=status)

def error_response(code,message,field,issue,status):
    return Response({
        "status": "error",
        "error": {
            "code":code,
            "message":message,
            "details":{
                "field":field,
                "issue":issue
            }
        }
    },status=status)

def generate_otp(n):
    otp=''.join(map(str,random.choices(range(0,10),k=n)))
    return otp

@shared_task
def send_otp_via_sns(phone_number, message):
    
    client = get_sns_client()
    try:
        resp = client.publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': settings.AWS_SNS_SENDER_ID
                },
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'  # or 'Promotional'
                }
            }
        )
        return resp  # contains MessageId
    except Exception as e:
        return e