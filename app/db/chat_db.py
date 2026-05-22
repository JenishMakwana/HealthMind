"""
Per-user chat database.

Each user gets their own SQLite file at:
  ./data/users/<user_id>/chats.db

Schema:
  conversations  – chat sessions (like ChatGPT sidebar items)
  messages       – individual messages within a conversation
"""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, ForeignKey, select, update
from loguru import logger


class ChatBase(DeclarativeBase):
    pass


class Conversation(ChatBase):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Message(ChatBase):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)   # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text)          # JSON-serialised SourceChunk list
    meta_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ─── Engine pool per user ─────────────────────────────────────────────────────
_engines: dict[str, any] = {}


def _get_user_engine(user_id: str):
    if user_id not in _engines:
        user_dir = f"./data/users/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        db_path = f"{user_dir}/chats.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        _engines[user_id] = engine
    return _engines[user_id]


async def ensure_user_db(user_id: str) -> None:
    engine = _get_user_engine(user_id)
    async with engine.begin() as conn:
        await conn.run_sync(ChatBase.metadata.create_all)
        columns = await conn.exec_driver_sql("PRAGMA table_info(messages)")
        column_names = {row[1] for row in columns.fetchall()}
        if "meta_json" not in column_names:
            await conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN meta_json TEXT")
    logger.debug(f"Chat DB ready for user {user_id}")


def _session_maker(user_id: str) -> async_sessionmaker:
    return async_sessionmaker(_get_user_engine(user_id), expire_on_commit=False)


# ─── CRUD helpers ─────────────────────────────────────────────────────────────

async def create_conversation(user_id: str, title: str = "New Chat") -> Conversation:
    await ensure_user_db(user_id)
    async with _session_maker(user_id)() as db:
        conv = Conversation(id=str(uuid.uuid4()), title=title)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv


async def list_conversations(user_id: str) -> List[Conversation]:
    await ensure_user_db(user_id)
    async with _session_maker(user_id)() as db:
        result = await db.execute(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        return result.scalars().all()


async def get_conversation(user_id: str, conv_id: str) -> Optional[Conversation]:
    await ensure_user_db(user_id)
    async with _session_maker(user_id)() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        return result.scalar_one_or_none()


async def rename_conversation(user_id: str, conv_id: str, new_title: str) -> None:
    async with _session_maker(user_id)() as db:
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(title=new_title, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()


async def delete_conversation(user_id: str, conv_id: str) -> None:
    async with _session_maker(user_id)() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        conv = result.scalar_one_or_none()
        if conv:
            # cascade delete messages first
            msgs = await db.execute(select(Message).where(Message.conversation_id == conv_id))
            for msg in msgs.scalars().all():
                await db.delete(msg)
            await db.delete(conv)
            await db.commit()


async def add_message(
    user_id: str,
    conv_id: str,
    role: str,
    content: str,
    sources_json: str | None = None,
    meta_json: str | None = None,
) -> Message:
    async with _session_maker(user_id)() as db:
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            role=role,
            content=content,
            sources_json=sources_json,
            meta_json=meta_json,
        )
        db.add(msg)
        # Touch conversation updated_at so it floats to top
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await db.commit()
        await db.refresh(msg)
        return msg


async def get_messages(user_id: str, conv_id: str) -> List[Message]:
    await ensure_user_db(user_id)
    async with _session_maker(user_id)() as db:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
        )
        return result.scalars().all()


async def auto_title_conversation(user_id: str, conv_id: str, first_question: str) -> None:
    """Set a smart title from the first user message (truncated)."""
    title = first_question[:60] + ("…" if len(first_question) > 60 else "")
    await rename_conversation(user_id, conv_id, title)
