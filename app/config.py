import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str = "test"
    admin_chat_id: int = 0
    admin_chat_ids: str = ""
    base_url: str = "https://web-production-a316a.up.railway.app"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bor"

    secret_key: str = "dev-secret-key-change-in-prod"
    admin_password: str = "admin123"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def model_post_init(self, __context):
        # Railway provides DATABASE_URL as postgresql:// — asyncpg needs postgresql+asyncpg://
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Запоминаем нужен ли SSL (для внешних подключений)
        # НЕ добавляем ?ssl=true в URL — это вызывает верификацию сертификата
        # SSL передаётся через connect_args в database.py
        is_external = (
            "railway.internal" not in url
            and "localhost" not in url
            and "127.0.0.1" not in url
        )
        object.__setattr__(self, "_needs_ssl", is_external)

        object.__setattr__(self, "database_url", url)


settings = Settings()
