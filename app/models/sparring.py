from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Text, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from app.database import Base
import enum


class MatchFormat(str, enum.Enum):
    single = "single"
    double = "double"
    mixed = "mixed"


class MatchStatus(str, enum.Enum):
    open = "open"
    full = "full"
    played = "played"
    cancelled = "cancelled"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organizer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    organizer_name: Mapped[str] = mapped_column(String(128), default="Игрок")
    organizer_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    format: Mapped[MatchFormat] = mapped_column(Enum(MatchFormat), default=MatchFormat.single)
    status: Mapped[MatchStatus] = mapped_column(Enum(MatchStatus), default=MatchStatus.open)

    title: Mapped[str] = mapped_column(String(128), default="Матч")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    play_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_hours: Mapped[float] = mapped_column(Float, default=1.0)
    court: Mapped[str | None] = mapped_column(String(32), nullable=True)

    ntrp_min: Mapped[float] = mapped_column(Float, default=2.0)
    ntrp_max: Mapped[float] = mapped_column(Float, default=5.0)

    slots_total: Mapped[int] = mapped_column(Integer, default=2)
    slots_taken: Mapped[int] = mapped_column(Integer, default=1)

    score: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    score_winner: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    participants: Mapped[list["MatchParticipant"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(128), default="Игрок")
    user_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team: Mapped[str | None] = mapped_column(String(1), nullable=True)
    score_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    match: Mapped["Match"] = relationship(back_populates="participants")


class SparringRequest(Base):
    __tablename__ = "sparring_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(128), default="Игрок")
    user_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    format: Mapped[str] = mapped_column(String(16), default="single")
    ntrp_level: Mapped[str] = mapped_column(String(16), default="3.0")
    preferred_time: Mapped[str] = mapped_column(String(128), default="")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
