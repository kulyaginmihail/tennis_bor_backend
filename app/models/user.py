from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram user_id
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="Игрок")
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ntrp_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferred_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    @property
    def display_name(self) -> str:
        name = self.first_name or ""
        if self.last_name:
            name += f" {self.last_name[0]}."
        return name.strip() or f"@{self.username}" if self.username else "Игрок"

    @property
    def tg_link(self) -> str | None:
        if self.username:
            return f"https://t.me/{self.username}"
        return None
