from __future__ import annotations
import asyncio
from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer
from loguru import logger
from app.core.config import get_settings

settings = get_settings()


class EmbeddingService:
    _model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    async def preload(self) -> None:
        """Eagerly load the model at startup so the first request has no delay."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load)
        logger.info(f"Embedding model ready: {settings.embedding_model}")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_running_loop()
        model = self._load()
        return await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
        )

    async def embed_query(self, query: str) -> List[float]:
        vecs = await self.embed_texts([query])
        return vecs[0]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
