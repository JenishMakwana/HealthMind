"""
Conversation management routes — ChatGPT-style sidebar.
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.db import chat_db
from app.schemas.schemas import (
    ConversationOut,
    ConversationCreate,
    ConversationRename,
    MessageOut,
    SourceChunk,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _msg_to_out(msg) -> MessageOut:
    sources = None
    meta = None
    if msg.sources_json:
        try:
            raw = json.loads(msg.sources_json)
            sources = [SourceChunk(**s) for s in raw]
        except Exception:
            sources = None
    if getattr(msg, "meta_json", None):
        try:
            meta = json.loads(msg.meta_json)
        except Exception:
            meta = None
    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        sources=sources,
        meta=meta,
        created_at=msg.created_at,
    )


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
):
    conv = await chat_db.create_conversation(user_id, payload.title)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("", response_model=List[ConversationOut])
async def list_conversations(user_id: str = Depends(get_current_user_id)):
    convs = await chat_db.list_conversations(user_id)
    return [
        ConversationOut(id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at)
        for c in convs
    ]


@router.get("/{conv_id}/messages", response_model=List[MessageOut])
async def get_messages(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
):
    conv = await chat_db.get_conversation(user_id, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = await chat_db.get_messages(user_id, conv_id)
    return [_msg_to_out(m) for m in msgs]


@router.patch("/{conv_id}", response_model=ConversationOut)
async def rename_conversation(
    conv_id: str,
    payload: ConversationRename,
    user_id: str = Depends(get_current_user_id),
):
    conv = await chat_db.get_conversation(user_id, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await chat_db.rename_conversation(user_id, conv_id, payload.title)
    conv = await chat_db.get_conversation(user_id, conv_id)
    return ConversationOut(id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at)


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
):
    conv = await chat_db.get_conversation(user_id, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await chat_db.delete_conversation(user_id, conv_id)
