from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.core.security import get_current_user_id
from app.db.database import get_db, User, DocumentRecord
from app.schemas.schemas import HealthResponse, UserOut
from app.services.qdrant_service import get_qdrant_service
from app.services.llm_service import get_llm_service
from app.core.config import get_settings

settings = get_settings()

health_router = APIRouter(tags=["health"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@health_router.get("/health", response_model=HealthResponse)
async def health():
    qdrant_status = await get_qdrant_service().health()
    llm_status = await get_llm_service().health()
    return HealthResponse(
        status="ok" if qdrant_status == "ok" and llm_status == "ok" else "degraded",
        qdrant=qdrant_status,
        llm=llm_status,
        version=settings.app_version,
    )


async def _require_admin(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@admin_router.get("/users", response_model=List[UserOut])
async def list_users(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@admin_router.patch("/users/{target_id}/role")
async def update_user_role(
    target_id: str,
    role: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    result = await db.execute(select(User).where(User.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = role
    await db.commit()
    return {"id": target_id, "role": role}


@admin_router.patch("/users/{target_id}/toggle")
async def toggle_user_active(
    target_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    result = await db.execute(select(User).where(User.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = not target.is_active
    await db.commit()
    return {"id": target_id, "is_active": target.is_active}


@admin_router.get("/stats")
async def admin_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    user_count = await db.scalar(select(func.count()).select_from(User))
    doc_count = await db.scalar(select(func.count()).select_from(DocumentRecord))
    ready_docs = await db.scalar(
        select(func.count()).select_from(DocumentRecord).where(DocumentRecord.status == "ready")
    )
    total_chunks = await db.scalar(select(func.sum(DocumentRecord.chunk_count)).select_from(DocumentRecord))
    qdrant_status = await get_qdrant_service().health()
    return {
        "total_users": user_count,
        "total_documents": doc_count,
        "ready_documents": ready_docs,
        "total_chunks_indexed": total_chunks or 0,
        "qdrant_status": qdrant_status,
    }
