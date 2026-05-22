from __future__ import annotations
import math
import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Dict, Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, ScoredPoint, FilterSelector,
)
from loguru import logger
from app.core.config import get_settings

settings = get_settings()
TOKEN_RE = re.compile(r"[a-zA-Z0-9]{3,}")


@dataclass
class RetrievedChunk:
    id: str
    payload: Dict[str, Any]
    vector_score: float | None = None
    lexical_score: float | None = None
    hybrid_score: float | None = None
    retrieval_method: str = "vector"
    score: float = 0.0
    retrieval_methods: set[str] = field(default_factory=set)


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


class QdrantService:
    def __init__(self) -> None:
        if settings.qdrant_path:
            self.client = AsyncQdrantClient(path=settings.qdrant_path)
        elif settings.qdrant_api_key:
            self.client = AsyncQdrantClient(url=f"https://{settings.qdrant_host}", api_key=settings.qdrant_api_key)
        else:
            self.client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    async def ensure_collection(self) -> None:
        exists = await self.client.collection_exists(settings.qdrant_collection_name)
        if not exists:
            await self.client.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config=VectorParams(size=settings.qdrant_vector_size, distance=Distance.COSINE),
            )
            logger.info(f"Created collection: {settings.qdrant_collection_name}")

    async def upsert_chunks(self, doc_id: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]], metadata: Dict[str, Any]) -> int:
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "text": chunk.get("text", ""),
                    "page_number": chunk.get("page_number"),
                    "filename": metadata.get("filename", ""),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "conversation_id": metadata.get("conversation_id", ""),
                    "namespace": settings.qdrant_namespace,
                },
            )
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
        await self.client.upsert(collection_name=settings.qdrant_collection_name, points=points)
        logger.info(f"Upserted {len(points)} chunks for doc {doc_id}")
        return len(points)

    def _scope_filter(self, conversation_id: str | None = None) -> Filter:
        must = [FieldCondition(key="namespace", match=MatchValue(value=settings.qdrant_namespace))]
        if conversation_id:
            must.append(FieldCondition(key="conversation_id", match=MatchValue(value=conversation_id)))
        return Filter(must=must)

    async def search(self, query_vector: List[float], top_k: int = 20, conversation_id: str | None = None) -> List[ScoredPoint]:
        return await self.client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=self._scope_filter(conversation_id),
        )

    async def vector_search(self, query_vector: List[float], top_k: int = 20, conversation_id: str | None = None) -> List[RetrievedChunk]:
        points = await self.search(query_vector=query_vector, top_k=top_k, conversation_id=conversation_id)
        return [
            RetrievedChunk(
                id=str(point.id),
                payload=dict(point.payload or {}),
                vector_score=float(point.score),
                retrieval_method="vector",
                score=float(point.score),
                retrieval_methods={"vector"},
            )
            for point in points
        ]

    async def lexical_search(self, query: str, top_k: int = 20, conversation_id: str | None = None) -> List[RetrievedChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_counts: dict[str, int] = {}
        for token in query_tokens:
            query_counts[token] = query_counts.get(token, 0) + 1

        scored: list[RetrievedChunk] = []
        offset = None
        while True:
            points, offset = await self.client.scroll(
                collection_name=settings.qdrant_collection_name,
                scroll_filter=self._scope_filter(conversation_id),
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            for point in points:
                payload = dict(point.payload or {})
                text_tokens = _tokenize(payload.get("text", ""))
                if not text_tokens:
                    continue
                text_counts: dict[str, int] = {}
                for token in text_tokens:
                    text_counts[token] = text_counts.get(token, 0) + 1

                overlap = 0.0
                for token, q_count in query_counts.items():
                    overlap += min(q_count, text_counts.get(token, 0))
                if overlap <= 0:
                    continue

                norm = math.sqrt(len(query_tokens) * len(text_tokens))
                lexical_score = overlap / norm if norm else 0.0
                scored.append(
                    RetrievedChunk(
                        id=str(point.id),
                        payload=payload,
                        lexical_score=lexical_score,
                        retrieval_method="lexical",
                        score=lexical_score,
                        retrieval_methods={"lexical"},
                    )
                )
            if offset is None:
                break

        scored.sort(key=lambda item: item.lexical_score or 0.0, reverse=True)
        return scored[:top_k]

    async def delete_by_doc_id(self, doc_id: str) -> None:
        await self.client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                        FieldCondition(key="namespace", match=MatchValue(value=settings.qdrant_namespace)),
                    ]
                )
            ),
        )
        logger.info(f"Deleted vectors for doc {doc_id}")

    async def health(self) -> str:
        try:
            await self.client.get_collections()
            return "ok"
        except Exception as exc:
            return f"error: {exc}"


@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    return QdrantService()
