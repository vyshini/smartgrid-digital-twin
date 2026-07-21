"""Use-case: register a new user. Only callable by admins (enforced at the route)."""
from app.core.security import hash_password
from app.domain.exceptions import UserAlreadyExistsError
from app.infrastructure.db.models.enums import UserRole
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.user_repository import UserRepository


class RegisterUserUseCase:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def execute(
        self, *, username: str, email: str, password: str, full_name: str, role: UserRole
    ) -> User:
        if await self._users.get_by_username(username) is not None:
            raise UserAlreadyExistsError(f"Username '{username}' is already taken")
        if await self._users.get_by_email(email) is not None:
            raise UserAlreadyExistsError(f"Email '{email}' is already registered")

        return await self._users.create(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
        )
