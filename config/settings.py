"""
Django settings for helpdesk project.

All configuration comes from environment variables, with defaults that work
for local development against the docker compose Postgres.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set SECRET_KEY, or DEBUG=1 for a local dev key.")
    SECRET_KEY = "django-insecure-dev-only"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],web")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Behind Railway's (or any) TLS-terminating proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Application definition

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'apps.tickets',
    'apps.knowledge_base',
    'apps.mock_helpdesk',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.tickets.context_processors.llm_mode',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database

DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get("DATABASE_URL", "postgres://helpdesk:helpdesk@localhost:5432/helpdesk"),
        conn_max_age=60,
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


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

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'tickets:list'
LOGOUT_REDIRECT_URL = 'login'


# Internationalization

LANGUAGE_CODE = 'uk'

TIME_ZONE = 'Europe/Kyiv'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
}


# Application settings

# Absolute base for links we hand out (Article links inside Drafts).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Demo Operator created at startup by `manage.py ensure_operator`.
OPERATOR_USERNAME = os.environ.get("OPERATOR_USERNAME", "operator")
OPERATOR_PASSWORD = os.environ.get("OPERATOR_PASSWORD", "operator")

# LLM. An empty key switches the adapter to stub mode (see ADR-0003 and the spec).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_STUB_MODE = not ANTHROPIC_API_KEY
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_RATE_LIMIT_PER_MINUTE = int(os.environ.get("LLM_RATE_LIMIT_PER_MINUTE", "60"))

# Worker.
WORKER_THREADS = int(os.environ.get("WORKER_THREADS", "30"))

# Helpdesk client.
HELPDESK_TIMEOUT_SECONDS = float(os.environ.get("HELPDESK_TIMEOUT_SECONDS", "10"))

# Where `simulate_webhooks` tells the Helpdesk to receive Replies (the mock
# Helpdesk), as reachable from the worker.
SIMULATOR_REPLY_BASE_URL = os.environ.get("SIMULATOR_REPLY_BASE_URL", PUBLIC_BASE_URL)

# Mock Helpdesk fault injection.
MOCK_HELPDESK_FAILURE_RATE = float(os.environ.get("MOCK_HELPDESK_FAILURE_RATE", "0.2"))
MOCK_HELPDESK_SLOW_RATE = float(os.environ.get("MOCK_HELPDESK_SLOW_RATE", "0.1"))
MOCK_HELPDESK_SLOW_SECONDS = float(os.environ.get("MOCK_HELPDESK_SLOW_SECONDS", "15"))
