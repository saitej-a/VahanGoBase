from django.urls import path,include
from servers.auth_user import urls
urlpatterns=[
    path('auth/',include(urls.urlpatterns))
]