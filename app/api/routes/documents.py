from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.security import get_current_user_id
from app.db.database import get_db, DocumentRecord, User
from app.schemas.schemas import BatchIngestResponse, DocumentOut
from app.services.ingestion_service import (
    create_document_record,
    get_conversation_documents,
    get_all_documents,
    get_document,
    schedule_ingestion,
    extract_segments,
    chunk_segments,
)
from app.services.llm_service import get_llm_service
import asyncio
from app.db import chat_db
from app.services.qdrant_service import get_qdrant_service

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_EXT = {"pdf", "docx", "txt"}


def _check_ext(filename: str) -> None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXT)}")


async def _require_admin(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/upload", response_model=BatchIngestResponse, status_code=202)
async def upload_document(
    files: List[UploadFile] = File(...),
    conversation_id: str = Form(...),
    title: str | None = Form(default=None),
    source: str | None = Form(default=None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Queue one or more medical documents for ingestion."""
    conv = await chat_db.get_conversation(user_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    document_ids: List[str] = []
    valid_files = []
    rejected_files = []

    llm_svc = get_llm_service()

    async def validate_file(file: UploadFile):
        filename = file.filename or "unknown"
        try:
            _check_ext(filename)
            raw_bytes = await file.read()
            segments = extract_segments(filename, raw_bytes)
            chunks = chunk_segments(segments)
            sample_text = " ".join(chunk.get("text", "") for chunk in chunks[:3])
            
            is_medical = await llm_svc.check_if_medical_document(sample_text)
            if is_medical:
                return {"valid": True, "file": file, "filename": filename, "raw_bytes": raw_bytes}
            else:
                return {"valid": False, "filename": filename}
        except Exception:
            return {"valid": False, "filename": filename}

    results = await asyncio.gather(*(validate_file(f) for f in files))

    for res in results:
        if res["valid"]:
            valid_files.append(res)
        else:
            rejected_files.append(res["filename"])

    if not valid_files:
        msgs = await chat_db.get_messages(user_id, conversation_id)
        docs = await get_conversation_documents(conversation_id, db)
        if not msgs and not docs:
            await chat_db.delete_conversation(user_id, conversation_id)
        raise HTTPException(
            status_code=400,
            detail="All uploaded documents were rejected because they are not medical-related. Chat deleted."
        )

    for vf in valid_files:
        filename = vf["filename"]
        raw_bytes = vf["raw_bytes"]
        doc_title = title.strip() if title and len(files) == 1 else Path(filename).stem.replace("-", " ").replace("_", " ")
        doc_id = await create_document_record(
            filename=filename,
            title=doc_title,
            source=source,
            user_id=user_id,
            conversation_id=conversation_id,
            db=db,
        )
        schedule_ingestion(
            doc_id=doc_id,
            filename=filename,
            title=doc_title,
            source=source,
            raw_bytes=raw_bytes,
        )
        document_ids.append(doc_id)

    noun = "document" if len(document_ids) == 1 else "documents"
    msg = f"Queued {len(document_ids)} {noun} for ingestion."
    if rejected_files:
        msg += f" Rejected non-medical files: {', '.join(rejected_files)}"

    return BatchIngestResponse(
        document_ids=document_ids,
        message=msg,
        rejected_files=rejected_files if rejected_files else None,
    )


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    conversation_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if conversation_id:
        conv = await chat_db.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        docs = await get_conversation_documents(conversation_id, db)
    else:
        docs = await get_all_documents(db)
    return docs


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document_detail(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_document(doc_id, db)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/conversation/{conversation_id}", status_code=204)
async def clear_conversation_documents(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    conv = await chat_db.get_conversation(user_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    docs = await get_conversation_documents(conversation_id, db)
    qdrant = get_qdrant_service()
    for doc in docs:
        await qdrant.delete_by_doc_id(doc.id)
        await db.delete(doc)
    await db.commit()


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    doc = await get_document(doc_id, db)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    qdrant = get_qdrant_service()
    await qdrant.delete_by_doc_id(doc_id)
    await db.delete(doc)
    await db.commit()
