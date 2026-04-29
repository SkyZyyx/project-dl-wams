import logging

from django.db import connection
from django.views.generic import TemplateView
from rest_framework import permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import ProductOwnerPermission, SellerWritePermission
from .services.search_hydration import hydrate_search_matches
from .services.search_proxy import SearchServiceError, delete_product_index, proxy_search_image_with_threshold

from .services.catalog_proxy import CatalogServiceError, fetch_products, fetch_products_by_ids, proxy_catalog_write


logger = logging.getLogger(__name__)


def _catalog_error_response(exc: CatalogServiceError):
    payload = exc.payload if exc.payload is not None else {"detail": exc.detail}
    return Response(payload, status=exc.status_code)


@api_view(["GET"])
def health(request):
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False

    payload = {"status": "ok" if db_ok else "degraded", "service": "main_service", "db": db_ok}
    http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)


class SearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response({"image": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            score_threshold = request.data.get("score_threshold")
            limit = request.data.get("limit")
            if score_threshold in (None, ""):
                threshold_value = None
            else:
                threshold_value = float(score_threshold)
            if limit in (None, ""):
                limit_value = 10
            else:
                limit_value = max(1, min(int(limit), 10))
            search_payload = proxy_search_image_with_threshold(
                image_name=image.name,
                image_bytes=image.read(),
                content_type=getattr(image, "content_type", "application/octet-stream"),
                score_threshold=threshold_value,
                limit=limit_value,
            )
        except ValueError:
            return Response({"detail": "Enter valid score_threshold and limit values."}, status=status.HTTP_400_BAD_REQUEST)
        except SearchServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        def prune_missing_products(product_ids: list[int]) -> None:
            for product_id in product_ids:
                try:
                    delete_product_index(product_id)
                except SearchServiceError:
                    logger.warning("failed to prune stale qdrant vectors for product_id=%s", product_id)

        try:
            matches, detail = hydrate_search_matches(
                search_payload,
                fetch_products_by_ids=fetch_products_by_ids,
                max_results=10,
                on_missing_products=prune_missing_products,
            )
        except CatalogServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        response_data = {"matches": matches}
        if detail:
            response_data["detail"] = detail
        return Response(response_data)

class ProductListView(APIView):
    permission_classes = [SellerWritePermission]

    def get(self, request):
        ids = request.query_params.get("ids")
        product_ids = None
        if ids:
            product_ids = [int(value) for value in ids.split(",") if value.strip().isdigit()]

        try:
            return Response(fetch_products(product_ids))
        except CatalogServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        authorization = request.headers.get("Authorization")
        try:
            status_code, payload = proxy_catalog_write(
                method="POST",
                path="/api/products/",
                body=request.body,
                content_type=request.META.get("CONTENT_TYPE", "application/json"),
                authorization=authorization,
            )
            return Response(payload, status=status_code)
        except CatalogServiceError as exc:
            return _catalog_error_response(exc)


class ProductCategoryView(APIView):
    permission_classes = [SellerWritePermission]

    def get(self, request):
        try:
            status_code, payload = proxy_catalog_write(
                method="GET",
                path="/api/categories/",
                body=b"",
                content_type="application/json",
                authorization=request.headers.get("Authorization"),
            )
            return Response(payload, status=status_code)
        except CatalogServiceError as exc:
            return _catalog_error_response(exc)

    def post(self, request):
        try:
            status_code, payload = proxy_catalog_write(
                method="POST",
                path="/api/categories/",
                body=request.body,
                content_type=request.META.get("CONTENT_TYPE", "application/json"),
                authorization=request.headers.get("Authorization"),
            )
            return Response(payload, status=status_code)
        except CatalogServiceError as exc:
            return _catalog_error_response(exc)


class ProductImageUploadView(APIView):
    permission_classes = [SellerWritePermission]

    def post(self, request, pk: int):
        try:
            status_code, payload = proxy_catalog_write(
                method="POST",
                path=f"/api/products/{pk}/images/",
                body=request.body,
                content_type=request.META.get("CONTENT_TYPE", "multipart/form-data"),
                authorization=request.headers.get("Authorization"),
            )
            return Response(payload, status=status_code)
        except CatalogServiceError as exc:
            return _catalog_error_response(exc)


class DemoPageView(TemplateView):
    template_name = "core/demo.html"
