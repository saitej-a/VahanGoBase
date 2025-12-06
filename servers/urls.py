from django.urls import path,include
from servers.auth_user import urls as auth_user_urls
from servers.rider import urls as rider_urls
urlpatterns=[
    path('auth/',include(auth_user_urls.urlpatterns)),
    path('rider/',include(rider_urls.urlpatterns))

]