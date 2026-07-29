"""Repository for OptimizationHistory persistence — same pattern as city_repository.py."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.optimization import OptimizationHistory


class OptimizationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, **fields) -> OptimizationHistory:
        record = OptimizationHistory(**fields)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_latest_for_city(self, city_id: int) -> OptimizationHistory | None:
        result = await self._session.execute(
            select(OptimizationHistory)
            .where(OptimizationHistory.city_id == city_id)
            .order_by(OptimizationHistory.run_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history_for_city(self, city_id: int, limit: int = 50) -> list[OptimizationHistory]:
        result = await self._session.execute(
            select(OptimizationHistory)
            .where(OptimizationHistory.city_id == city_id)
            .order_by(OptimizationHistory.run_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(self, run_id: int) -> OptimizationHistory | None:
        return await self._session.get(OptimizationHistory, run_id)