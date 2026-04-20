from uuid import uuid4

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import IndexRequestSerializer, SearchMatchSerializer, SearchRequestSerializer
from .services.embedder import DINOv2Embedder
from .services.qdrant import delete_by_product_id, search_vectors, upsert_vector
from .services.quality import validate_image_quality


class IndexView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = IndexRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        image_bytes = image_file.read()
        ok, reason = validate_image_quality(image_bytes)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        product_id = serializer.validated_data["product_id"]
        product_image_id = serializer.validated_data.get("product_image_id")
        vector_id = str(product_image_id or uuid4())
        vector = DINOv2Embedder().embed(image_bytes)
        upsert_vector(
            vector_id=vector_id,
            vector=vector,
            payload={
                "product_id": product_id,
                "product_image_id": product_image_id,
                "filename": image_file.name,
            },
        )
        return Response(
            {
                "status": "indexed",
                "qdrant_id": vector_id,
                "product_id": product_id,
                "product_image_id": product_image_id,
            },
            status=status.HTTP_201_CREATED,
        )


class SearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        image_bytes = image_file.read()
        ok, reason = validate_image_quality(image_bytes)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        vector = DINOv2Embedder().embed(image_bytes)
        results = search_vectors(
            vector=vector,
            limit=serializer.validated_data["limit"],
            score_threshold=serializer.validated_data.get("score_threshold"),
        )

        matches = []
        for result in results:
            payload = result.payload or {}
            matches.append(
                {
                    "product_id": payload.get("product_id"),
                    "product_image_id": payload.get("product_image_id"),
                    "qdrant_id": str(result.id),
                    "score": float(result.score),
                }
            )

        return Response({"matches": SearchMatchSerializer(matches, many=True).data})


class DeleteIndexView(APIView):
    def delete(self, request, product_id: int):
        removed = delete_by_product_id(product_id)
        if removed == 0:
            return Response({"status": "deleted", "product_id": product_id}, status=status.HTTP_200_OK)
        return Response({"status": "deleted", "product_id": product_id}, status=status.HTTP_200_OK)
