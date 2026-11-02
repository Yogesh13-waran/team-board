"""
Django settings for the TeamBoard project.

================================================================================
ARCHITECTURAL OVERVIEW & INTERVIEW PERSPECTIVE
================================================================================
1. The 12-Factor App Principle (Config in Environment):
   - Never hardcode secrets (SECRET_KEY, DB credentials) into source control.
   - We use `python-dotenv` to inject environment variables from a local `.env` file
     during development and production container orchestrations (Docker / Kubernetes).

2. Global-by-Default Security Policy:
   - In modern API architectures (Zero Trust), every endpoint is locked down by default.
   - We register `IsAuthenticated` as the default permission and `JWTAuthentication`
     as the default authentication mechanism.
   - Public endpoints (like registration and login) must explicitly opt out by setting:
     `authentication_classes = []` and `permission_classes = []`.
   - Why? If a developer creates a new endpoint and forgets to add permissions, it is
     secure by default rather than accidentally exposed.

3. Stateless JWT (JSON Web Tokens):
   - Traditional session auth requires server-side storage (e.g. database, Redis).
   - SimpleJWT creates signed cryptographic tokens (header.payload.signature).
   - Verification only requires the server's SECRET_KEY (symmetric HMAC-SHA256),
     enabling horizontal scaling without distributed session caches.
================================================================================
"""

import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file at the project root
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'insecure-default-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Allowed hosts parsed from comma-separated env string
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0,testserver').split(',')
    if host.strip()
]
if 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-Party Libraries
    'rest_framework',
    'rest_framework_simplejwt',

    # Local Domain Apps
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'teamboard.urls'

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

WSGI_APPLICATION = 'teamboard.wsgi.application'

# ==============================================================================
# Database Configuration (PostgreSQL via Docker)
# ==============================================================================
# In production and containerized environments, database credentials must be
# read from environment variables. Django's postgres backend leverages the
# modern `psycopg` (v3) driver installed in Python 3.14.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'teamboard_db'),
        'USER': os.getenv('DB_USER', 'teamboard_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'teamboard_secure_pass_2026'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# Django REST Framework (DRF) Configuration
# ==============================================================================
# As specified in Step 2:
# Global default is IsAuthenticated with JWTAuthentication.
# Public endpoints must explicitly declare authentication_classes = []
# and permission_classes = [].
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Return JSON by default, avoiding HTML renderer in pure API testing
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# ==============================================================================
# SimpleJWT Configuration
# ==============================================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', 60))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS', 1))
    ),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}
