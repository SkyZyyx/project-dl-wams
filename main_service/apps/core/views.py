from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from apps.products.services.search_proxy import SearchServiceError, proxy_search_image


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
    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response({"image": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            search_payload = proxy_search_image(
                image_name=image.name,
                image_bytes=image.read(),
                content_type=getattr(image, "content_type", "application/octet-stream"),
            )
        except SearchServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        matches = search_payload.get("matches", [])
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

        products = Product.objects.filter(id__in=product_ids).select_related("category").prefetch_related("images")
        products_by_id = {product.id: product for product in products}

        hydrated_matches = []
        for product_id in product_ids:
            product = products_by_id.get(product_id)
            match = best_matches.get(product_id)
            if product is None or match is None:
                continue

            product_data = ProductSerializer(product, context={"request": request}).data
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
