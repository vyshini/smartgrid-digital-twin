# Backend — Phase 2

FastAPI + PostgreSQL backend implementing: JWT authentication with RBAC
(admin / grid_operator / engineer / researcher), and read APIs for cities,
grid nodes, and transmission lines. Built on Clean Architecture per
`docs/architecture.md` from Phase 1.

## Setup

**Database driver note**: this project uses `psycopg[binary,pool]` (Psycopg 3),
not `asyncpg`. `psycopg[binary]` ships prebuilt wheels for Windows/macOS/Linux
across current Python versions, which avoids the "Microsoft Visual C++ 14.0
required" build failure asyncpg can hit on Windows when no matching wheel
exists for your exact Python version.

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set JWT_SECRET_KEY to a real random value, point DATABASE_URL at your Postgres instance
# (DATABASE_URL can be a plain postgresql:// URL — app/core/config.py rewrites it to
# postgresql+psycopg:// automatically for the async engine)

# Postgres must be running and reachable at DATABASE_URL, then:
alembic upgrade head    # creates schema + seeds the 8 cities
```

## Run

```bash
uvicorn app.main:app --reload
# API docs: http://localhost:8000/api/v1/docs
```

## Test

```bash
pytest                  # unit + integration tests, runs against in-memory SQLite — no Postgres needed
pytest --cov=app        # with coverage
```

**Note on test scope**: tests run against SQLite for speed and zero external
dependencies. Postgres-only features (native ENUM types, `GENERATED ALWAYS`
computed columns) are defined in the raw-SQL Alembic migration and are not
exercised by these tests — they get validated against real Postgres in CI
(Phase 6). ORM models deliberately use portable types (`sa.Uuid`, `sa.JSON`,
`sa.Enum` with `create_type=False`) so the same model code runs correctly
against both.

## Creating the first admin user

`/auth/register` requires an existing admin caller (by design — roles are
assigned deliberately, not self-selected). Bootstrap the very first admin
directly against the database:

```python
# one-off script, run once after `alembic upgrade head`
import asyncio
from app.core.security import hash_password
from app.infrastructure.db.models.enums import UserRole
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        session.add(User(
            username="admin", email="admin@smartgrid.in",
            password_hash=hash_password("change-me-immediately"),
            full_name="System Administrator", role=UserRole.ADMIN,
        ))
        await session.commit()

asyncio.run(main())
```

## What's implemented (Phase 2 scope)

- JWT auth: register (admin-only), login, refresh, logout, `/me`
- RBAC dependency (`require_roles`) enforced per-route
- Cities: list, detail (with grid nodes + transmission lines), nodes-only view
- Domain layer: `City`, `GridNode`, `TransmissionLine`, `Battery`,
  `GenerationMix`, `LoadProfile` — framework-free, self-validating entities
- Repository pattern isolating all SQL from use-cases
- Alembic migration seeding the 8 cities from Phase 1
- 20 automated tests (unit: domain rules + security; integration: use-cases,
  repositories, full HTTP request/response cycle via ASGI transport)

## What's deliberately deferred to later phases

- `forecast_history`, `ml_models` tables/endpoints → Phase 3 (LSTM)
- `optimization_history` table/endpoints → Phase 4 (QAOA)
- `simulation_scenarios`, `simulation_history`, WebSocket tick stream → Phase 4/5
- `alerts`, `reports` endpoints → Phase 6 wiring
- Dashboard `/overview` endpoint is intentionally NOT built yet — it needs
  forecast + optimization scores that don't exist until Phase 3/4, and a
  placeholder would violate the "no placeholder code" requirement.
- Dockerfile / docker-compose → Phase 6
