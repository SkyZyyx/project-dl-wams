from dataclasses import dataclass
import logging
from time import perf_counter
from uuid import uuid4

from rest_framework import status

from .embedder import get_embedder
from .model_registry import get_default_model_id
from .preprocess import preprocess_image_bytes
from .quality import validate_image_quality
from .qdrant import search_vectors, upsert_vector
from .qdrant_policy import (
    get_search_thresholds,
    is_query_vector_out_of_distribution,
    is_top_hit_below_ood_threshold,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UseCaseResponse:
    data: dict
    status_code: int


def _resolve_model_id(model_id: str | None = None) -> str:
    return model_id or get_default_model_id()


def _shape_match(result) -> dict:
    payload = result.payload or {}
    return {
        "product_id": payload.get("product_id"),
        "product_image_id": payload.get("product_image_id"),
        "qdrant_id": str(result.id),
        "score": float(result.score),
    }


def _shape_matches(results) -> list[dict]:
    return [_shape_match(result) for result in results]


def _filter_results(results, min_score: float):
    filtered_results = [result for result in results if float(getattr(result, "score", 0)) >= min_score]
    return filtered_results if filtered_results else results[:5]


def index_image(*, image_bytes: bytes, image_name: str, product_id: int, product_image_id: int | None = None, model_id: str | None = None) -> UseCaseResponse:
    model_id = _resolve_model_id(model_id)
    started_at = perf_counter()
    ok, reason = validate_image_quality(image_bytes)
    if not ok:
        logger.info("index rejected model=%s product_id=%s reason=%s", model_id, product_id, reason)
        return UseCaseResponse({"detail": reason}, status.HTTP_400_BAD_REQUEST)

    preprocess_started = perf_counter()
    embedding_bytes = preprocess_image_bytes(image_bytes)
    preprocess_ms = (perf_counter() - preprocess_started) * 1000
    embed_started = perf_counter()
    vector = get_embedder(model_id).embed(embedding_bytes)
    embed_ms = (perf_counter() - embed_started) * 1000
    vector_id = product_image_id if product_image_id is not None else str(uuid4())
    upsert_started = perf_counter()
    upsert_vector(
        vector_id=vector_id,
        vector=vector,
        payload={"product_id": product_id, "product_image_id": product_image_id, "filename": image_name},
        model_id=model_id,
    )
    total_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "index completed model=%s product_id=%s product_image_id=%s vector_id=%s preprocess_ms=%.1f embed_ms=%.1f upsert_ms=%.1f total_ms=%.1f",
        model_id,
        product_id,
        product_image_id,
        vector_id,
        preprocess_ms,
        embed_ms,
        (perf_counter() - upsert_started) * 1000,
        total_ms,
    )
    return UseCaseResponse(
        {
            "status": "indexed",
            "qdrant_id": vector_id,
            "product_id": product_id,
            "product_image_id": product_image_id,
        },
        status.HTTP_201_CREATED,
    )


def search_image(*, image_bytes: bytes, limit: int = 10, score_threshold: float | None = None, model_id: str | None = None) -> UseCaseResponse:
    model_id = _resolve_model_id(model_id)
    thresholds = get_search_thresholds(model_id)
    started_at = perf_counter()

    ok, reason = validate_image_quality(image_bytes)
    if not ok:
        logger.info("search rejected model=%s reason=%s", model_id, reason)
        return UseCaseResponse({"detail": reason}, status.HTTP_400_BAD_REQUEST)

    preprocess_started = perf_counter()
    embedding_bytes = preprocess_image_bytes(image_bytes)
    preprocess_ms = (perf_counter() - preprocess_started) * 1000
    embed_started = perf_counter()
    vector = get_embedder(model_id).embed(embedding_bytes)
    embed_ms = (perf_counter() - embed_started) * 1000

    ood_started = perf_counter()
    if is_query_vector_out_of_distribution(vector=vector, model_id=model_id):
        logger.info(
            "search ood model=%s limit=%s threshold=%s preprocess_ms=%.1f embed_ms=%.1f ood_ms=%.1f total_ms=%.1f",
            model_id,
            limit,
            score_threshold,
            preprocess_ms,
            embed_ms,
            (perf_counter() - ood_started) * 1000,
            (perf_counter() - started_at) * 1000,
        )
        return UseCaseResponse({"detail": "no similar products found", "matches": []}, status.HTTP_200_OK)

    search_started = perf_counter()
    results = search_vectors(vector=vector, limit=limit, score_threshold=score_threshold, model_id=model_id)
    search_ms = (perf_counter() - search_started) * 1000
    if is_top_hit_below_ood_threshold(results=results, model_id=model_id):
        logger.info(
            "search low_confidence model=%s limit=%s threshold=%s results=%s preprocess_ms=%.1f embed_ms=%.1f search_ms=%.1f total_ms=%.1f",
            model_id,
            limit,
            score_threshold,
            len(results),
            preprocess_ms,
            embed_ms,
            search_ms,
            (perf_counter() - started_at) * 1000,
        )
        return UseCaseResponse({"detail": "no similar products found", "matches": []}, status.HTTP_200_OK)

    shape_started = perf_counter()
    filtered_results = _filter_results(results, thresholds["min_score"])
    matches = _shape_matches(filtered_results)
    logger.info(
        "search completed model=%s limit=%s threshold=%s results=%s matches=%s preprocess_ms=%.1f embed_ms=%.1f search_ms=%.1f shape_ms=%.1f total_ms=%.1f",
        model_id,
        limit,
        score_threshold,
        len(results),
        len(matches),
        preprocess_ms,
        embed_ms,
        search_ms,
        (perf_counter() - shape_started) * 1000,
        (perf_counter() - started_at) * 1000,
    )
    return UseCaseResponse({"matches": matches}, status.HTTP_200_OK)
