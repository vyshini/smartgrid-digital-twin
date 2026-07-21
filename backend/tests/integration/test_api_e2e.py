"""
End-to-end tests hitting the actual FastAPI app (routers, DI, schemas) over
an in-process ASGI transport — the strongest signal that Phase 2's wiring is
correct, since it exercises the real dependency graph rather than calling
use-cases directly.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_session
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import *  # noqa: F401,F403
from app.infrastructure.db.models.city import City
from app.main import app


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    # Seed one city directly so /cities tests don't depend on Alembic seed data.
    async with session_factory() as session:
        session.add(City(name="Delhi", state="Delhi", latitude=28.6139, longitude=77.2090, population=32900000))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_list_cities_requires_auth(client):
    resp = await client.get("/api/v1/cities")
    assert resp.status_code == 401


async def test_register_requires_admin_role(client):
    # No token at all -> 401, not 403, since auth happens before role check.
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.in",
            "password": "password123",
            "full_name": "New User",
            "role": "researcher",
        },
    )
    assert resp.status_code == 401


async def test_login_with_nonexistent_user_returns_401(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "ghost", "password": "whatever"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_get_unknown_city_returns_404_with_valid_token(client):
    # Seed an admin user directly via the ORM (bypassing the admin-only register
    # endpoint, since no admin exists yet to call it) then log in through the real API.
    from app.core.security import hash_password
    from app.infrastructure.db.models.enums import UserRole
    from app.infrastructure.db.models.user import User as UserModel

    override = app.dependency_overrides[get_session]
    async for session in override():
        session.add(
            UserModel(
                username="admin_e2e",
                email="admin_e2e@example.in",
                password_hash=hash_password("adminpass1"),
                full_name="Admin E2E",
                role=UserRole.ADMIN,
            )
        )
        await session.commit()
        break

    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin_e2e", "password": "adminpass1"}
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/cities/999", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CITY_NOT_FOUND"


async def test_list_cities_with_valid_token_returns_seeded_city(client):
    from app.core.security import hash_password
    from app.infrastructure.db.models.enums import UserRole
    from app.infrastructure.db.models.user import User as UserModel

    override = app.dependency_overrides[get_session]
    async for session in override():
        session.add(
            UserModel(
                username="researcher_e2e",
                email="researcher_e2e@example.in",
                password_hash=hash_password("researchpass1"),
                full_name="Researcher E2E",
                role=UserRole.RESEARCHER,
            )
        )
        await session.commit()
        break

    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "researcher_e2e", "password": "researchpass1"}
    )
    access_token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/cities", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Delhi" in names
