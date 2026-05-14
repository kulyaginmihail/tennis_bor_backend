from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import httpx

from app.database import get_db
from app.models.sparring import Match, MatchParticipant, SparringRequest, MatchFormat, MatchStatus
from app.models.user import User
from app.services.stats import get_or_create_stats, _update_streak, _update_elo, check_achievements

router = APIRouter(prefix="/api/sparring", tags=["sparring"])


async def _get_or_create_user(db, user_id, first_name, last_name, username):
    if not user_id:
        return None
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        user = User(id=user_id, first_name=first_name or "Игрок", last_name=last_name, username=username)
        db.add(user)
        await db.flush()
    return user


class CreateMatchRequest(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    format: str = "single"
    title: str = "Матч"
    description: Optional[str] = None
    play_date: datetime
    duration_hours: float = 1.0
    court: Optional[str] = None
    ntrp_min: float = 2.0
    ntrp_max: float = 5.0


@router.get("/matches")
async def list_matches(
    ntrp_min: Optional[float] = None,
    ntrp_max: Optional[float] = None,
    format: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Match).where(Match.status == MatchStatus.open).order_by(Match.play_date)
    if ntrp_min is not None:
        q = q.where(Match.ntrp_max >= ntrp_min)
    if ntrp_max is not None:
        q = q.where(Match.ntrp_min <= ntrp_max)
    if format:
        q = q.where(Match.format == format)
    result = await db.execute(q)
    matches = result.scalars().all()
    return [_match_out(m) for m in matches]


def _match_out(m: Match) -> dict:
    return {
        "id": m.id,
        "organizer_id": m.organizer_id,
        "organizer_name": m.organizer_name,
        "organizer_username": m.organizer_username,
        "format": m.format.value if hasattr(m.format, "value") else m.format,
        "status": m.status.value if hasattr(m.status, "value") else m.status,
        "title": m.title,
        "description": m.description,
        "play_date": m.play_date.isoformat(),
        "duration_hours": m.duration_hours,
        "court": m.court,
        "ntrp_min": m.ntrp_min,
        "ntrp_max": m.ntrp_max,
        "slots_total": m.slots_total,
        "slots_taken": m.slots_taken,
        "slots_left": m.slots_total - m.slots_taken,
        "score": m.score,
        "score_status": m.score_status,
        "score_winner": m.score_winner,
        "created_at": m.created_at.isoformat(),
    }


@router.post("/matches")
async def create_match(body: CreateMatchRequest, db: AsyncSession = Depends(get_db)):
    user = await _get_or_create_user(db, body.user_id, body.first_name, body.last_name, body.username)
    display_name = user.display_name if user else (body.first_name or "Игрок")
    username = user.username if user else body.username
    slots = {"single": 2, "double": 4, "mixed": 4}.get(body.format, 2)

    match = Match(
        organizer_id=body.user_id, organizer_name=display_name, organizer_username=username,
        format=body.format, title=body.title, description=body.description,
        play_date=body.play_date, duration_hours=body.duration_hours, court=body.court,
        ntrp_min=body.ntrp_min, ntrp_max=body.ntrp_max, slots_total=slots, slots_taken=1,
    )
    db.add(match)
    await db.flush()

    if body.user_id:
        w_stats = await get_or_create_stats(body.user_id, db)
        w_stats.matches_created += 1

    await db.commit()
    return _match_out(match)


class JoinMatchBody(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    team: Optional[str] = None


@router.post("/matches/{match_id}/join")
async def join_match(match_id: int, body: JoinMatchBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    if match.status != MatchStatus.open:
        raise HTTPException(status_code=400, detail="Матч уже недоступен")
    if match.slots_taken >= match.slots_total:
        raise HTTPException(status_code=400, detail="Все места заняты")
    if match.organizer_id == body.user_id:
        raise HTTPException(status_code=400, detail="Вы организатор этого матча")

    dup = await db.execute(select(MatchParticipant).where(
        MatchParticipant.match_id == match_id, MatchParticipant.user_id == body.user_id))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже в этом матче")

    user = await _get_or_create_user(db, body.user_id, body.first_name, body.last_name, body.username)
    display_name = user.display_name if user else (body.first_name or "Игрок")

    participant = MatchParticipant(
        match_id=match_id, user_id=body.user_id, user_name=display_name,
        user_username=body.username, team=body.team,
    )
    db.add(participant)
    match.slots_taken += 1
    if match.slots_taken >= match.slots_total:
        match.status = MatchStatus.full
    await db.commit()
    return {"ok": True, "slots_left": match.slots_total - match.slots_taken, "status": match.status}


@router.post("/matches/{match_id}/leave")
async def leave_match(match_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")

    part_res = await db.execute(select(MatchParticipant).where(
        MatchParticipant.match_id == match_id, MatchParticipant.user_id == user_id))
    participant = part_res.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="Вы не в этом матче")

    await db.delete(participant)
    match.slots_taken = max(1, match.slots_taken - 1)
    if match.status == MatchStatus.full:
        match.status = MatchStatus.open
    await db.commit()
    return {"ok": True}


def _match_to_dict(m: Match, participants: list) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "status": m.status.value if hasattr(m.status, "value") else m.status,
        "score_status": m.score_status,
        "score_winner": m.score_winner,
        "play_date": m.play_date.isoformat(),
        "format": m.format.value if hasattr(m.format, "value") else m.format,
        "court": m.court,
        "ntrp_min": m.ntrp_min,
        "ntrp_max": m.ntrp_max,
        "slots_total": m.slots_total,
        "slots_taken": m.slots_taken,
        "score": m.score,
        "participants": [
            {"user_name": p.user_name, "user_username": p.user_username,
             "team": p.team, "score_confirmed": p.score_confirmed}
            for p in participants
        ],
    }


@router.get("/matches/my")
async def my_matches(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match).where(Match.organizer_id == user_id).order_by(desc(Match.play_date))
    )
    out = []
    for m in result.scalars().all():
        parts_res = await db.execute(select(MatchParticipant).where(MatchParticipant.match_id == m.id))
        d = _match_to_dict(m, parts_res.scalars().all())
        d["my_confirmed"] = bool(m.score) if m.score_status != "confirmed" else True
        out.append(d)
    return out


@router.get("/matches/joined")
async def joined_matches(user_id: int, db: AsyncSession = Depends(get_db)):
    parts_res = await db.execute(select(MatchParticipant).where(MatchParticipant.user_id == user_id))
    out = []
    for p in parts_res.scalars().all():
        match_res = await db.execute(select(Match).where(Match.id == p.match_id))
        m = match_res.scalar_one_or_none()
        if not m:
            continue
        all_parts = await db.execute(select(MatchParticipant).where(MatchParticipant.match_id == m.id))
        d = _match_to_dict(m, all_parts.scalars().all())
        d["my_confirmed"] = p.score_confirmed
        d["my_team"] = p.team
        out.append(d)
    return out


class ScoreBody(BaseModel):
    user_id: int
    score: str
    winner: str = "organizer"


@router.post("/matches/{match_id}/score")
async def set_match_score(match_id: int, body: ScoreBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    if match.organizer_id != body.user_id:
        raise HTTPException(status_code=403, detail="Только организатор может выставить счёт")
    match.score = body.score
    match.score_winner = body.winner
    match.score_status = "pending"
    await db.commit()
    return {"ok": True}


@router.post("/matches/{match_id}/score/confirm")
async def confirm_score(match_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match or not match.score:
        raise HTTPException(status_code=404, detail="Матч или счёт не найден")

    part_res = await db.execute(select(MatchParticipant).where(
        MatchParticipant.match_id == match_id, MatchParticipant.user_id == user_id))
    participant = part_res.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=403, detail="Вы не участник этого матча")

    participant.score_confirmed = True
    all_parts_res = await db.execute(select(MatchParticipant).where(MatchParticipant.match_id == match_id))
    all_parts = all_parts_res.scalars().all()
    if all(p.score_confirmed for p in all_parts):
        match.score_status = "confirmed"
        match.status = MatchStatus.played
        await _update_sparring_stats(match, all_parts, db)
    await db.commit()
    return {"ok": True, "all_confirmed": match.score_status == "confirmed"}


@router.delete("/matches/{match_id}")
async def delete_match(match_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    if match.organizer_id != user_id:
        raise HTTPException(status_code=403, detail="Только организатор может удалить матч")
    match.status = MatchStatus.cancelled
    await db.commit()
    return {"ok": True}


async def _update_sparring_stats(match: Match, participants: list, db: AsyncSession):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    winner_ids, loser_ids = [], []
    if match.score_winner == "organizer":
        if match.organizer_id: winner_ids.append(match.organizer_id)
        loser_ids = [p.user_id for p in participants if p.user_id]
    elif match.score_winner == "participant":
        if match.organizer_id: loser_ids.append(match.organizer_id)
        winner_ids = [p.user_id for p in participants if p.user_id]
    elif match.score_winner in ("A", "B"):
        if match.organizer_id:
            (winner_ids if match.score_winner == "A" else loser_ids).append(match.organizer_id)
        for p in participants:
            if p.user_id:
                (winner_ids if p.team == match.score_winner else loser_ids).append(p.user_id)

    winner_stats_list = []
    for uid in winner_ids:
        s = await get_or_create_stats(uid, db)
        s.matches_total += 1; s.matches_won += 1; s.monthly_wins += 1; s.monthly_matches += 1
        _update_streak(s, now); winner_stats_list.append(s)
    loser_stats_list = []
    for uid in loser_ids:
        s = await get_or_create_stats(uid, db)
        s.matches_total += 1; s.matches_lost += 1; s.monthly_matches += 1
        _update_streak(s, now); loser_stats_list.append(s)

    # Apply ELO update for 1v1 matches
    if len(winner_stats_list) == 1 and len(loser_stats_list) == 1:
        _update_elo(winner_stats_list[0], loser_stats_list[0])

    for uid, s in zip(winner_ids, winner_stats_list):
        await db.flush(); await check_achievements(uid, s, db)
    for uid, s in zip(loser_ids, loser_stats_list):
        await db.flush(); await check_achievements(uid, s, db)


# ── Sparring Requests ──────────────────────────────────────────

class CreateRequestBody(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    format: str = "single"
    ntrp_level: str = "3.0"
    preferred_time: str = ""
    comment: Optional[str] = None


@router.get("/requests")
async def list_requests(format: Optional[str] = None, ntrp: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(SparringRequest).where(SparringRequest.is_active == True).order_by(desc(SparringRequest.created_at))
    if format: q = q.where(SparringRequest.format == format)
    if ntrp: q = q.where(SparringRequest.ntrp_level == ntrp)
    result = await db.execute(q)
    return [
        {"id": r.id, "user_name": r.user_name, "user_username": r.user_username,
         "format": r.format, "ntrp_level": r.ntrp_level, "preferred_time": r.preferred_time,
         "comment": r.comment, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in result.scalars().all()
    ]


@router.post("/requests")
async def create_request(body: CreateRequestBody, db: AsyncSession = Depends(get_db)):
    user = await _get_or_create_user(db, body.user_id, body.first_name, body.last_name, body.username)
    display_name = user.display_name if user else (body.first_name or "Игрок")
    username = user.username if user else body.username

    req = SparringRequest(
        user_id=body.user_id, user_name=display_name, user_username=username,
        format=body.format, ntrp_level=body.ntrp_level, preferred_time=body.preferred_time, comment=body.comment,
    )
    db.add(req)
    await db.commit()

    # TG notification
    from app.config import settings
    if settings.bot_token and settings.bot_token != "test" and settings.admin_chat_id:
        fmt_map = {"single": "Одиночный", "double": "Парный", "mixed": "Микст"}
        text = (f"🎾 Новая заявка на спарринг\n\n"
                f"👤 {display_name}\n"
                f"📊 NTRP: {body.ntrp_level}\n"
                f"🎯 Формат: {fmt_map.get(body.format, body.format)}\n"
                f"⏰ {body.preferred_time}")
        if body.comment:
            text += f"\n💬 {body.comment}"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",
                    json={"chat_id": settings.admin_chat_id, "text": text}
                )
        except Exception:
            pass

    return {"ok": True, "id": req.id}


@router.delete("/requests/{request_id}")
async def delete_request(request_id: int, user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SparringRequest).where(SparringRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if req.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    req.is_active = False
    await db.commit()
    return {"ok": True}
