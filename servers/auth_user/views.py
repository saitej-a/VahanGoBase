from rest_framework import status
from rest_framework.decorators import api_view
from base.utils import success_response,error_response,generate_otp,send_otp_via_sns
# Create your views here.
@api_view(['POST'])
def request_otp(request):
    phone_number=request.data.get('phone_number',None)
    role=request.data.get('role','rider')

    if phone_number==None:
        return error_response(code="AUTH_MISSING_DETAILS",message='Phone number is required',field='otp',issue='missing fields',status=status.HTTP_400_BAD_REQUEST)
    otp=generate_otp(6)
    # print(otp)
    try:
        idx=send_otp_via_sns.delay(phone_number,f"Your OTP for the VahanGo is {otp} will be expired in an hour") # type: ignore
    except Exception as e:
        return error_response("AUTH_OTP_REQUEST","unable to send OTP","otp","Unable to send OTP",status.HTTP_404_NOT_FOUND)
    return success_response(data={'otp':otp,'idx':str(idx)},status=status.HTTP_200_OK)
