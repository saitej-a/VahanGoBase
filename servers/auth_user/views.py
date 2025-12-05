from rest_framework import status
from rest_framework.decorators import api_view
from base.utils import success_response,error_response,generate_otp,send_otp_via_sns,generate_username
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken,RefreshToken
from .serializers import UserModelSerializer
# Create your views here.
user_model=get_user_model()
@api_view(['POST'])
def request_otp(request):
    phone_number=request.data.get('phone_number',None)
    role=request.data.get('role','rider')

    if phone_number==None:
        return error_response(code="AUTH_MISSING_DETAILS",message='Phone number is required',field='otp',issue='missing fields',status=status.HTTP_400_BAD_REQUEST)
    otp=generate_otp(6)
    # print(otp)
    cache.set(f'otp_{phone_number}',otp,3600)
    cache.set(f'role_{phone_number}',role,3600)
    try:
        idx=send_otp_via_sns.delay(phone_number,f"Your OTP for the VahanGo is {otp} will be expired in an hour") # type: ignore
    except Exception as e:
        return error_response("AUTH_OTP_REQUEST","unable to send OTP","otp","Unable to send OTP",status.HTTP_404_NOT_FOUND)
    return success_response(data={'otp':otp,'idx':str(idx)},status=status.HTTP_200_OK)
@api_view(['POST'])
def login(request):
    phone_number=request.data.get('phone_number',None)
    otp=request.data.get('otp',None)
    otp_id=request.data.get('otp_id',None)
    device_token=request.data.get('device_token',None)
    
    role=cache.get(f'role_{phone_number}','rider')
    sent_otp=cache.get(f'otp_{phone_number}',None)
    if sent_otp==None:
        return error_response('AUTH_INVALID_OTP','OTP Expired','Authentication','OTP Expired',status.HTTP_400_BAD_REQUEST)
    if phone_number==None:
        return error_response('AUTH_PHONE_REQUIRED','Phone number required','Authentication','Missing Field',status.HTTP_400_BAD_REQUEST)
    if otp!=sent_otp:
        return error_response("AUTH_INVALID_OTP",'OTP Expired','Authentication',"OTP Incorrect",status.HTTP_400_BAD_REQUEST)
    cache.delete(f'otp_{phone_number}')
    if user_model.objects.filter(phone=phone_number).exists():
        user=user_model.objects.get(phone=phone_number)
        data=UserModelSerializer(user)
        return success_response(data={'token':str(AccessToken.for_user(user)),'refresh_token':str(RefreshToken.for_user(user)),'user':data.data},status=status.HTTP_200_OK)
    else:
        

        user=user_model.objects.create_user(username=generate_username(),phone=phone_number,role=role)
        data=UserModelSerializer(user)
        return success_response(data={'token':str(AccessToken.for_user(user)),'refresh_token':str(RefreshToken.for_user(user)),'user':data.data},status=status.HTTP_200_OK)
@api_view(['POST'])
def refresh(request):
    refresh_token=request.data.get('refresh_token',None)
    if refresh_token==None:
        return error_response('AUTH_REFRESH_TOKEN','Refresh token is required','Authentication','Refresh token is missing',status.HTTP_400_BAD_REQUEST)
    return success_response({'access':AccessToken(refresh_token)},status=status.HTTP_200_OK) 