"""
Telegram Bot для теннисного центра БОР.
Webhook-режим — интегрирован в FastAPI, работает на том же Railway-сервисе.
"""
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.bot_token}"
WEBAPP_URL = "https://tennis-bor-frontend.vercel.app"

WELCOME_TEXT = (
    "🎾 *Теннисный центр БОР*\n\n"
    "Добро пожаловать\\! Здесь всё для падела и тенниса в одном приложении\\.\n\n"
    "*Что вас ждёт:*\n"
    "🏆 Турниры по теннису и паделу\n"
    "🤝 Спарринги с игроками вашего уровня\n"
    "👨‍🏫 Запись к опытным тренерам\n"
    "📈 Личный рейтинг и статистика\n\n"
    "Нажмите кнопку ниже, чтобы открыть приложение 👇"
)


async def _post(method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{TELEGRAM_API}/{method}", json=payload)
        return r.json()


async def send_start_message(chat_id: int) -> None:
    await _post("sendMessage", {
        "chat_id": chat_id,
        "text": WELCOME_TEXT,
        "parse_mode": "MarkdownV2",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": "🎾 Открыть приложение",
                    "web_app": {"url": WEBAPP_URL},
                }
            ]]
        },
    })


async def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("channel_post")
    if not msg:
        return
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]
    if text.startswith("/start"):
        await send_start_message(chat_id)


async def setup_bot(base_url: str) -> None:
    """
    Вызывается при старте приложения.
    Регистрирует webhook, устанавливает кнопку меню, команды и описание бота.
    """
    if not settings.bot_token or settings.bot_token == "test":
        logger.warning("BOT_TOKEN не задан — бот не запущен")
        return

    webhook_url = f"{base_url}/bot/webhook/{settings.bot_token}"
    logger.info(f"Регистрация webhook: {webhook_url}")

    # 1. Webhook
    r = await _post("setWebhook", {
        "url": webhook_url,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    })
    logger.info(f"setWebhook → {r}")

    # 2. Кнопка меню (открывает Mini App прямо из чата)
    await _post("setChatMenuButton", {
        "menu_button": {
            "type": "web_app",
            "text": "🎾 Открыть",
            "web_app": {"url": WEBAPP_URL},
        }
    })

    # 3. Список команд
    await _post("setMyCommands", {
        "commands": [
            {"command": "start", "description": "Запустить бота"},
        ]
    })

    # 4. Описание (видно до первого сообщения)
    await _post("setMyDescription", {
        "description": (
            "Теннисный центр «БОР» — падел и теннис в одном месте.\n\n"
            "Спарринги, турниры, тренеры и ваш личный рейтинг — "
            "всё внутри приложения."
        )
    })

    # 5. Краткое описание (на странице профиля бота)
    await _post("setMyShortDescription", {
        "short_description": "Падел и теннис — спарринги, турниры, тренеры, рейтинг"
    })

    logger.info("✅ Бот настроен")
