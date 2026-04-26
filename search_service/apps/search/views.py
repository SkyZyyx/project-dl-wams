from uuid import uuid4

from django.conf import settings
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import IndexRequestSerializer, SearchMatchSerializer, SearchRequestSerializer
from .services.embedder import get_embedder
from .services.model_registry import get_default_model_id, get_model_spec
from .services.preprocess import preprocess_image_bytes
from .services.qdrant import (
    delete_by_product_id,
    is_top_hit_below_ood_threshold,
    search_vectors,
    upsert_vector,
)
from .services.quality import validate_image_quality
from .services.visualization import generate_gradcam_overlay


class IndexView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        spec = get_model_spec(get_default_model_id())
        print(
            f"[MODEL_TRACE] index model={spec.model_id} "
            f"collection={spec.collection_name} "
            f"checkpoint={spec.checkpoint_path or '<none>'}"
        )
        serializer = IndexRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        image_bytes = image_file.read()
        ok, reason = validate_image_quality(image_bytes)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        product_id = serializer.validated_data["product_id"]
        product_image_id = serializer.validated_data.get("product_image_id")
        vector_id = product_image_id if product_image_id is not None else str(uuid4())
        embedding_bytes = preprocess_image_bytes(image_bytes)
        vector = get_embedder().embed(embedding_bytes)
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
        spec = get_model_spec(get_default_model_id())
        print(
            f"[MODEL_TRACE] search model={spec.model_id} "
            f"collection={spec.collection_name} "
            f"checkpoint={spec.checkpoint_path or '<none>'}"
        )
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data["image"]
        image_bytes = image_file.read()
        ok, reason = validate_image_quality(image_bytes)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        embedding_bytes = preprocess_image_bytes(image_bytes)
        vector = get_embedder().embed(embedding_bytes)

        results = search_vectors(
            vector=vector,
            limit=serializer.validated_data["limit"],
            score_threshold=serializer.validated_data.get("score_threshold"),
        )

        # Keep a conservative floor for weak nearest-neighbor hits.
        if is_top_hit_below_ood_threshold(results=results):
            return Response({"detail": "no similar products found", "matches": []}, status=status.HTTP_200_OK)

        # Filter out individual results below the minimum score floor.
        min_score = getattr(settings, "SEARCH_MIN_SCORE_THRESHOLD", 0.80)
        results = [r for r in results if float(getattr(r, "score", 0)) >= min_score]

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
        delete_by_product_id(product_id)
        return Response({"status": "deleted", "product_id": product_id}, status=status.HTTP_200_OK)


class GradCamView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image_file = request.FILES.get("image")
        if image_file is None:
            return Response({"image": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = image_file.read()
        ok, reason = validate_image_quality(image_bytes)
        if not ok:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)

        try:
            return Response(generate_gradcam_overlay(image_bytes))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
