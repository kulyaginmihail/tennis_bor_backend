from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.tournament import Tournament, TournamentStatus, TournamentSport, Admin
from app.models.sparring import Match, MatchParticipant, SparringRequest, MatchStatus
from app.models.user import User
from app.models.stats import UserStats
from app.models.event import HomeEvent
from app.services.auth import hash_password, verify_password, create_access_token, get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Login ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.username == body.username))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    admin.last_login = datetime.now(timezone.utc)
    token = create_access_token({"sub": str(admin.id), "username": admin.username})
    return {"access_token": token, "token_type": "bearer", "display_name": admin.display_name}


@router.get("/create-first-admin")
@router.post("/create-first-admin")
async def create_first_admin(username: str, password: str, display_name: str = "Главный администратор", db: AsyncSession = Depends(get_db)):
    count = await db.execute(select(func.count(Admin.id)))
    if count.scalar() > 0:
        raise HTTPException(status_code=403, detail="Администраторы уже созданы")
    admin = Admin(username=username, password_hash=hash_password(password), display_name=display_name, is_superadmin=True)
    db.add(admin)
    await db.flush()
    return {"ok": True, "id": admin.id}


@router.get("/reset-admin-password")
async def reset_admin_password(new_password: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.is_superadmin == True))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Суперадмин не найден")
    admin.password_hash = hash_password(new_password)
    await db.flush()
    return {"ok": True, "username": admin.username}


# ── Stats ──────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models.lead import Lead
    from app.models.gift import GiftCertificate
    users_total = (await db.execute(select(func.count(User.id)))).scalar()
    matches_active = (await db.execute(select(func.count(Match.id)).where(Match.status == MatchStatus.open))).scalar()
    sparring_requests = (await db.execute(select(func.count(SparringRequest.id)).where(SparringRequest.is_active == True))).scalar()
    leads_total = (await db.execute(select(func.count(Lead.id)))).scalar()
    tournaments_total = (await db.execute(select(func.count(Tournament.id)).where(Tournament.is_published == True))).scalar()
    events_total = (await db.execute(select(func.count(HomeEvent.id)).where(HomeEvent.is_active == True))).scalar()
    return {
        "users_total": users_total,
        "matches_active": matches_active,
        "sparring_requests": sparring_requests,
        "leads_total": leads_total,
        "tournaments_total": tournaments_total,
        "events_total": events_total,
    }


# ── Matches admin ──────────────────────────────────────────────

@router.get("/matches")
async def admin_matches(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).order_by(desc(Match.created_at)).limit(100))
    return [
        {
            "id": m.id, "title": m.title, "organizer_name": m.organizer_name,
            "status": m.status.value if hasattr(m.status, "value") else m.status,
            "play_date": m.play_date.isoformat() if m.play_date else None,
            "format": m.format.value if hasattr(m.format, "value") else m.format,
            "court": m.court, "slots_total": m.slots_total, "slots_taken": m.slots_taken,
            "score": m.score, "score_status": m.score_status,
        }
        for m in result.scalars().all()
    ]


