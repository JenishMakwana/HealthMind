import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import get_settings
from app.db.database import init_db
from app.api.routes.auth import router as auth_router
from app.api.routes.conversations import router as conv_router
from app.api.routes.query import router as query_router
from app.api.routes.documents import router as docs_router
from app.api.routes.audio import router as audio_router
from app.api.routes.health_admin import health_router, admin_router
from app.services.embedding_service import get_embedding_service
from app.services.reranker_service import get_reranker_service
from app.services.stt_service import get_stt_service

settings = get_settings()
os.makedirs("./data/users", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    logger.info("Main database initialised")

    # ── Pre-load all local ML models concurrently ───────────────────────────
    logger.info("Pre-loading ML models...")

    async def _preload_stt():
        try:
            await get_stt_service().preload()
        except Exception as exc:
            logger.warning(f"STT model pre-load skipped: {exc}")

    await asyncio.gather(
        get_embedding_service().preload(),
        get_reranker_service().preload(),
        _preload_stt(),
    )
    logger.info("All ML models are ready — server accepting requests")

    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Medical Knowledge RAG API — Groq · Llama 4 Scout · Qdrant · BioBERT · Cross-Encoder",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(health_router, prefix=PREFIX)
app.include_router(auth_router, prefix=PREFIX)
app.include_router(conv_router, prefix=PREFIX)
app.include_router(query_router, prefix=PREFIX)
app.include_router(docs_router, prefix=PREFIX)
app.include_router(audio_router, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}
