"""Django settings for the MarketDebater frontend."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

# DEBUG defaults to OFF. Set DJANGO_DEBUG=1 in your local .env for development.
# A "default-on" DEBUG leaks stack traces, settings, and env values on any 500.
DEBUG = os.getenv("DJANGO_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}

# SECRET_KEY must be set explicitly when DEBUG is off. The fallback below is a
# publicly-known string usable only for local development — never for prod.
_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()
if not _SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off. Generate one with:\n"
            "  python -c \"from django.core.management.utils import get_random_secret_key; "
            "print(get_random_secret_key())\""
        )
    _SECRET_KEY = "django-insecure-marketdebater-dev-key"  # dev-only fallback
SECRET_KEY = _SECRET_KEY

ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves Django static files directly from gunicorn in prod.
    # Must sit right after SecurityMiddleware per WhiteNoise docs.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "marketdebater_frontend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "marketdebater_frontend.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production security settings.
# NOTE: Django has no built-in Content Security Policy setting. The earlier
# SECURE_CONTENT_SECURITY_POLICY key was silently ignored — install django-csp
# if you need CSP enforcement.
# NOTE: SECURE_BROWSER_XSS_FILTER was removed in Django 6.0; the X-XSS-Protection
# header it set is also deprecated by modern browsers (Chrome dropped it in 2019).
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"

# Always-trusted origins for local dev + common managed hosts.
# Add deployment-specific origins (e.g. https://yourapp.up.railway.app, custom
# domains) via the DJANGO_CSRF_TRUSTED_ORIGINS env var as a comma-separated list.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "https://*.pythonanywhere.com",
    "https://*.up.railway.app",
] + [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
