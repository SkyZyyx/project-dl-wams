from __future__ import annotations

from dataclasses import dataclass

from .services.model_registry import get_default_model_id, get_model_spec
from .services.qdrant import ensure_collection, get_client
from .services.qdrant_policy import clear_collection_mean_vector_cache, get_search_thresholds


@dataclass(frozen=True)
class SearchOperationsState:
    model_id: str
    collection_name: str
    thresholds: dict[str, float]


def get_search_operations_state(model_id: str | None = None) -> SearchOperationsState:
    spec = get_model_spec(model_id or get_default_model_id())
    return SearchOperationsState(
        model_id=spec.model_id,
        collection_name=spec.collection_name,
        thresholds=get_search_thresholds(spec.model_id),
    )


def reset_active_collection(model_id: str | None = None) -> str:
    spec = get_model_spec(model_id or get_default_model_id())
    client = get_client()
    if hasattr(client, "collection_exists"):
        exists = client.collection_exists(spec.collection_name)
    else:
        exists = spec.collection_name in {collection.name for collection in client.get_collections().collections}

    if exists:
        client.delete_collection(spec.collection_name)

    ensure_collection(spec.model_id)
    clear_collection_mean_vector_cache(spec.model_id)
    return spec.collection_name


def clear_active_cache(model_id: str | None = None) -> str:
    spec = get_model_spec(model_id or get_default_model_id())
    clear_collection_mean_vector_cache(spec.model_id)
    return spec.collection_name
