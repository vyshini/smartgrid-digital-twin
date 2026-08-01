# backend/check_capacity.py — throwaway script, delete after
import asyncio
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.city_repository import CityRepository
from app.quantum.population_data import apportioned_city_capacity

async def main():
    async with AsyncSessionLocal() as session:
        city = await CityRepository(session).get_by_id(1)
        print("City:", city.name)

    cap = apportioned_city_capacity(city.name)
    print("Apportioned capacity:", cap)
    for s in ("coal", "hydro", "wind", "solar"):
        block = getattr(cap, f"{s}_mw")  # N_BLOCKS=1, so this IS the block size now
        print(f"  {s}_mw block size: {block:.1f} MW")

asyncio.run(main())