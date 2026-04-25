from django.db import connection
from django.views.generic import TemplateView
from rest_framework import permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.search_proxy import SearchServiceError, proxy_gradcam_image, proxy_search_image_with_threshold

from .services.catalog_proxy import CatalogServiceError, fetch_products, fetch_products_by_ids


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
            if score_threshold in (None, ""):
                threshold_value = None
            else:
                threshold_value = float(score_threshold)
            search_payload = proxy_search_image_with_threshold(
                image_name=image.name,
                image_bytes=image.read(),
                content_type=getattr(image, "content_type", "application/octet-stream"),
                score_threshold=threshold_value,
            )
        except ValueError:
            return Response({"score_threshold": ["Enter a valid number."]}, status=status.HTTP_400_BAD_REQUEST)
        except SearchServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        matches = search_payload.get("matches", [])
        if not matches:
            response_data = {"matches": []}
            detail = search_payload.get("detail")
            if detail:
                response_data["detail"] = detail
            return Response(response_data)

        product_ids = []
        best_matches = {}
        for match in matches:
            product_id = match.get("product_id")
            if product_id is None:
                continue
            score = float(match.get("score") or 0)
            current = best_matches.get(product_id)
            if current is None or score > current["score"]:
                best_matches[product_id] = {
                    "product_id": product_id,
                    "product_image_id": match.get("product_image_id"),
                    "qdrant_id": match.get("qdrant_id"),
                    "score": score,
                }
            if product_id not in product_ids:
                product_ids.append(product_id)

        try:
            products_payload = fetch_products_by_ids(product_ids)
        except CatalogServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        products_by_id = {int(product["id"]): product for product in products_payload if product.get("id") is not None}

        hydrated_matches = []
        for product_id in product_ids:
            product = products_by_id.get(product_id)
            match = best_matches.get(product_id)
            if product is None or match is None:
                continue

            product_data = dict(product)
            product_data.update(
                {
                    "score": match["score"],
                    "product_image_id": match["product_image_id"],
                    "qdrant_id": match["qdrant_id"],
                }
            )
            hydrated_matches.append(product_data)

        hydrated_matches.sort(key=lambda item: item.get("score", 0), reverse=True)
        return Response({"matches": hydrated_matches})


class ProductListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        ids = request.query_params.get("ids")
        product_ids = None
        if ids:
            product_ids = [int(value) for value in ids.split(",") if value.strip().isdigit()]

        try:
            return Response(fetch_products(product_ids))
        except CatalogServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class GradCamView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response({"image": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = proxy_gradcam_image(
                image_name=image.name,
                image_bytes=image.read(),
                content_type=getattr(image, "content_type", "application/octet-stream"),
            )
        except SearchServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(payload)


class DemoPageView(TemplateView):
    template_name = "core/demo.html"
