import redis
from django.conf import settings
redis_client=redis.Redis.from_url(settings.REDIS_URL+'/2',decode_responses=True)
GEO_KEY='drivers:geo'
def add_driver_location(driver_id,lng,lat):
    member=f'driver:{driver_id}'
    redis_client.geoadd(GEO_KEY,[lng,lat,member])
def nearby_drivers(lng,lat,radius=1000,count=10):
    drivers=redis_client.geosearch(GEO_KEY,longitude=lng,latitude=lat,radius=radius,count=count,unit='m',sort='ASC',withdist=True,withcoord=True)
    # print(drivers)
    return drivers
def remove_driver(driver_id):
    redis_client.zrem(GEO_KEY,f'driver:{driver_id}')
