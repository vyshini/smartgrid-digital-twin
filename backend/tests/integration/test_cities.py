import pytest

from app.infrastructure.db.models.city import City, GridNode, TransmissionLine
from app.infrastructure.repositories.city_repository import CityRepository


async def _seed_city_with_nodes(session):
    city = City(name="Delhi", state="Delhi", latitude=28.6139, longitude=77.2090, population=32900000)
    session.add(city)
    await session.flush()

    node_a = GridNode(city_id=city.id, node_code="IN-DL-01", transmission_capacity_mw=5000)
    node_b = GridNode(city_id=city.id, node_code="IN-DL-02", transmission_capacity_mw=4000)
    session.add_all([node_a, node_b])
    await session.flush()

    line = TransmissionLine(
        from_node_id=node_a.id, to_node_id=node_b.id, capacity_mw=1000,
        current_load_mw=750, length_km=42.5,
    )
    session.add(line)
    await session.flush()
    return city, node_a, node_b, line


async def test_list_all_returns_seeded_cities(db_session):
    await _seed_city_with_nodes(db_session)
    await db_session.commit()

    repo = CityRepository(db_session)
    cities = await repo.list_all()
    assert len(cities) == 1
    assert cities[0].name == "Delhi"


async def test_get_nodes_for_city(db_session):
    city, node_a, node_b, _ = await _seed_city_with_nodes(db_session)
    await db_session.commit()

    repo = CityRepository(db_session)
    nodes = await repo.get_nodes_for_city(city.id)
    assert {n.node_code for n in nodes} == {"IN-DL-01", "IN-DL-02"}


async def test_get_transmission_lines_for_nodes(db_session):
    city, node_a, node_b, line = await _seed_city_with_nodes(db_session)
    await db_session.commit()

    repo = CityRepository(db_session)
    lines = await repo.get_transmission_lines_for_nodes([node_a.id, node_b.id])
    assert len(lines) == 1
    assert lines[0].current_load_mw == 750


async def test_get_by_id_missing_returns_none(db_session):
    repo = CityRepository(db_session)
    assert await repo.get_by_id(999) is None
