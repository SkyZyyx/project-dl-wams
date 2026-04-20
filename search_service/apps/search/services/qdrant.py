from functools import lru_cache

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


COLLECTION_NAME = "product_images"
VECTOR_SIZE = 768


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL)


def ensure_collection() -> None:
    client = get_client()
    collections = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
        )


def upsert_vector(*, vector_id: str, vector: list[float], payload: dict) -> None:
    ensure_collection()
    get_client().upsert(
        collection_name=COLLECTION_NAME,
        points=[qmodels.PointStruct(id=vector_id, vector=vector, payload=payload)],
    )


def search_vectors(*, vector: list[float], limit: int = 5, score_threshold: float | None = None):
    ensure_collection()
    return get_client().search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
        with_vectors=False,
    )


def delete_by_product_id(product_id: int) -> int:
    ensure_collection()
    get_client().delete(
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="product_id", match=qmodels.MatchValue(value=product_id))]
            )
        ),
    )
    return 1
