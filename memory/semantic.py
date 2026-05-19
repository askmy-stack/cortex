"""Semantic memory helpers — optional Qdrant vectors for decisions."""

from __future__ import annotations

import os
import uuid
from typing import Any

import structlog

from shared.models import DecisionEvent

log = structlog.get_logger(__name__)

_COLLECTION = os.environ.get("QDRANT_COLLECTION", "cortex_decisions")
_model: Any | None = None


def semantic_enabled() -> bool:
    """Return True when Qdrant semantic indexing is enabled."""
    return os.environ.get("CORTEX_SEMANTIC_ENABLED", "false").lower() in {"1", "true", "yes"}


def _get_embedder() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        model_name = os.environ.get("CORTEX_EMBED_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(model_name)
    return _model


def _client() -> Any | None:
    if not semantic_enabled():
        return None
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return None

    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def _embed(text: str) -> list[float]:
    model = _get_embedder()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def upsert_decision_vector(decision: DecisionEvent) -> None:
    """Upsert decision embedding into Qdrant when semantic search is enabled."""
    client = _client()
    if client is None:
        return
    try:
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ImportError:
        return

    try:
        vector = _embed(decision.content)
    except Exception as exc:
        log.warning("semantic.embed_failed", error=str(exc), event_id=decision.event_id)
        return

    dim = len(vector)
    if not client.collection_exists(_COLLECTION):
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, decision.event_id))
    point = PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "event_id": decision.event_id,
            "workspace_id": decision.workspace_id,
            "content": decision.content,
        },
    )
    client.upsert(collection_name=_COLLECTION, points=[point])
    log.info("semantic.upsert", event_id=decision.event_id, collection=_COLLECTION)


def search_decision_ids(query: str, workspace_id: str, limit: int) -> list[str]:
    """Return decision IDs from Qdrant similarity search."""
    client = _client()
    if client is None:
        return []
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
    except ImportError:
        return []

    try:
        vector = _embed(query)
    except Exception as exc:
        log.warning("semantic.search_embed_failed", error=str(exc))
        return []

    hits = client.search(
        collection_name=_COLLECTION,
        query_vector=vector,
        limit=limit,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="workspace_id",
                    match=MatchValue(value=workspace_id),
                )
            ],
        ),
    )
    return [str(hit.payload.get("event_id", "")) for hit in hits if hit.payload]
