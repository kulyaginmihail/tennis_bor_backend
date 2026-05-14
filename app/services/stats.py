from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.stats import UserStats, UserAchievement, AchievementType, ACHIEVEMENT_META, ResultStatus, MatchResult
from app.models.sparring import Match, MatchParticipant, MatchStatus
from app.models.user import User


async def get_or_create_stats(user_id: int, db: AsyncSession) -> UserStats:
    res = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    stats = res.scalar_one_or_none()
    if not stats:
        stats = UserStats(user_id=user_id)
        db.add(stats)
        await db.flush()
    return stats


def _update_streak(stats: UserStats, match_date: datetime) -> None:
    now = match_date.date()
    if stats.last_match_date is None:
        stats.current_streak = 1
    else:
        last = stats.last_match_date.date()
        delta = (now - last).days
        if delta == 0:
            pass
        elif delta == 1:
            stats.current_streak += 1
        else:
            stats.current_streak = 1
    stats.longest_streak = max(stats.longest_streak, stats.current_streak)
    stats.last_match_date = match_date


def _update_elo(winner_stats: UserStats, loser_stats: UserStats) -> None:
    K = 20
    expected_w = 1 / (1 + 10 ** ((loser_stats.rating_points - winner_stats.rating_points) / 400))
    delta = round(K * (1 - expected_w))
    winner_stats.rating_points += delta
    loser_stats.rating_points = max(800, loser_stats.rating_points - delta)


async def check_achievements(user_id: int, stats: UserStats, db: AsyncSession) -> list[AchievementType]:
    res = await db.execute(select(UserAchievement.achievement).where(UserAchievement.user_id == user_id))
    earned = set(res.scalars().all())

    candidates: list[AchievementType] = []

    def maybe(ach: AchievementType, condition: bool):
        if condition and ach not in earned:
            candidates.append(ach)

    maybe(AchievementType.first_match, stats.matches_total >= 1)
    maybe(AchievementType.wins_10,     stats.matches_won   >= 10)
    maybe(AchievementType.wins_25,     stats.matches_won   >= 25)
    maybe(AchievementType.matches_30,  stats.matches_total >= 30)
    maybe(AchievementType.streak_7,    stats.current_streak >= 7)
    maybe(AchievementType.streak_30,   stats.current_streak >= 30)
    maybe(AchievementType.organizer,   stats.matches_created >= 1)

    top3_res = await db.execute(
        select(UserStats.user_id)
        .order_by(desc(UserStats.monthly_wins), desc(UserStats.rating_points))
        .limit(3)
    )
    top3_ids = [r[0] for r in top3_res.all()]
    maybe(AchievementType.top3_rating, user_id in top3_ids and stats.matches_total > 0)

    for ach in candidates:
        db.add(UserAchievement(user_id=user_id, achievement=ach))
    return candidates


async def apply_match_result(result_id: int, db: AsyncSession) -> dict:
    res = await db.execute(select(MatchResult).where(MatchResult.id == result_id))
    result = res.scalar_one_or_none()
    if not result or result.status == ResultStatus.confirmed:
        return {}

    now = datetime.now(timezone.utc)
    result.status = ResultStatus.confirmed
    result.confirmed_at = now

    match_res = await db.execute(select(Match).where(Match.id == result.match_id))
    match = match_res.scalar_one_or_none()
    if match:
        match.status = MatchStatus.played

    winner_id = result.winner_id
    loser_id = result.loser_id
    if not winner_id or not loser_id:
        await db.flush()
        return {}

    w_stats = await get_or_create_stats(winner_id, db)
    w_stats.matches_total += 1
    w_stats.matches_won += 1
    w_stats.monthly_wins += 1
    w_stats.monthly_matches += 1
    _update_streak(w_stats, now)

    l_stats = await get_or_create_stats(loser_id, db)
    l_stats.matches_total += 1
    l_stats.matches_lost += 1
    l_stats.monthly_matches += 1
    _update_streak(l_stats, now)

    _update_elo(w_stats, l_stats)
    await db.flush()

    w_achs = await check_achievements(winner_id, w_stats, db)
    l_achs = await check_achievements(loser_id, l_stats, db)
    await db.flush()

    return {
        "winner_id": winner_id, "loser_id": loser_id,
        "winner_new_achievements": w_achs, "loser_new_achievements": l_achs,
        "winner_stats": {"matches_total": w_stats.matches_total, "matches_won": w_stats.matches_won,
                         "current_streak": w_stats.current_streak, "rating_points": w_stats.rating_points,
                         "level": w_stats.level_label},
        "loser_stats":  {"matches_total": l_stats.matches_total, "matches_won": l_stats.matches_won,
                         "current_streak": l_stats.current_streak, "rating_points": l_stats.rating_points,
                         "level": l_stats.level_label},
    }


