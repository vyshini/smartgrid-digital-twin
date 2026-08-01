"""Use-case: authenticate a user and issue access + refresh tokens."""
import hashlib
import uuid
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.user_repository import UserRepository


def _hash_token(token: str) -> str:
    # Refresh tokens are stored hashed (never plaintext) so a DB leak doesn't
    # directly hand out valid session tokens.
    return hashlib.sha256(token.encode()).hexdigest()


class LoginUseCase:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def execute(self, *, username: str, password: str) -> tuple[User, str, str]:
        user = await self._users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Incorrect username or password")
        if not user.is_active:
            raise InactiveUserError("This account has been deactivated")

        access_token = create_access_token(subject=user.id, role=user.role)
        refresh_token, expires_at = create_refresh_token(subject=user.id)
        await self._users.store_refresh_token(
            user_id=user.id, token_hash=_hash_token(refresh_token), expires_at=expires_at
        )
        return user, access_token, refresh_token


class RefreshTokenUseCase:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def execute(self, *, refresh_token: str) -> str:
        payload = decode_token(refresh_token, expected_type="refresh")
        token_hash = _hash_token(refresh_token)

        stored = await self._users.get_refresh_token(token_hash)
        if stored is None:
            raise InvalidCredentialsError("Refresh token is invalid, expired, or already revoked")

        user = await self._users.get_by_id(uuid.UUID(payload["sub"])) 
        if user is None or not user.is_active:
            raise InactiveUserError("This account is no longer active")

        return create_access_token(subject=user.id, role=user.role)


class LogoutUseCase:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def execute(self, *, refresh_token: str) -> None:
        await self._users.revoke_refresh_token(_hash_token(refresh_token))
