from base.utils import success_response,error_response
from servers.redis import add_driver_location
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_driver(request):
    driver_id=request.user.driver.id
    lng,lat=request.data.get('lng'),request.data.get('lat')
    add_driver_location(driver_id,lat=lat,lng=lng)
    return success_response('',status.HTTP_200_OK)