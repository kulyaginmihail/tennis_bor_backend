import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.lead import Lead
from app.config import settings

router = APIRouter(prefix="/api/leads", tags=["leads"])


class LeadCreate(BaseModel):
    name: str
    age_group: str       # adult | child
    contact_type: str    # telegram | phone | email
    contact_value: str


async def _send_tg_lead(lead: Lead):
    if not settings.bot_token or settings.bot_token == "test":
        return
    age_label = "Взрослый" if lead.age_group == "adult" else "Ребёнок"
    contact_labels = {"telegram": "Telegram", "phone": "Телефон", "email": "Email"}
    contact_label = contact_labels.get(lead.contact_type, lead.contact_type)
    text = (f"📋 *Новая заявка на пробное занятие*\n\n"
            f"👤 Имя: {lead.name}\n"
            f"🎾 Категория: {age_label}\n"
            f"📞 {contact_label}: {lead.contact_value}")

    chat_ids: set[str] = set()
    if settings.admin_chat_id:
        chat_ids.add(str(settings.admin_chat_id))
    if settings.admin_chat_ids:
        for cid in settings.admin_chat_ids.split(","):
            cid = cid.strip()
            if cid: chat_ids.add(cid)

    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        for chat_id in chat_ids:
            try:
                await client.post(url, json={
                    "chat_id": int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id,
                    "text": text, "parse_mode": "Markdown"
                })
            except Exception:
                pass


@router.post("")
async def create_lead(data: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(name=data.name, age_group=data.age_group,
                contact_type=data.contact_type, contact_value=data.contact_value)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    try:
        await _send_tg_lead(lead)
    except Exception:
        pass
    return {"ok": True, "id": lead.id}


@router.get("/admin")
async def get_leads(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).order_by(desc(Lead.created_at)).limit(200))
    return [
        {"id": l.id, "name": l.name, "age_group": l.age_group,
         "contact_type": l.contact_type, "contact_value": l.contact_value,
         "created_at": l.created_at.isoformat() if l.created_at else None}
        for l in result.scalars().all()
    ]
