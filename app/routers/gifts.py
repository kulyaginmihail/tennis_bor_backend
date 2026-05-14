import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

from app.database import get_db
from app.models.gift import GiftCertificate
from app.config import settings

router = APIRouter(prefix="/api/gifts", tags=["gifts"])


class GiftCreate(BaseModel):
    name: str
    amount: int
    contact_type: str    # telegram | phone
    contact_value: str
    comment: Optional[str] = None


async def _send_tg_gift(gift: GiftCertificate):
    if not settings.bot_token or settings.bot_token == "test":
        return
    contact_labels = {"telegram": "Telegram", "phone": "Телефон"}
    contact_label = contact_labels.get(gift.contact_type, gift.contact_type)
    comment_line = f"\n💬 Кому дарим: {gift.comment}" if gift.comment else ""
    text = (f"🎁 *Заявка на подарочный сертификат*\n\n"
            f"👤 Имя: {gift.name}\n"
            f"💰 Сумма: {gift.amount:,} ₽\n"
            f"📞 {contact_label}: {gift.contact_value}"
            f"{comment_line}")

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
async def create_gift(data: GiftCreate, db: AsyncSession = Depends(get_db)):
    gift = GiftCertificate(name=data.name, amount=data.amount,
                           contact_type=data.contact_type, contact_value=data.contact_value, comment=data.comment)
    db.add(gift)
    await db.commit()
    await db.refresh(gift)
    try:
        await _send_tg_gift(gift)
    except Exception:
        pass
    return {"ok": True, "id": gift.id}


@router.get("/admin")
async def get_gifts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GiftCertificate).order_by(desc(GiftCertificate.created_at)).limit(200))
    return [
        {"id": g.id, "name": g.name, "amount": g.amount,
         "contact_type": g.contact_type, "contact_value": g.contact_value,
         "comment": g.comment, "created_at": g.created_at.isoformat() if g.created_at else None}
        for g in result.scalars().all()
    ]
