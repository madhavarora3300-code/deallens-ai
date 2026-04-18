from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from core.config import settings
import os

# Get DATABASE_URL and ensure it uses asyncpg
database_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Convert postgresql:// to postgresql+asyncpg:// if needed
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine — used by FastAPI web tier only (persistent pool, loop-bound)
engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Async session factory — for FastAPI web tier only
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def make_task_session_factory():
    """
    Create a fresh async engine + session factory using NullPool.

    NullPool opens a brand-new connection for every session and closes it when
    the session exits — no connection is ever reused across event loops.
    Call this INSIDE the async function that runs under asyncio.run() in a
    Celery task, NOT at module level.  Each asyncio.run() creates a new loop;
    NullPool ensures no asyncpg connection from a previous loop leaks in.
    """
    task_engine = create_async_engine(database_url, poolclass=NullPool)
    return async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
