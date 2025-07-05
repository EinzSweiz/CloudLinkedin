import os
import logging
from pathlib import Path
from decouple import config
from django.templatetags.static import static


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

#APP
INSTALLED_APPS = [
    "unfold",  # before django.contrib.admin
    "unfold.contrib.filters",  # optional, if special filters are needed
    "unfold.contrib.forms",  # optional, if special form elements are needed
    "unfold.contrib.inlines",  # optional, if special inlines are needed
    "unfold.contrib.import_export",  # optional, if django-import-export package is used
    "unfold.contrib.guardian",  # optional, if django-guardian package is used
    "unfold.contrib.simple_history",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    "channels",
    #Apps for LinkedIn parser
    "mailer",
    "parser_controler",
    "django_celery_beat",
    "exporter",
    'django_celery_results',
    'rest_framework',
    'authorization',
    'payments',
]

UNFOLD = {
    "SITE_TITLE": "Linkedin Parser",
    "SITE_HEADER": "Linkedin Parser Admin",
    "SITE_TAGLINE": "B2B LinkedIn Automation",
    "SHOW_HISTORY": True,
    "STYLES": [
        lambda request: ("/static/admin/css/beautiful_admin.css")
    ],
    "DASHBOARD_CALLBACK": "b2b_linkedin_app.admin.dashboard_callback",
    "SITE_ICON": "/static/images/linkedin-svgrepo-com.svg",  # place your icon in static folder
    "LOGIN": {
        "image": "/static/images/login_bg.svg",  # optional background image
        "heading": "Welcome to LinkedIn Parser",
        "sub_heading": "Automate your lead generation",
    },
    "FOOTER": {
        "copyright": "Linkedin Parser © 2025",
        "links": [
            {"name": "Support", "url": "mailto:support@example.com"},
        ],
    },
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'b2b_linkedin_app.middleware.payment_required_middleware.PaymentRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True  # For development only!

# For production, use specific origins:
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:6080",
#     "http://127.0.0.1:6080",
#     "ws://localhost:6080",
#     "wss://localhost:6080",
# ]

# Allow WebSocket connections
CORS_ALLOW_CREDENTIALS = True

# Allow WebSocket headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'sec-websocket-key',
    'sec-websocket-protocol',
    'sec-websocket-version',
    'upgrade',
    'connection',
]

# Add localhost to allowed hosts
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

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

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
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
        'exporter': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
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
ASGI_APPLICATION = 'b2b_linkedin_app.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('redis', 6379)],
        },
    },
}

# =========================
# SMTP
# =========================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', cast=str, default=None)
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', cast=str, default=None)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', cast=str, default=None)


# =========================
# GOOGLE SHEETS CONFIGURATION - ENHANCED
# =========================
GSHEET_CREDENTIALS_PATH = BASE_DIR / "credentials/linkedin-parser-463408-e93a62d9e95d.json"
GSHEET_SPREADSHEET_ID = "10reLINkOiYPSfMaWoF7MSd4doXNKk0X3skbJzij8s3E"

# Google Sheets Export Settings
GSHEET_EXPORT_ENABLED = config('GSHEET_EXPORT_ENABLED', cast=bool, default=True)
GSHEET_BATCH_SIZE = config('GSHEET_BATCH_SIZE', cast=int, default=10)
GSHEET_RETRY_ATTEMPTS = config('GSHEET_RETRY_ATTEMPTS', cast=int, default=3)
GSHEET_RATE_LIMIT_DELAY = config('GSHEET_RATE_LIMIT_DELAY', cast=int, default=2)

# Validate Google Sheets configuration on startup
def validate_google_sheets_config():
    """Validate Google Sheets configuration"""
    import os
    
    if GSHEET_EXPORT_ENABLED:
        # Check credentials file exists
        if not os.path.exists(GSHEET_CREDENTIALS_PATH):
            print(f"⚠️  WARNING: Google Sheets credentials file not found: {GSHEET_CREDENTIALS_PATH}")
            return False
            
        # Check spreadsheet ID is set
        if not GSHEET_SPREADSHEET_ID:
            print("⚠️  WARNING: GSHEET_SPREADSHEET_ID not configured")
            return False
            
        print("Google Sheets configuration validated")
        return True
    else:
        print("ℹ️  Google Sheets export is disabled")
        return True

# Run validation on startup (optional)
try:
    validate_google_sheets_config()
except Exception as e:
    print(f" Error validating Google Sheets config: {e}")