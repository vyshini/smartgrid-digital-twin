from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.rbac import require_any_authenticated_role
from app.domain.exceptions import CityNotFoundError
from app.infrastructure.db.models.city import TransmissionLine
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.city_repository import CityRepository
from app.schemas.city_schemas import CityDetailOut, CityOut, GridNodeOut, TransmissionLineOut

router = APIRouter(prefix="/cities", tags=["cities"])


def _to_transmission_line_out(line: TransmissionLine) -> TransmissionLineOut:
    capacity = float(line.capacity_mw)
    current_load = float(line.current_load_mw)
    utilization_pct = 0.0 if capacity == 0 else round(100 * current_load / capacity, 2)
    return TransmissionLineOut(
        id=line.id,
        from_node_id=line.from_node_id,
        to_node_id=line.to_node_id,
        capacity_mw=capacity,
        current_load_mw=current_load,
        length_km=float(line.length_km),
        loss_pct=float(line.loss_pct),
        status=line.status,
        utilization_pct=utilization_pct,
    )


@router.get("", response_model=list[CityOut])
async def list_cities(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_any_authenticated_role),
) -> list[CityOut]:
    cities = await CityRepository(session).list_all()
    return [CityOut.model_validate(c) for c in cities]


@router.get("/{city_id}", response_model=CityDetailOut)
async def get_city(
    city_id: int,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_any_authenticated_role),
) -> CityDetailOut:
    repo = CityRepository(session)
    city = await repo.get_by_id(city_id)
    if city is None:
        raise CityNotFoundError(f"City with id {city_id} was not found")

    nodes = await repo.get_nodes_for_city(city_id)
    lines = await repo.get_transmission_lines_for_nodes([n.id for n in nodes])

    return CityDetailOut(
        city=CityOut.model_validate(city),
        grid_nodes=[GridNodeOut.model_validate(n) for n in nodes],
        transmission_lines=[_to_transmission_line_out(line) for line in lines],
    )


@router.get("/{city_id}/nodes", response_model=list[GridNodeOut])
async def get_city_nodes(
    city_id: int,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_any_authenticated_role),
) -> list[GridNodeOut]:
    repo = CityRepository(session)
    if await repo.get_by_id(city_id) is None:
        raise CityNotFoundError(f"City with id {city_id} was not found")
    nodes = await repo.get_nodes_for_city(city_id)
    return [GridNodeOut.model_validate(n) for n in nodes]

