import copy
from rest_framework import status
from base.utils import success_response,error_response
from rest_framework.decorators import api_view,permission_classes
from .serializers import FavoriteLocationSerializer
from rest_framework.permissions import IsAuthenticated
from .models import FavoriteLocation
from ..redis import nearby_drivers

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_favorite_locations(request):
    data=copy.copy(request.data)
    data['rider_id']=request.user.rider.id
    instance=FavoriteLocationSerializer(data=data)
    if instance.is_valid():
        instance.save()
        return success_response({"data":instance.data},status.HTTP_200_OK)
    else:
        return error_response('','','','',status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_favorite_locations(request):
    query_set=FavoriteLocation.objects.filter(rider_id=request.user.rider.id)
    data=FavoriteLocationSerializer(query_set,many=True)
    return success_response(data.data,status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_drivers(request):
    return success_response(str(nearby_drivers(request.data.get('lng'),request.data.get('lat'))),status.HTTP_200_OK)