async def _recent_matches(user_id: int, db: AsyncSession) -> list[dict]:
    history = []
    org = await db.execute(
        select(Match).where(
            Match.organizer_id == user_id, Match.status == MatchStatus.played, Match.score_winner.isnot(None)
        ).order_by(desc(Match.play_date)).limit(10)
    )
    for m in org.scalars().all():
        is_win = m.score_winner in ("organizer", "A")
        pts = await db.execute(select(MatchParticipant).where(MatchParticipant.match_id == m.id).limit(1))
        opp = pts.scalar_one_or_none()
        history.append({"is_win": is_win, "date": m.play_date.isoformat(),
                        "opponent": opp.user_name if opp else "Соперник",
                        "format": m.format.value if hasattr(m.format, "value") else str(m.format),
                        "score": m.score or "—"})

    parts = await db.execute(select(MatchParticipant).where(MatchParticipant.user_id == user_id))
    for p in parts.scalars().all():
        mr = await db.execute(select(Match).where(Match.id == p.match_id, Match.status == MatchStatus.played, Match.score_winner.isnot(None)))
        m = mr.scalar_one_or_none()
        if not m:
            continue
        if m.score_winner == "participant":
            is_win = True
        elif m.score_winner == "organizer":
            is_win = False
        elif m.score_winner in ("A", "B") and p.team:
            is_win = (m.score_winner == p.team)
        else:
            continue
        history.append({"is_win": is_win, "date": m.play_date.isoformat(),
                        "opponent": m.organizer_name,
                        "format": m.format.value if hasattr(m.format, "value") else str(m.format),
                        "score": m.score or "—"})

    history.sort(key=lambda x: x["date"], reverse=True)
    return history[:5]


async def get_player_profile(user_id: int, db: AsyncSession) -> dict | None:
    u_res = await db.execute(select(User).where(User.id == user_id))
    user = u_res.scalar_one_or_none()
    if not user:
        return None

    stats = await get_or_create_stats(user_id, db)

    ach_res = await db.execute(select(UserAchievement).where(UserAchievement.user_id == user_id))
    achievements = ach_res.scalars().all()
    ach_list = [
        {"key": a.achievement.value, "icon": ACHIEVEMENT_META[a.achievement]["icon"],
         "label": ACHIEVEMENT_META[a.achievement]["label"], "earned_at": a.earned_at.isoformat()}
        for a in achievements
    ]

    first = user.first_name or ""
    last = user.last_name or ""

    return {
        "user_id": user.id,
        "name": user.display_name,
        "username": user.username,
        "initials": ((first[0] if first else "") + (last[0] if last else "")).upper() or "?",
        "photo_url": user.photo_url,
        "ntrp_level": user.ntrp_level,
        "wins": stats.matches_won,
        "matches": stats.matches_total,
        "losses": stats.matches_lost,
        "streak": stats.current_streak,
        "longest_streak": stats.longest_streak,
        "rating_points": stats.rating_points,
        "win_rate": stats.win_rate,
        "level": stats.level_label,
        "level_progress": stats.level_progress_pct,
        "monthly_wins": stats.monthly_wins,
        "monthly_matches": stats.monthly_matches,
        "achievements": ach_list,
        "recent_matches": await _recent_matches(user_id, db),
    }


async def get_leaderboard(limit: int, db: AsyncSession) -> list[dict]:
    q = (
        select(UserStats, User)
        .join(User, User.id == UserStats.user_id)
        .order_by(desc(UserStats.monthly_wins), desc(UserStats.rating_points))
        .limit(limit)
    )
    res = await db.execute(q)
    return [
        {
            "user_id": stats.user_id, "name": user.display_name,
            "first_name": user.first_name, "last_name": user.last_name,
            "username": user.username,
            "wins": stats.monthly_wins, "matches": stats.monthly_matches,
            "rating": stats.rating_points, "level": stats.level_label,
            "streak": stats.current_streak,
        }
        for stats, user in res.all()
    ]
