from __future__ import annotations
import asyncio
import io
import uuid
from typing import Any, List

from fastapi import UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.db.database import AsyncSessionLocal, DocumentRecord
from app.services.embedding_service import get_embedding_service
from app.services.qdrant_service import get_qdrant_service

settings = get_settings()
_ingestion_tasks: set[asyncio.Task] = set()


def _extract_pdf(data: bytes) -> List[dict[str, Any]]:
    import fitz
    with fitz.open(stream=data, filetype="pdf") as doc:
        return [
            {"text": page.get_text("text") or "", "page_number": page.number + 1}
            for page in doc
        ]


def _extract_docx(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def extract_segments(filename: str, data: bytes) -> List[dict[str, Any]]:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return _extract_pdf(data)
    elif ext in ("docx", "doc"):
        return [{"text": _extract_docx(data), "page_number": None}]
    elif ext == "txt":
        return [{"text": _extract_txt(data), "page_number": None}]
    raise ValueError(f"Unsupported file type: .{ext}")


def chunk_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c for c in splitter.split_text(text) if c.strip()]


def chunk_segments(segments: List[dict[str, Any]]) -> List[dict[str, Any]]:
    chunks: List[dict[str, Any]] = []
    for segment in segments:
        text = segment.get("text", "")
        if not text.strip():
            continue
        for chunk in chunk_text(text):
            chunks.append(
                {
                    "text": chunk,
                    "page_number": segment.get("page_number"),
                }
            )
    return chunks


async def ingest_document(
    file: UploadFile,
    title: str,
    source: str | None,
    user_id: str,
    conversation_id: str,
    db: AsyncSession,
) -> str:
    doc_id = str(uuid.uuid4())
    filename = file.filename or "unknown"

    record = DocumentRecord(
        id=doc_id, filename=filename, title=title,
        source=source, chunk_count=0, uploaded_by=user_id, conversation_id=conversation_id, status="processing",
    )
    db.add(record)
    await db.commit()

    try:
        raw_bytes = await file.read()
        logger.info(f"Ingesting '{filename}' ({len(raw_bytes):,} bytes)")
        segments = extract_segments(filename, raw_bytes)
        if not any((segment.get("text") or "").strip() for segment in segments):
            raise ValueError("No extractable text found — file may be image-only.")

        chunks = chunk_segments(segments)
        logger.info(f"Split '{filename}' into {len(chunks)} chunks")

        emb_svc = get_embedding_service()
        embeddings = await emb_svc.embed_texts([chunk["text"] for chunk in chunks])

        qdrant = get_qdrant_service()
        await qdrant.ensure_collection()
        n = await qdrant.upsert_chunks(
            doc_id=doc_id, chunks=chunks, embeddings=embeddings,
            metadata={
                "filename": filename,
                "title": title,
                "source": source or "",
                "conversation_id": record.conversation_id,
            },
        )

        record.chunk_count = n
        record.status = "ready"
        await db.commit()
        logger.success(f"Document {doc_id} ready ({n} chunks)")

    except Exception as exc:
        record.status = "error"
        record.error_message = str(exc)
        await db.commit()
        logger.error(f"Ingestion failed for {doc_id}: {exc}")
        raise

    return doc_id


async def create_document_record(
    *,
    filename: str,
    title: str,
    source: str | None,
    user_id: str,
    conversation_id: str,
    db: AsyncSession,
) -> str:
    doc_id = str(uuid.uuid4())
    record = DocumentRecord(
        id=doc_id,
        filename=filename,
        title=title,
        source=source,
        chunk_count=0,
        uploaded_by=user_id,
        conversation_id=conversation_id,
        status="processing",
    )
    db.add(record)
    await db.commit()
    return doc_id


async def ingest_document_bytes(
    *,
    doc_id: str,
    filename: str,
    title: str,
    source: str | None,
    raw_bytes: bytes,
    db: AsyncSession,
) -> None:
    record = await db.get(DocumentRecord, doc_id)
    if not record:
        raise ValueError(f"Document record not found: {doc_id}")

    try:
        logger.info(f"Ingesting '{filename}' ({len(raw_bytes):,} bytes)")
        segments = extract_segments(filename, raw_bytes)
        if not any((segment.get("text") or "").strip() for segment in segments):
            raise ValueError("No extractable text found - file may be image-only.")

        chunks = chunk_segments(segments)
        logger.info(f"Split '{filename}' into {len(chunks)} chunks")

        emb_svc = get_embedding_service()
        embeddings = await emb_svc.embed_texts([chunk["text"] for chunk in chunks])

        qdrant = get_qdrant_service()
        await qdrant.ensure_collection()
        n = await qdrant.upsert_chunks(
            doc_id=doc_id, chunks=chunks, embeddings=embeddings,
            metadata={
                "filename": filename,
                "title": title,
                "source": source or "",
                "conversation_id": record.conversation_id,
            },
        )

        record.chunk_count = n
        record.status = "ready"
        record.error_message = None
        await db.commit()
        logger.success(f"Document {doc_id} ready ({n} chunks)")

    except Exception as exc:
        record.status = "error"
        record.error_message = str(exc)
        await db.commit()
        logger.error(f"Ingestion failed for {doc_id}: {exc}")
        raise


async def ingest_document_background(
    *,
    doc_id: str,
    filename: str,
    title: str,
    source: str | None,
    raw_bytes: bytes,
) -> None:
    async with AsyncSessionLocal() as db:
        await ingest_document_bytes(
            doc_id=doc_id,
            filename=filename,
            title=title,
            source=source,
            raw_bytes=raw_bytes,
            db=db,
        )


async def _run_ingestion_job(
    *,
    doc_id: str,
    filename: str,
    title: str,
    source: str | None,
    raw_bytes: bytes,
) -> None:
    try:
        await ingest_document_background(
            doc_id=doc_id,
            filename=filename,
            title=title,
            source=source,
            raw_bytes=raw_bytes,
        )
    except Exception:
        # Errors are persisted onto the document record inside ingest_document_bytes.
        logger.exception(f"Background ingestion crashed for doc {doc_id}")


def schedule_ingestion(
    *,
    doc_id: str,
    filename: str,
    title: str,
    source: str | None,
    raw_bytes: bytes,
) -> None:
    task = asyncio.create_task(
        _run_ingestion_job(
            doc_id=doc_id,
            filename=filename,
            title=title,
            source=source,
            raw_bytes=raw_bytes,
        )
    )
    _ingestion_tasks.add(task)
    task.add_done_callback(_ingestion_tasks.discard)


async def get_all_documents(db: AsyncSession) -> List[DocumentRecord]:
    result = await db.execute(select(DocumentRecord).order_by(DocumentRecord.created_at.desc()))
    return result.scalars().all()


async def get_conversation_documents(conversation_id: str, db: AsyncSession) -> List[DocumentRecord]:
    result = await db.execute(
        select(DocumentRecord)
        .where(DocumentRecord.conversation_id == conversation_id)
        .order_by(DocumentRecord.created_at.desc())
    )
    return result.scalars().all()


async def get_conversation_ready_document_count(conversation_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(DocumentRecord)
        .where(
            DocumentRecord.conversation_id == conversation_id,
            DocumentRecord.status == "ready",
        )
    )
    return len(result.scalars().all())


async def get_document(doc_id: str, db: AsyncSession) -> DocumentRecord | None:
    result = await db.execute(select(DocumentRecord).where(DocumentRecord.id == doc_id))
    return result.scalar_one_or_none()
