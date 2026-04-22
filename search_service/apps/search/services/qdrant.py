from functools import lru_cache
import json
import math
from types import SimpleNamespace
from urllib import request as urllib_request

from django.conf import settings


COLLECTION_NAME = "product_images"
VECTOR_SIZE = 768


@lru_cache(maxsize=1)
def get_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.QDRANT_URL)


@lru_cache(maxsize=1)
def get_models():
    from qdrant_client.http import models as qmodels

    return qmodels


def ensure_collection() -> None:
    client = get_client()
    if hasattr(client, "collection_exists"):
        exists = client.collection_exists(COLLECTION_NAME)
    else:
        exists = COLLECTION_NAME in {collection.name for collection in client.get_collections().collections}

    if exists:
        return

    qmodels = get_models()
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
    )


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return list(vector)
    return [value / norm for value in vector]


@lru_cache(maxsize=1)
def get_collection_mean_vector() -> list[float] | None:
    ensure_collection()
    client = get_client()
    total: list[float] | None = None
    count = 0
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
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
        return None

    return _normalize_vector([value / count for value in total])


def is_query_vector_out_of_distribution(*, vector: list[float]) -> bool:
    mean_vector = get_collection_mean_vector()
    if mean_vector is None:
        return False

    normalized_vector = _normalize_vector(vector)
    if len(normalized_vector) != len(mean_vector):
        return False

    cosine_similarity = sum(left * right for left, right in zip(normalized_vector, mean_vector))
    return cosine_similarity < getattr(settings, "SEARCH_OOD_COSINE_THRESHOLD", 0.35)


def is_top_hit_below_ood_threshold(*, results) -> bool:
    if not results:
        return True

    top_score = max(float(getattr(result, "score", 0.0)) for result in results)
    return top_score < getattr(settings, "SEARCH_OOD_TOP_SCORE_THRESHOLD", 0.45)


def upsert_vector(*, vector_id: int | str, vector: list[float], payload: dict) -> None:
    ensure_collection()
    qmodels = get_models()
    get_client().upsert(
        collection_name=COLLECTION_NAME,
        points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
    )
    get_collection_mean_vector.cache_clear()


def search_vectors(*, vector: list[float], limit: int = 5, score_threshold: float | None = None):
    ensure_collection()
    payload = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_vectors": False,
    }
    if score_threshold is not None:
        payload["score_threshold"] = score_threshold

    request = urllib_request.Request(
        f"{settings.QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib_request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    return [
        SimpleNamespace(id=item.get("id"), score=item.get("score"), payload=item.get("payload") or {})
        for item in data.get("result", [])
    ]


def delete_by_product_id(product_id: int) -> int:
    ensure_collection()
    qmodels = get_models()
    get_client().delete(
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="product_id", match=qmodels.MatchValue(value=product_id))]
            )
        ),
    )
    get_collection_mean_vector.cache_clear()
    return 1
