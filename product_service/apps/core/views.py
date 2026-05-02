from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


def _db_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


@api_view(["GET"])
def health(request):
    payload = {"status": "ok", "service": "product_service"}
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
def ready(request):
    db_ok = _db_ready()
    payload = {"status": "ok" if db_ok else "degraded", "service": "product_service", "db": db_ok}
    http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)
