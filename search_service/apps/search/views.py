import logging

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import IndexRequestSerializer, SearchRequestSerializer
from .services.model_registry import get_default_model_id, get_model_spec
from .services.qdrant import delete_by_product_id
from .services import search_use_case


logger = logging.getLogger(__name__)


class IndexView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        spec = get_model_spec(get_default_model_id())
        serializer = IndexRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        logger.info(
            "index request model=%s collection=%s image=%s size=%s",
            spec.model_id,
            spec.collection_name,
            image_file.name,
            getattr(image_file, "size", None),
        )
        result = search_use_case.index_image(
            image_bytes=image_file.read(),
            image_name=image_file.name,
            product_id=serializer.validated_data["product_id"],
            product_image_id=serializer.validated_data.get("product_image_id"),
        )
        return Response(result.data, status=result.status_code)


class SearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        spec = get_model_spec(get_default_model_id())
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        logger.info(
            "search request model=%s collection=%s image=%s size=%s limit=%s threshold=%s",
            spec.model_id,
            spec.collection_name,
            image_file.name,
            getattr(image_file, "size", None),
            serializer.validated_data["limit"],
            serializer.validated_data.get("score_threshold"),
        )
        result = search_use_case.search_image(
            image_bytes=image_file.read(),
            limit=serializer.validated_data["limit"],
            score_threshold=serializer.validated_data.get("score_threshold"),
        )
        return Response(result.data, status=result.status_code)


class DeleteIndexView(APIView):
    def delete(self, request, product_id: int):
        delete_by_product_id(product_id)
        return Response({"status": "deleted", "product_id": product_id}, status=status.HTTP_200_OK)
