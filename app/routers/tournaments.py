from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.tournament import Tournament, TournamentParticipant, TournamentStatus, TournamentSport

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


def _tourn_out(t: Tournament) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "sport": t.sport.value if hasattr(t.sport, "value") else t.sport,
        "status": t.status.value if hasattr(t.status, "value") else t.status,
        "play_date": t.play_date,
        "format": t.format,
        "max_participants": t.max_participants,
        "entry_fee": t.entry_fee,
        "is_published": t.is_published,
    }


@router.get("")
async def list_tournaments(db: AsyncSession = Depends(get_db)):
    q = select(Tournament).where(Tournament.is_published == True).order_by(Tournament.play_date)
    result = await db.execute(q)
    return [_tourn_out(t) for t in result.scalars().all()]


@router.get("/{tournament_id}")
async def get_tournament(tournament_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Турнир не найден")
    return _tourn_out(t)


class JoinTournamentBody(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


@router.post("/{tournament_id}/join")
async def join_tournament(tournament_id: int, body: JoinTournamentBody, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Турнир не найден")
    if t.status not in (TournamentStatus.open, TournamentStatus.upcoming):
        raise HTTPException(status_code=400, detail="Регистрация закрыта")

    display = (body.first_name or "Игрок")
    if body.last_name:
        display += f" {body.last_name[0]}."

    participant = TournamentParticipant(
        tournament_id=tournament_id, user_id=body.user_id, user_name=display
    )
    db.add(participant)
    await db.commit()
    return {"ok": True}
