"""Repository for SimulationHistory persistence — same minimal pattern as
forecast_repository.py / optimization_repository.py."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.simulation import SimulationHistory


class SimulationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, **fields) -> SimulationHistory:
        record = SimulationHistory(**fields)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_history_for_city(self, city_id: int, limit: int = 50) -> list[SimulationHistory]:
        result = await self._session.execute(
            select(SimulationHistory)
            .where(SimulationHistory.city_id == city_id)
            .order_by(SimulationHistory.run_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())