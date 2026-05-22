from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "HealthMind"
    app_version: str = "1.0.0"
    debug: bool = False

    secret_key: str = Field(default="dev-secret-change-in-prod")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_path: str = "data/qdrant"
    qdrant_collection_name: str = "medical-knowledge-rag"
    qdrant_namespace: str = "medical-docs"
    qdrant_vector_size: int = 768

    groq_api_key: str = Field(default="")
    google_api_key: str = Field(default="")
    llm_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    gemini_model: str = "gemini-2.5-flash"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.1

    embedding_model: str = "NeuML/pubmedbert-base-embeddings"

    # STT (Speech-to-Text) — Qwen ASR
    stt_enabled: bool = True
    stt_model: str = "Qwen/Qwen3-ASR-1.7B"
    stt_device: str = "auto"
    stt_dtype: str = "auto"
    stt_max_new_tokens: int = 256
    stt_context: str = ""
    stt_language: str = "en"
    speech_max_upload_mb: int = 25

    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 5
    reranker_max_chunks_per_doc: int = 2
    reranker_min_score: float = -1.0
    reranker_score_window: float = 1.5

    rag_retrieval_top_k: int = 20
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 64
    rag_conversation_history_turns: int = 6
    rag_hybrid_rrf_k: int = 60

    database_url: str = "sqlite+aiosqlite:///./data/healthmind_main.db"
    allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()

