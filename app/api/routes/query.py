from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_current_user_id
from app.schemas.schemas import QueryRequest, QueryResponse
from app.services.rag_pipeline import run_rag_pipeline
from app.db import chat_db
from app.db.database import get_db
from app.services.ingestion_service import get_conversation_ready_document_count, get_conversation_documents
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

router = APIRouter(prefix="/query", tags=["rag"])


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify conversation belongs to user
    conv = await chat_db.get_conversation(user_id, request.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    ready_docs = await get_conversation_ready_document_count(request.conversation_id, db)
    if ready_docs == 0:
        docs = await get_conversation_documents(request.conversation_id, db)
        has_processing = any((d.status or "").lower() == "processing" for d in docs)
        has_failed = any((d.status or "").lower() == "failed" for d in docs)
        if has_processing:
            assistant_text = "Documents are still processing for this chat. Please wait a moment and try again."
        elif has_failed:
            assistant_text = "Document processing failed for this chat. Re-upload the files and try again."
        else:
            assistant_text = "Upload documents to this chat first."
        await chat_db.add_message(
            user_id=user_id,
            conv_id=request.conversation_id,
            role="user",
            content=request.query,
        )
        asst_msg = await chat_db.add_message(
            user_id=user_id,
            conv_id=request.conversation_id,
            role="assistant",
            content=assistant_text,
        )
        messages = await chat_db.get_messages(user_id, request.conversation_id)
        if len(messages) <= 2:
            await chat_db.auto_title_conversation(user_id, request.conversation_id, request.query)
        return QueryResponse(
            message_id=asst_msg.id,
            conversation_id=request.conversation_id,
            query=request.query,
            search_query=request.query,
            answer=assistant_text,
            sources=[],
            model="none",
            retrieval_strategy="none",
            conversation_turns_used=0,
            retrieval_ms=0,
            rerank_ms=0,
            generation_ms=0,
        )

    logger.info(f"RAG query user={user_id} conv={request.conversation_id}: {request.query[:60]}...")
    try:
        return await run_rag_pipeline(request, user_id)
    except Exception as exc:
        logger.error(f"RAG pipeline error: {exc}")
        raise HTTPException(status_code=500, detail=f"RAG pipeline failed: {str(exc)}")
