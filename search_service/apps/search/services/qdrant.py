from functools import lru_cache
import json
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


def upsert_vector(*, vector_id: int | str, vector: list[float], payload: dict) -> None:
    ensure_collection()
    qmodels = get_models()
    get_client().upsert(
        collection_name=COLLECTION_NAME,
        points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
    )


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
    return 1
