from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


def _db_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _qdrant_ready() -> bool:
    try:
        with urllib_request.urlopen(f"{settings.QDRANT_URL.rstrip('/')}/collections", timeout=2) as response:
            return response.status == 200
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError):
        return False


@api_view(["GET"])
def health(request):
    payload = {"status": "ok", "service": "search_service"}
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
def ready(request):
    db_ok = _db_ready()
    qdrant_ok = _qdrant_ready()
    ready = db_ok and qdrant_ok
    payload = {
        "status": "ok" if ready else "degraded",
        "service": "search_service",
        "db": db_ok,
        "qdrant": qdrant_ok,
        "qdrant_url": settings.QDRANT_URL,
    }
    http_status = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)
