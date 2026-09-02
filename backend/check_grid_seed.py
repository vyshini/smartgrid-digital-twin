"""
Quick check: were grid_nodes / transmission_lines ever seeded for any
city? Alembic's 0001_initial_schema.py seeds the 8 `cities` rows but
nothing seeds grid_nodes or transmission_lines -- those only get
populated today via ORM calls inside the test suite (see
tests/integration/test_cities.py's _seed_city_with_nodes), never against
the real database. This script checks the real DB directly.

Run from backend/:
    python check_grid_seed.py
"""
import asyncio

from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.city_repository import CityRepository


async def main() -> None:
    async with AsyncSessionLocal() as session:
        repo = CityRepository(session)
        cities = await repo.list_all()
        if not cities:
            print("No cities found at all -- did you run 'alembic upgrade head'?")
            return

        total_nodes = 0
        for city in cities:
            nodes = await repo.get_nodes_for_city(city.id)
            total_nodes += len(nodes)
            print(f"  {city.name:12s} (id={city.id}): {len(nodes)} grid nodes")

        print(f"\nTotal grid nodes across all 8 cities: {total_nodes}")
        if total_nodes == 0:
            print("CONFIRMED: no grid topology seeded. City Digital Twin tab will be empty for every city.")


if __name__ == "__main__":
    asyncio.run(main())