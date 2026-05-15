from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HomeEvent(Base):
    __tablename__ = "home_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120))
    subtitle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="default")  # lime | default | cream
    link_to: Mapped[str | None] = mapped_column(String(60), nullable=True)  # sparring | tournaments | prices | coaches
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
