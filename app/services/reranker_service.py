from __future__ import annotations
import asyncio
from functools import lru_cache
from typing import List, Tuple, TypeVar, Callable

from sentence_transformers.cross_encoder import CrossEncoder
from loguru import logger
from app.core.config import get_settings

settings = get_settings()
T = TypeVar("T")


class RerankerService:
    _model: CrossEncoder | None = None

    def _load(self) -> CrossEncoder:
        if self._model is None:
            logger.info(f"Loading reranker: {settings.reranker_model}")
            self._model = CrossEncoder(settings.reranker_model, max_length=512)
        return self._model

    async def preload(self) -> None:
        """Eagerly load the model at startup so the first request has no delay."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load)
        logger.info(f"Reranker model ready: {settings.reranker_model}")

    async def rerank(
        self,
        query: str,
        candidates: List[T],
        text_fn: Callable[[T], str],
        top_k: int | None = None,
    ) -> List[Tuple[T, float]]:
        if not candidates:
            return []
        k = top_k or settings.reranker_top_k
        model = self._load()
        pairs = [(query, text_fn(c)) for c in candidates]
        loop = asyncio.get_running_loop()
        scores: List[float] = await loop.run_in_executor(None, lambda: model.predict(pairs).tolist())
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]


@lru_cache(maxsize=1)
def get_reranker_service() -> RerankerService:
    return RerankerService()
