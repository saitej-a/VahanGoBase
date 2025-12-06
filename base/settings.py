
from pathlib import Path
import os
from dotenv import load_dotenv
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-*5(=ti+p9y=gyu0zkoojz$b55meinl-5w*ibm)3mpkm2ybiohh'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'servers.auth_user',
    
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'base.middleware.ExceptionHandlingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    
]

ROOT_URLCONF = 'base.urls'
REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES':[
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication'
    ],
    'DEFAULT_PAGINATION_CLASS':'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE':20
}
from datetime import timedelta
SIMPLE_JWT={
    'ACCESS_TOKEN_LIFETIME':timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME':timedelta(days=7),

}
# celery
CELERY_BROKER_URL=os.environ.get('REDIS_URL','redis://redis:6379')+'/0'
# cache
CACHES={
    'default':{
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL','redis://redis:6379')+'/1',
    }
}
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

#AWS
AWS_SECRET_ACCESS_KEY=os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_ACCESS_KEY_ID=os.environ.get("AWS_ACCESS_KEY_ID")
AWS_REGION=os.environ.get("AWS_REGION")
AWS_SNS_SENDER_ID=os.environ.get("AWS_SNS_SENDER_ID")

WSGI_APPLICATION = 'base.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Custom user model
AUTH_USER_MODEL='auth_user.customUser'
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
