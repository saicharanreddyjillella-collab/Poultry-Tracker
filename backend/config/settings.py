import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG defaults to False (safe for production). Set DEBUG=True in the
# environment for local development.
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# SECRET_KEY must be provided via the environment in production. In DEBUG we
# fall back to a throwaway key so local dev is zero-config; with DEBUG off and
# no key set we fail fast rather than boot with a known, insecure key.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key-not-for-production'
    else:
        raise RuntimeError(
            'SECRET_KEY environment variable must be set when DEBUG is False.'
        )

# ALLOWED_HOSTS defaults to localhost; set the real host(s) via the
# environment in production (comma-separated).
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    'ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

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
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# Database — use PostgreSQL if DATABASE_URL is set, else SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import re
    m = re.match(r'postgres://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': m.group(5),
            'USER': m.group(1),
            'PASSWORD': m.group(2),
            'HOST': m.group(3),
            'PORT': m.group(4),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Brute-force protection on the login endpoint (per client IP).
        'login': '10/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# Password strength validators (enforced at every password-set point).
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# CORS: allow everything in local dev; in production restrict to the origins
# listed in CORS_ALLOWED_ORIGINS (comma-separated, e.g. https://sairamfeeds.in).
_cors_origins = [o.strip() for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()]
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = _cors_origins
    # CSRF trusted origins mirror the allowed CORS origins in production.
    CSRF_TRUSTED_ORIGINS = _cors_origins

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Uploaded documents (farmer agreements, KYC, vet certificates, etc.)
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# Cap uploads at 10 MB; documents are scans/PDFs, not large media.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Production security hardening (active only when DEBUG is False) ───
# SECURE_SSL_REDIRECT and cookie-secure assume the app is served over HTTPS.
# Set DISABLE_HTTPS=True in the environment only for a non-HTTPS internal
# deployment where you knowingly accept the risk.
if not DEBUG:
    _https = os.environ.get('DISABLE_HTTPS', 'False').lower() != 'true'
    SESSION_COOKIE_SECURE = _https
    CSRF_COOKIE_SECURE = _https
    SECURE_SSL_REDIRECT = _https
    # Behind nginx/other proxy terminating TLS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000 if _https else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _https
    SECURE_HSTS_PRELOAD = _https
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
