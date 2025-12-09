import requests as re
import os
import logging
logger=logging.getLogger(__name__)
GMAPS_API=os.environ.get('GMAPS_API')
GMAPS_URL:str=os.environ.get('GMAPS_DISTANCE_MATRIX_URL','')
SESSION=re.session()

def get_dist_duration(src_lat,src_lng,dest_lat,dest_lng):
    result=SESSION.get(GMAPS_URL,params={
        'destinations':f'{dest_lng},{dest_lat}',
        'origins':f'{src_lng},{src_lat}',
        'key':GMAPS_API
    })
    result_respose=result.json()
    try:
        row=result_respose.get('rows')[0]
        ele=row.get('elements')[0]
        dist=ele.get('distance').get('value')
        duration=ele.get('duration').get('value')
        return dist,duration

    except Exception as e:
        logger.error('Unexpected error occured '+str(e))
        return 0,0
def estimate_amount(dist,dur,base_fare=20,type_of='auto'):
    pass