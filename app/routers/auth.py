from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.services.stats import get_or_create_stats

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    tg_id: int
    first_name: Optional[str] = "Игрок"
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == body.tg_id))
    user = res.scalar_one_or_none()

    if user is None:
        user = User(
            id=body.tg_id,
            first_name=body.first_name or "Игрок",
            last_name=body.last_name,
            username=body.username,
            photo_url=body.photo_url,
        )
        db.add(user)
    else:
        if body.first_name: user.first_name = body.first_name
        if body.last_name:  user.last_name  = body.last_name
        if body.username:   user.username   = body.username
        if body.photo_url:  user.photo_url  = body.photo_url
        user.last_seen = datetime.now(timezone.utc)

    await db.flush()
    # Ensure stats row exists
    await get_or_create_stats(body.tg_id, db)
    await db.commit()

    first = user.first_name or ""
    last = user.last_name or ""

    return {
        "user_id": user.id,
        "name": user.display_name,
        "username": user.username,
        "initials": ((first[0] if first else "") + (last[0] if last else "")).upper() or "?",
        "photo_url": user.photo_url,
        "ntrp_level": user.ntrp_level,
    }
