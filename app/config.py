import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str = "test"
    admin_chat_id: int = 0
    admin_chat_ids: str = ""

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
            object.__setattr__(self, "database_url", url.replace("postgresql://", "postgresql+asyncpg://", 1))
        elif url.startswith("postgres://"):
            object.__setattr__(self, "database_url", url.replace("postgres://", "postgresql+asyncpg://", 1))


settings = Settings()
