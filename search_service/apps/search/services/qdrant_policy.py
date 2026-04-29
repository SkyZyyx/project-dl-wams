import math
import logging
from time import perf_counter

from django.conf import settings

from .model_registry import get_model_spec
from .qdrant import ensure_collection, get_client


logger = logging.getLogger(__name__)


_COLLECTION_MEAN_CACHE: dict[str, list[float] | None] = {}


def _cache_key(model_id: str | None = None) -> str:
    return get_model_spec(model_id).model_id


def get_search_thresholds(model_id: str | None = None) -> dict[str, float]:
    spec = get_model_spec(model_id)
    thresholds = {
        "min_score": 0.45,
        "ood_top_score": 0.32,
        "ood_cosine": 0.20,
    }

    if spec.family == "clip":
        thresholds.update(
            {
                "min_score": 0.42,
                "ood_top_score": 0.30,
                "ood_cosine": 0.18,
            }
        )

    overrides = getattr(settings, "SEARCH_THRESHOLD_OVERRIDES", {})
    if isinstance(overrides, dict):
        family_overrides = overrides.get(spec.family, {})
        model_overrides = overrides.get(spec.model_id, {})
        if isinstance(family_overrides, dict):
            thresholds.update({key: float(value) for key, value in family_overrides.items() if key in thresholds})
        if isinstance(model_overrides, dict):
            thresholds.update({key: float(value) for key, value in model_overrides.items() if key in thresholds})

    return thresholds


def clear_collection_mean_vector_cache(model_id: str | None = None) -> None:
    _COLLECTION_MEAN_CACHE.pop(_cache_key(model_id), None)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return list(vector)
    return [value / norm for value in vector]


def get_collection_mean_vector(model_id: str | None = None) -> list[float] | None:
    cache_key = _cache_key(model_id)
    if cache_key in _COLLECTION_MEAN_CACHE:
        return _COLLECTION_MEAN_CACHE[cache_key]

    started_at = perf_counter()
    ensure_collection(model_id)
    client = get_client()
    collection_name = get_model_spec(model_id).collection_name
    total: list[float] | None = None
    count = 0
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=getattr(settings, "SEARCH_COLLECTION_SCROLL_LIMIT", 256),
            offset=offset,
            with_vectors=True,
            with_payload=False,
        )

        if not points:
            break

        for point in points:
            vector = getattr(point, "vector", None)
            if isinstance(vector, dict):
                vector = next(iter(vector.values()), None)
            if not vector:
                continue

            if total is None:
                total = [0.0] * len(vector)

            if len(vector) != len(total):
                continue

            for index, value in enumerate(vector):
                total[index] += float(value)
            count += 1

        if offset is None:
            break

    if total is None or count == 0:
        _COLLECTION_MEAN_CACHE[cache_key] = None
        logger.info("mean_vector empty model=%s collection=%s elapsed_ms=%.1f", cache_key, collection_name, (perf_counter() - started_at) * 1000)
        return None

    mean_vector = _normalize_vector([value / count for value in total])
    _COLLECTION_MEAN_CACHE[cache_key] = mean_vector
    logger.info(
        "mean_vector computed model=%s collection=%s points=%s elapsed_ms=%.1f",
        cache_key,
        collection_name,
        count,
        (perf_counter() - started_at) * 1000,
    )
    return mean_vector


def is_query_vector_out_of_distribution(*, vector: list[float], model_id: str | None = None) -> bool:
    mean_vector = get_collection_mean_vector(model_id)
    if mean_vector is None:
        return False

    normalized_vector = _normalize_vector(vector)
    if len(normalized_vector) != len(mean_vector):
        return False

    cosine_similarity = sum(left * right for left, right in zip(normalized_vector, mean_vector))
    return cosine_similarity < get_search_thresholds(model_id)["ood_cosine"]


def is_top_hit_below_ood_threshold(*, results, model_id: str | None = None) -> bool:
    if not results:
        return True

    top_score = max(float(getattr(result, "score", 0.0)) for result in results)
    return top_score < get_search_thresholds(model_id)["ood_top_score"]
