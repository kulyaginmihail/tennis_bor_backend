from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import os

from app.config import settings
from app.database import init_db
from app.routers import auth, sparring, tournaments, leads, gifts, admin
from app.routers.stats import router as stats_router
from app.routers.profile import router as profile_router
from app.routers.events import router as events_router
from app.bot import setup_bot, handle_update

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _background_startup():
    """DB init + bot setup в фоне — не блокирует healthcheck."""
    try:
        await init_db()
        print("✅ БОР — база данных инициализирована")
        await setup_bot(settings.base_url)
    except Exception as e:
        print(f"❌ Startup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.join(BASE_DIR, "admin"), exist_ok=True)
    # Запускаем в фоне — сервер сразу принимает запросы и проходит healthcheck
    asyncio.create_task(_background_startup())
    yield
    print("👋 Сервер остановлен")


app = FastAPI(title="Падел-Теннис БОР API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

admin_dir = os.path.join(BASE_DIR, "admin")
if os.path.isdir(admin_dir):
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")

app.include_router(auth.router)
app.include_router(sparring.router)
app.include_router(tournaments.router)
app.include_router(leads.router)
app.include_router(gifts.router)
app.include_router(admin.router)
app.include_router(stats_router)
app.include_router(profile_router)
app.include_router(events_router)


@app.get("/")
async def root():
    return {"service": "Падел-Теннис БОР API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/bot/webhook/{token}")
async def bot_webhook(token: str, request: Request):
    if token != settings.bot_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    update = await request.json()
    await handle_update(update)
    return {"ok": True}
