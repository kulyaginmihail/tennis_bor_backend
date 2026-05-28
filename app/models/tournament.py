from sqlalchemy import String, Boolean, DateTime, Integer, Text, Float, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base
import enum


class TournamentStatus(str, enum.Enum):
    upcoming = "upcoming"
    open = "open"
    live = "live"
    past = "past"


class TournamentSport(str, enum.Enum):
    padel = "padel"
    tennis = "tennis"


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sport: Mapped[TournamentSport] = mapped_column(Enum(TournamentSport), default=TournamentSport.padel)
    status: Mapped[TournamentStatus] = mapped_column(Enum(TournamentStatus), default=TournamentStatus.upcoming)

    play_date: Mapped[str] = mapped_column(String(64))
    format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_fee: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(Integer)
    user_name: Mapped[str] = mapped_column(String(128), default="Игрок")
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TournamentRegistration(Base):
    """Заявки на турнир через лид-форму (без авторизации)."""
    __tablename__ = "tournament_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer)
    tournament_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    contact: Mapped[str] = mapped_column(String(128))   # телефон или @username
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(128), default="Администратор")
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
