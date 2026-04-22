import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-search-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,search_service,nginx"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.search",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("DJANGO_USE_SQLITE", "0") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "wams"),
            "USER": os.getenv("POSTGRES_USER", "wams"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "wams"),
            "HOST": os.getenv("POSTGRES_HOST", "postgres"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://main_service:8000")
SEARCH_OOD_COSINE_THRESHOLD = float(os.getenv("SEARCH_OOD_COSINE_THRESHOLD", "0.35"))
SEARCH_OOD_TOP_SCORE_THRESHOLD = float(os.getenv("SEARCH_OOD_TOP_SCORE_THRESHOLD", "0.45"))
SEARCH_COLLECTION_SCROLL_LIMIT = int(os.getenv("SEARCH_COLLECTION_SCROLL_LIMIT", "256"))

SEARCH_PREPROCESS_ENABLED = os.getenv("SEARCH_PREPROCESS_ENABLED", "1") == "1"
SEARCH_PREPROCESS_USE_REMBG = os.getenv("SEARCH_PREPROCESS_USE_REMBG", "0") == "1"
SEARCH_PREPROCESS_PAD = int(os.getenv("SEARCH_PREPROCESS_PAD", "12"))
SEARCH_PREPROCESS_THRESHOLD = int(os.getenv("SEARCH_PREPROCESS_THRESHOLD", "24"))
SEARCH_PREPROCESS_MIN_AREA_RATIO = float(os.getenv("SEARCH_PREPROCESS_MIN_AREA_RATIO", "0.01"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
