from functools import lru_cache
import json
import math
from types import SimpleNamespace
from urllib import request as urllib_request

from django.conf import settings

from .model_registry import get_model_spec


_COLLECTION_MEAN_CACHE: dict[str, list[float] | None] = {}


@lru_cache(maxsize=1)
def get_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.QDRANT_URL)


@lru_cache(maxsize=1)
def get_models():
    from qdrant_client.http import models as qmodels

    return qmodels


def _resolve_spec(model_id: str | None = None):
    return get_model_spec(model_id)


def _cache_key(model_id: str | None = None) -> str:
    return _resolve_spec(model_id).model_id


def get_search_thresholds(model_id: str | None = None) -> dict[str, float]:
    spec = _resolve_spec(model_id)
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


def _collection_name(model_id: str | None = None) -> str:
    return _resolve_spec(model_id).collection_name


def _vector_size(model_id: str | None = None) -> int:
    return _resolve_spec(model_id).vector_size


def clear_collection_mean_vector_cache(model_id: str | None = None) -> None:
    _COLLECTION_MEAN_CACHE.pop(_cache_key(model_id), None)


def ensure_collection(model_id: str | None = None) -> None:
    client = get_client()
    collection_name = _collection_name(model_id)
    if hasattr(client, "collection_exists"):
        exists = client.collection_exists(collection_name)
    else:
        exists = collection_name in {collection.name for collection in client.get_collections().collections}

    if exists:
        return

    qmodels = get_models()
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=_vector_size(model_id), distance=qmodels.Distance.COSINE),
    )


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return list(vector)
    return [value / norm for value in vector]


def get_collection_mean_vector(model_id: str | None = None) -> list[float] | None:
    cache_key = _cache_key(model_id)
    if cache_key in _COLLECTION_MEAN_CACHE:
        return _COLLECTION_MEAN_CACHE[cache_key]

    ensure_collection(model_id)
    client = get_client()
    collection_name = _collection_name(model_id)
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
        return None

    mean_vector = _normalize_vector([value / count for value in total])
    _COLLECTION_MEAN_CACHE[cache_key] = mean_vector
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


def upsert_vector(*, vector_id: int | str, vector: list[float], payload: dict, model_id: str | None = None) -> None:
    ensure_collection(model_id)
    qmodels = get_models()
    get_client().upsert(
        collection_name=_collection_name(model_id),
        points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
    )
    clear_collection_mean_vector_cache(model_id)


def search_vectors(*, vector: list[float], limit: int = 5, score_threshold: float | None = None, model_id: str | None = None):
    ensure_collection(model_id)
    payload = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_vectors": False,
    }
    if score_threshold is not None:
        payload["score_threshold"] = score_threshold

    request = urllib_request.Request(
        f"{settings.QDRANT_URL}/collections/{_collection_name(model_id)}/points/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib_request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    return [
        SimpleNamespace(id=item.get("id"), score=item.get("score"), payload=item.get("payload") or {})
        for item in data.get("result", [])
    ]


def delete_by_product_id(product_id: int, model_id: str | None = None) -> int:
    ensure_collection(model_id)
    qmodels = get_models()
    get_client().delete(
        collection_name=_collection_name(model_id),
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="product_id", match=qmodels.MatchValue(value=product_id))]
            )
        ),
    )
    clear_collection_mean_vector_cache(model_id)
    return 1
