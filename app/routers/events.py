from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.event import HomeEvent

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(HomeEvent)
        .where(HomeEvent.is_active == True)
        .order_by(HomeEvent.sort_order, HomeEvent.id)
    )
    events = res.scalars().all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "subtitle": e.subtitle,
            "color": e.color,
            "link_to": e.link_to,
            "sort_order": e.sort_order,
        }
        for e in events
    ]
