from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user import User

router = APIRouter(tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    ntrp_level: Optional[str] = None
    preferred_format: Optional[str] = None


@router.put("/api/profile/{user_id}")
async def update_profile(user_id: int, body: ProfileUpdateRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if body.first_name:       user.first_name       = body.first_name
    if body.last_name:        user.last_name         = body.last_name
    if body.username:         user.username          = body.username
    if body.ntrp_level:       user.ntrp_level        = body.ntrp_level
    if body.preferred_format: user.preferred_format  = body.preferred_format
    await db.commit()
    return {"ok": True}
