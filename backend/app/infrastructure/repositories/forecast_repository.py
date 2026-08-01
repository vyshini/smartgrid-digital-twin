"""Repository for ForecastHistory persistence — same minimal pattern as
optimization_repository.py."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.forecast import ForecastHistory


class ForecastRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, **fields) -> ForecastHistory:
        record = ForecastHistory(**fields)
        self._session.add(record)
        await self._session.flush()
        return record