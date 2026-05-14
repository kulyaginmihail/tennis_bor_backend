from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, Float, ForeignKey, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database import Base
import enum


class ResultStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    disputed = "disputed"


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"))
    reported_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    loser_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    score_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_sets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ResultStatus] = mapped_column(Enum(ResultStatus), default=ResultStatus.pending)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)

    matches_total: Mapped[int] = mapped_column(Integer, default=0)
    matches_won: Mapped[int] = mapped_column(Integer, default=0)
    matches_lost: Mapped[int] = mapped_column(Integer, default=0)
    matches_created: Mapped[int] = mapped_column(Integer, default=0)

    sets_won: Mapped[int] = mapped_column(Integer, default=0)
    sets_lost: Mapped[int] = mapped_column(Integer, default=0)

    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rating_points: Mapped[int] = mapped_column(Integer, default=1000)

    monthly_wins: Mapped[int] = mapped_column(Integer, default=0)
    monthly_matches: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    @property
    def win_rate(self) -> float:
        if self.matches_total == 0:
            return 0.0
        return round(self.matches_won / self.matches_total * 100, 1)

    @property
    def level_label(self) -> str:
        r = self.rating_points
        if r < 1050:  return "Новичок"
        if r < 1150:  return "Любитель"
        if r < 1300:  return "Клубный"
        if r < 1500:  return "Разрядник"
        if r < 1700:  return "Мастер"
        return "Элита"

    @property
    def level_progress_pct(self) -> int:
        thresholds = [1000, 1050, 1150, 1300, 1500, 1700]
        r = self.rating_points
        for i in range(len(thresholds) - 1):
            lo, hi = thresholds[i], thresholds[i + 1]
            if lo <= r < hi:
                return int((r - lo) / (hi - lo) * 100)
        return 100


class AchievementType(str, enum.Enum):
    first_match  = "first_match"
    wins_10      = "wins_10"
    wins_25      = "wins_25"
    matches_30   = "matches_30"
    streak_7     = "streak_7"
    streak_30    = "streak_30"
    organizer    = "organizer"
    top3_rating  = "top3_rating"


ACHIEVEMENT_META = {
    AchievementType.first_match: {"icon": "🎾", "label": "Первый матч",    "desc": "Сыграл первый матч"},
    AchievementType.wins_10:     {"icon": "🏅", "label": "10 побед",       "desc": "10 побед в матчах"},
    AchievementType.wins_25:     {"icon": "🏆", "label": "25 побед",       "desc": "25 побед в матчах"},
    AchievementType.matches_30:  {"icon": "⚡", "label": "30 матчей",      "desc": "30 сыгранных матчей"},
    AchievementType.streak_7:    {"icon": "🔥", "label": "7 дней подряд",  "desc": "Активность 7 дней"},
    AchievementType.streak_30:   {"icon": "💎", "label": "30 дней подряд", "desc": "Активность 30 дней"},
    AchievementType.organizer:   {"icon": "🤝", "label": "Организатор",    "desc": "Создал свой матч"},
    AchievementType.top3_rating: {"icon": "👑", "label": "Топ-3 рейтинг",  "desc": "Топ-3 клубного рейтинга"},
}


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    achievement: Mapped[AchievementType] = mapped_column(Enum(AchievementType))
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
