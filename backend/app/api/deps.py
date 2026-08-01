"""Shared FastAPI dependencies: DB session, current-user resolution."""
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.domain.exceptions import InactiveUserError, InvalidTokenError, UserNotFoundError
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.user_repository import UserRepository

# auto_error=False: HTTPBearer's own default (auto_error=True) raises 403
# when the Authorization header is entirely missing — REST convention says
# 401 for "no credentials provided" (403 should mean "identified, but not
# permitted"). Handling the missing-credentials case ourselves via
# InvalidTokenError (already mapped to 401 in core/exceptions.py) keeps
# this consistent with every other auth-failure response this API returns.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise InvalidTokenError("Missing bearer token")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidTokenError("Token missing subject claim")

    repo = UserRepository(session)
    # user_id comes out of the JWT as a plain string (JSON has no UUID
    # type) — must be converted back to uuid.UUID before hitting a column
    # typed Uuid(as_uuid=True). Postgres/psycopg silently tolerates the
    # raw string via implicit casting, which is why this only ever
    # surfaced against SQLite (see tests/conftest.py) — a real latent bug
    # that manual Postgres-backed testing couldn't have caught.
    user = await repo.get_by_id(uuid.UUID(user_id))
    if user is None:
        raise UserNotFoundError("User associated with this token no longer exists")
    if not user.is_active:
        raise InactiveUserError("This account has been deactivated")
    return user