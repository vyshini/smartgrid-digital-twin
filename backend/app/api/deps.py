"""Shared FastAPI dependencies: DB session, current-user resolution."""
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.domain.exceptions import InactiveUserError, InvalidTokenError, UserNotFoundError
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.user_repository import UserRepository

# HTTPBearer (not OAuth2PasswordBearer) because /auth/login accepts a JSON body,
# not the OAuth2 form-encoded password grant. In Swagger UI this shows a single
# "paste your token" field instead of a username/password form that would send
# the wrong content-type to /auth/login.
bearer_scheme = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidTokenError("Token missing subject claim")

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError("User associated with this token no longer exists")
    if not user.is_active:
        raise InactiveUserError("This account has been deactivated")
    return user