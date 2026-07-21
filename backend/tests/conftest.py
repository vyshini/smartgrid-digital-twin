import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import *  # noqa: F401,F403 registers all models


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """
    In-memory SQLite for fast unit/integration tests. Postgres-only features used
    in production (GENERATED ALWAYS columns, native ENUM types) are exercised
    separately against real Postgres in CI (see .github/workflows/backend-ci.yml,
    Phase 6) — this fixture is for repository/use-case logic, not schema fidelity.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
