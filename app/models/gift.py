from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class GiftCertificate(Base):
    __tablename__ = "gift_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    amount: Mapped[int] = mapped_column(Integer)
    contact_type: Mapped[str] = mapped_column(String(16))  # telegram | phone
    contact_value: Mapped[str] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
