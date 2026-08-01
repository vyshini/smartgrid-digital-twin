"""Repository for ForecastHistory persistence — same minimal pattern as
optimization_repository.py."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.forecast import ForecastHistory

from sqlalchemy import select

class ForecastRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, **fields) -> ForecastHistory:
        record = ForecastHistory(**fields)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_latest_for_city(self, city_id: int) -> ForecastHistory | None:
        result = await self._session.execute(
            select(ForecastHistory)
            .where(ForecastHistory.city_id == city_id)
            .order_by(ForecastHistory.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()