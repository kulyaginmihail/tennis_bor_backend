import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": "require"},
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
AsyncSessionFactory = AsyncSessionLocal


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    # Retry — Railway иногда поднимает Postgres медленнее чем web-сервис
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                from app.models import user, sparring, stats, tournament, lead, gift  # noqa
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt == max_attempts:
                raise
            wait = attempt * 2
            logger.warning(f"DB unavailable (attempt {attempt}/{max_attempts}), retry in {wait}s: {e}")
            await asyncio.sleep(wait)

    migrations = [
        # Make nullable columns safe
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_name='matches' AND column_name='organizer_id' AND is_nullable='NO') THEN
                ALTER TABLE matches ALTER COLUMN organizer_id DROP NOT NULL;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_name='sparring_requests' AND column_name='user_id' AND is_nullable='NO') THEN
                ALTER TABLE sparring_requests ALTER COLUMN user_id DROP NOT NULL;
            END IF;
        END $$;
        """,
        # Add user profile columns
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='ntrp_level') THEN
                ALTER TABLE users ADD COLUMN ntrp_level VARCHAR(16);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='photo_url') THEN
                ALTER TABLE users ADD COLUMN photo_url VARCHAR(512);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='preferred_format') THEN
                ALTER TABLE users ADD COLUMN preferred_format VARCHAR(16) DEFAULT 'single';
            END IF;
        END $$;
        """,
        # Add score columns to matches
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='matches' AND column_name='score') THEN
                ALTER TABLE matches ADD COLUMN score VARCHAR(64);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='matches' AND column_name='score_status') THEN
                ALTER TABLE matches ADD COLUMN score_status VARCHAR(16);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='match_participants' AND column_name='score_confirmed') THEN
                ALTER TABLE match_participants ADD COLUMN score_confirmed BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='match_participants' AND column_name='team') THEN
                ALTER TABLE match_participants ADD COLUMN team VARCHAR(1);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='matches' AND column_name='score_winner') THEN
                ALTER TABLE matches ADD COLUMN score_winner VARCHAR(20);
            END IF;
        END $$;
        """,
        # Add matches_created to user_stats
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_stats' AND column_name='matches_created') THEN
                ALTER TABLE user_stats ADD COLUMN matches_created INTEGER NOT NULL DEFAULT 0;
            END IF;
        END $$;
        """,
    ]

    for sql in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception as e:
            print(f"[migration] warning: {e}")
