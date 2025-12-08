from django.shortcuts import render
from rest_framework import status
from base.utils import success_response,error_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view,permission_classes
from servers.ride.models import Ride
from django.db import transaction
from .utils import get_estimated_amount
# Create your views here.
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ride_request(request):
    src_lat=request.data.get('src_lat')
    src_lng=request.data.get('src_lng')
    dest_lat=request.data.get('dest_lat')
    dest_lng=request.data.get('dest_lng')
    is_shared=request.data.get('is_shared')
    # implemented from here
    if not (src_lat or src_lng):
        return error_response()
    if not (dest_lat or dest_lng):
        return error_response()
    estimated_amount=get_estimated_amount()
    try:
        with transaction.atomic():
            ride_obj=Ride.objects.create(src_lat=src_lat,src_lng=src_lng,dest_lat=dest_lat,dest_lng=dest_lng,estimated_amount=estimated_amount,is_shared=is_shared,rider_id=request.user.rider)
            pass
    except Exception as e:
        pass
    