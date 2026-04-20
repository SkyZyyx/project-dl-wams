from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "search_service",
        "db": db_ok,
        "qdrant_url": settings.QDRANT_URL,
    }
    http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)