@router.delete("/matches/{match_id}")
async def admin_delete_match(match_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    match.status = MatchStatus.cancelled
    await db.commit()
    return {"ok": True}


@router.delete("/matches/{match_id}/score")
async def admin_reset_score(match_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    match.score = None; match.score_status = None; match.score_winner = None
    await db.commit()
    return {"ok": True}


# ── Sparring Requests admin ────────────────────────────────────

@router.get("/sparring-requests")
async def admin_sparring_requests(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SparringRequest).order_by(desc(SparringRequest.created_at)).limit(100))
    return [
        {"id": r.id, "user_name": r.user_name, "user_username": r.user_username,
         "format": r.format, "ntrp_level": r.ntrp_level, "preferred_time": r.preferred_time,
         "comment": r.comment, "is_active": r.is_active,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in result.scalars().all()
    ]


@router.delete("/sparring-requests/{req_id}")
async def admin_delete_request(req_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SparringRequest).where(SparringRequest.id == req_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    req.is_active = False
    await db.commit()
    return {"ok": True}


# ── Leads admin ────────────────────────────────────────────────

@router.get("/leads")
async def admin_leads(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models.lead import Lead
    result = await db.execute(select(Lead).order_by(desc(Lead.created_at)).limit(200))
    return [
        {"id": l.id, "name": l.name, "age_group": l.age_group,
         "contact_type": l.contact_type, "contact_value": l.contact_value,
         "created_at": l.created_at.isoformat() if l.created_at else None}
        for l in result.scalars().all()
    ]


# ── Gifts admin ────────────────────────────────────────────────

@router.get("/gifts")
async def admin_gifts(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.models.gift import GiftCertificate
    result = await db.execute(select(GiftCertificate).order_by(desc(GiftCertificate.created_at)).limit(200))
    return [
        {"id": g.id, "name": g.name, "amount": g.amount,
         "contact_type": g.contact_type, "contact_value": g.contact_value,
         "comment": g.comment, "created_at": g.created_at.isoformat() if g.created_at else None}
        for g in result.scalars().all()
    ]


# ── Tournaments admin ──────────────────────────────────────────

class TournamentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    sport: str = "padel"
    status: str = "open"
    play_date: str
    format: Optional[str] = None
    max_participants: Optional[int] = None
    entry_fee: Optional[float] = None
    is_published: bool = True


@router.get("/tournaments")
async def admin_tournaments(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).order_by(desc(Tournament.created_at)).limit(100))
    return [
        {"id": t.id, "title": t.title, "sport": t.sport.value if hasattr(t.sport, "value") else t.sport,
         "status": t.status.value if hasattr(t.status, "value") else t.status,
         "play_date": t.play_date, "entry_fee": t.entry_fee,
         "max_participants": t.max_participants, "is_published": t.is_published}
        for t in result.scalars().all()
    ]


@router.post("/tournaments")
async def admin_create_tournament(body: TournamentCreate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    t = Tournament(
        title=body.title, description=body.description, sport=body.sport, status=body.status,
        play_date=body.play_date, format=body.format,
        max_participants=body.max_participants, entry_fee=body.entry_fee, is_published=body.is_published
    )
    db.add(t)
    await db.commit()
    return {"ok": True, "id": t.id}


@router.delete("/tournaments/{tournament_id}")
async def admin_delete_tournament(tournament_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Турнир не найден")
    t.is_published = False
    await db.commit()
    return {"ok": True}


# ── Events admin ──────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    color: str = "default"
    link_to: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


@router.get("/events")
async def admin_events(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HomeEvent).order_by(HomeEvent.sort_order, HomeEvent.id))
    return [
        {"id": e.id, "title": e.title, "subtitle": e.subtitle,
         "color": e.color, "link_to": e.link_to, "sort_order": e.sort_order,
         "is_active": e.is_active,
         "created_at": e.created_at.isoformat() if e.created_at else None}
        for e in result.scalars().all()
    ]


@router.post("/events")
async def admin_create_event(body: EventCreate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    e = HomeEvent(
        title=body.title, subtitle=body.subtitle, color=body.color,
        link_to=body.link_to, sort_order=body.sort_order, is_active=body.is_active
    )
    db.add(e)
    await db.commit()
    return {"ok": True, "id": e.id}


@router.patch("/events/{event_id}")
async def admin_toggle_event(event_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HomeEvent).where(HomeEvent.id == event_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    e.is_active = not e.is_active
    await db.commit()
    return {"ok": True, "is_active": e.is_active}


@router.delete("/events/{event_id}")
async def admin_delete_event(event_id: int, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HomeEvent).where(HomeEvent.id == event_id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    await db.delete(e)
    await db.commit()
    return {"ok": True}


# ── Users admin ────────────────────────────────────────────────

@router.get("/users")
async def admin_users(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    q = select(User).order_by(desc(User.created_at)).limit(200)
    result = await db.execute(q)
    return [
        {"id": u.id, "username": u.username, "first_name": u.first_name, "last_name": u.last_name,
         "ntrp_level": u.ntrp_level, "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in result.scalars().all()
    ]
