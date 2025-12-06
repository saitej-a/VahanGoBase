from rest_framework import status
from rest_framework.decorators import api_view,permission_classes
from base.utils import success_response,error_response,generate_otp,send_otp_via_sns,generate_username
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken,RefreshToken
from .serializers import UserModelSerializer
from django.db import transaction, IntegrityError
from rest_framework_simplejwt.exceptions import InvalidToken,TokenError
from servers.rider.models import Rider
from rest_framework.permissions import IsAuthenticated

user_model=get_user_model()
@api_view(['POST'])
def request_otp(request):
    phone_number=request.data.get('phone_number',None)
    role=request.data.get('role','rider')
    # print(phone_number)
    if phone_number==None:
        return error_response(code="AUTH_MISSING_DETAILS",message='Phone number is required',field='otp',issue='missing fields',status=status.HTTP_400_BAD_REQUEST)
    otp=generate_otp(6)
    # print(otp)
    cache.set(f'otp_role_{phone_number}',{'otp':otp,'role':role,'attempts':0},600)
    try:
        idx=send_otp_via_sns.delay(phone_number,f"Your OTP for the VahanGo is {otp} will be expired in 10 Minutes") # type: ignore
    except Exception as e:
        return error_response("AUTH_OTP_REQUEST","unable to send OTP","otp","Unable to send OTP",status.HTTP_404_NOT_FOUND)
    return success_response(data={'otp':otp,'idx':str(idx),'message':"OTP sent Successfully"},status=status.HTTP_200_OK)
@api_view(['POST'])
def login(request):
    phone_number=request.data.get('phone_number',None)
    otp=request.data.get('otp',None)
    otp_id=request.data.get('otp_id',None)
    device_token=request.data.get('device_token',None)
    password=request.data.get('password',None)
    cache_data=cache.get(f'otp_role_{phone_number}',{})
    role=cache_data.get('role','rider')
    sent_otp=cache_data.get('otp',None)
    attempts=cache_data.get('attempts',0)
    if sent_otp==None:
        return error_response('AUTH_INVALID_OTP','OTP Expired','Authentication','OTP Expired',status.HTTP_400_BAD_REQUEST)
    if phone_number==None:
        return error_response('AUTH_PHONE_REQUIRED','Phone number required','Authentication','Missing Field',status.HTTP_400_BAD_REQUEST)
    if attempts>=5:
        return error_response('AUTH_TOO_MANY',"Too many Attempts",'Authentication','Too many login attempts',status.HTTP_429_TOO_MANY_REQUESTS)
    if otp!=sent_otp:
        cache_data['attempts']=attempts+1
        cache.set(f'otp_role_{phone_number}',cache_data)
        return error_response("AUTH_INVALID_OTP",'OTP Expired','Authentication',"OTP Incorrect",status.HTTP_400_BAD_REQUEST)
    cache.delete(f'otp_role_{phone_number}')
    try:
        with transaction.atomic():
            user, created = user_model.objects.get_or_create(phone=phone_number, defaults={
                "username": generate_username(),
                "role": role,
                "is_active": True,
                
            })
            if created:
                user.is_verified=True
                if password:
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                
                user.save()
                if role=='rider':
                    rider=Rider.objects.create(user_id=user)
                    rider.save()
                elif role=='driver':
                    pass

        
    except IntegrityError:
        user=user_model.objects.get(phone=phone_number)
    data=UserModelSerializer(user)
    return success_response(data={'token':str(AccessToken.for_user(user)),'refresh_token':str(RefreshToken.for_user(user)),'user':data.data},status=status.HTTP_200_OK)
@api_view(['POST'])
def refresh(request):
    refresh_token=request.data.get('refresh_token',None)
    if refresh_token==None:
        return error_response('AUTH_REFRESH_TOKEN','Refresh token is required','Authentication','Refresh token is missing',status.HTTP_400_BAD_REQUEST)
    try:
        gen_refresh_token=RefreshToken(refresh_token)
        return success_response({'token':str(gen_refresh_token.access_token),'refresh_token':gen_refresh_token},status=status.HTTP_200_OK)
    except InvalidToken:
        return error_response('AUTH_INVALID_TOKEN','TOken is invalid','Authentication','Refresh token is invalid',status.HTTP_400_BAD_REQUEST)
    except TokenError:
        return error_response('AUTH_TOKEN_ERROR','Token Error','Authentication','Token error',status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request):
    data=request.data
    user=user_model.objects.get(id=request.user.id)
    try:
        user_data=UserModelSerializer(user,data=data,partial=True)
        if user_data.is_valid():
            user_data.save()
            return success_response(user_data.data,status.HTTP_200_OK)
        else:
            return error_response('AUTH_INVALID_UPDATE','Not valid Information','Authentication','Invalid details',status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return error_response('AUTH_UNABLE_UPDATE','Not valid Information','Authentication','Invalid details',status.HTTP_406_NOT_ACCEPTABLE)