import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-product-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _allowed_hosts(default_hosts: str, *extras: str) -> list[str]:
    hosts = [host.strip() for host in default_hosts.split(",") if host.strip()]
    for host in extras:
        if host and host not in hosts:
            hosts.append(host)
    return hosts


ALLOWED_HOSTS = _allowed_hosts(
    os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,productservice,nginx"),
    "testserver",
    "productservice",
    "searchservice",
    "mainservice",
    "userservice",
    "orderservice",
    "nginx",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.products.apps.ProductsConfig",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "postgres_products"),
        "USER": os.getenv("POSTGRES_USER", "wams"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "wams"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres_products"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))

SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://searchservice:8004")
SEARCH_SERVICE_HOST_HEADER = os.getenv("SEARCH_SERVICE_HOST_HEADER", "localhost")
SEARCH_SERVICE_TIMEOUT_SECONDS = float(os.getenv("SEARCH_SERVICE_TIMEOUT_SECONDS", "180"))
JWT_SIGNING_KEY = os.getenv("JWT_SIGNING_KEY", SECRET_KEY)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTStatelessUserAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "SIGNING_KEY": JWT_SIGNING_KEY,
}
