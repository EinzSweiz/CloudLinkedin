import os
import logging
from pathlib import Path
from decouple import config


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

AUTH_USER_MODEL = 'authorization.User'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-$l8%s@zu$b4j%+=@d-m9rp4k%&z33_8#ij!_6y&u6h24nj-4_6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

#HUNTER API KEY
HUNTER_API_KEY = config('HUNTER_API_KEY', cast=str, default=None)

#-----------------------------
#     MailGun SETTINGS 
#-----------------------------
MAILGUN_DOMAIN=config('MAILGUN_DOMAIN', cast=str, default=None)
MAILGUN_API_KEY=config('MAILGUN_API_KEY', cast=str, default=None)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    #Apps for LinkedIn parser
    "mailer",
    "parser_controler",
    "django_celery_beat",
    'django_celery_results',
    'authorization',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'b2b_linkedin_app.middleware.payment_required_middleware.PaymentRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'b2b_linkedin_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
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

WSGI_APPLICATION = 'b2b_linkedin_app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': 'db',
        'PORT': config('DB_PORT', default='5433'),
    }
}

#------------------------------
#       ENV DATA 
#------------------------------
LINKEDIN_LOGIN_URL = config('LINKEDIN_LOGIN_URL', cast=str, default="https://www.linkedin.com/oauth/v2/authorization")
LINKEDIN_SEARCH_URL = config('LINKEDIN_SEARCH_URL', cast=str, default="https://api.linkedin.com/v2/search/people")
EMAIL = config('EMAIL', cast=str)
PASSWORD = config('PASSWORD', cast=str)

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [BASE_DIR / "static"]

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': True,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'parser_controler': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    }

}

# CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_BROKER_URL = "amqp://admin:admin@rabbitmq:5672//"
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'  # если используешь Redis для результатов
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# ==========================
# STRIPE CONFIGURATION
# ==========================
STRIPE_PUBLISH_KEY = config('STRIPE_PUBLISH_KEY', cast=str, default=None)
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', cast=str, default=None)
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', cast=str, default=None)
STRIPE_SUBSCRIPTION_PRICE_ID = config('STRIPE_SUBSCRIPTION_PRICE_ID', cast=str, default=None)

os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

CELERYD_HIJACK_ROOT_LOGGER = False 