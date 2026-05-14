from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.stats import get_player_profile, get_leaderboard, apply_match_result

router = APIRouter(tags=["stats"])


@router.get("/api/profile/{user_id}")
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    profile = await get_player_profile(user_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return profile


@router.get("/api/leaderboard")
async def leaderboard(limit: int = 10, db: AsyncSession = Depends(get_db)):
    return await get_leaderboard(limit, db)


@router.post("/api/stats/apply-result/{result_id}")
async def apply_result(result_id: int, db: AsyncSession = Depends(get_db)):
    result = await apply_match_result(result_id, db)
    await db.commit()
    return result or {"ok": True}
