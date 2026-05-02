import json
from types import SimpleNamespace
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings

from .model_registry import get_model_spec


from functools import lru_cache


class QdrantServiceError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.QDRANT_URL, timeout=getattr(settings, "QDRANT_HTTP_TIMEOUT", 5))


@lru_cache(maxsize=1)
def get_models():
    from qdrant_client.http import models as qmodels

    return qmodels


def _collection_name(model_id: str | None = None) -> str:
    return get_model_spec(model_id).collection_name


def _vector_size(model_id: str | None = None) -> int:
    return get_model_spec(model_id).vector_size


def ensure_collection(model_id: str | None = None) -> None:
    try:
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
    except Exception as exc:
        if isinstance(exc, QdrantServiceError):
            raise
        raise QdrantServiceError("qdrant collection unavailable") from exc


def upsert_vector(*, vector_id: int | str, vector: list[float], payload: dict, model_id: str | None = None) -> None:
    ensure_collection(model_id)
    qmodels = get_models()
    try:
        get_client().upsert(
            collection_name=_collection_name(model_id),
            points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
        )
    except Exception as exc:
        raise QdrantServiceError("qdrant upsert unavailable") from exc
    from .qdrant_policy import clear_collection_mean_vector_cache

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
        f"{settings.QDRANT_URL.rstrip('/')}/collections/{_collection_name(model_id)}/points/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(request, timeout=getattr(settings, "QDRANT_HTTP_TIMEOUT", 5)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, urllib_error.URLError, urllib_error.HTTPError) as exc:
        raise QdrantServiceError("qdrant search unavailable") from exc

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
    from .qdrant_policy import clear_collection_mean_vector_cache

    clear_collection_mean_vector_cache(model_id)
    return 1
