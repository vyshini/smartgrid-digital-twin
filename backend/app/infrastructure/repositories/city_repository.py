"""Repository for City / GridNode / TransmissionLine persistence."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.city import City, GridNode, TransmissionLine


class CityRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_all(self) -> list[City]:
        result = await self._session.execute(select(City).order_by(City.name))
        return list(result.scalars().all())

    async def get_by_id(self, city_id: int) -> City | None:
        return await self._session.get(City, city_id)

    async def get_by_name(self, name: str) -> City | None:
        result = await self._session.execute(select(City).where(City.name == name))
        return result.scalar_one_or_none()

    async def get_nodes_for_city(self, city_id: int) -> list[GridNode]:
        result = await self._session.execute(
            select(GridNode).where(GridNode.city_id == city_id).order_by(GridNode.node_code)
        )
        return list(result.scalars().all())

    async def get_transmission_lines_for_nodes(self, node_ids: list[int]) -> list[TransmissionLine]:
        if not node_ids:
            return []
        result = await self._session.execute(
            select(TransmissionLine).where(
                TransmissionLine.from_node_id.in_(node_ids) | TransmissionLine.to_node_id.in_(node_ids)
            )
        )
        return list(result.scalars().all())
