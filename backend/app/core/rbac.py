"""
Role-based access control. Routes declare the roles allowed via
`Depends(require_roles(...))`, keeping authorization checks declarative
and out of business logic.
"""
from collections.abc import Callable

from fastapi import Depends

from app.api.deps import get_current_user
from app.domain.exceptions import InsufficientPermissionError
from app.infrastructure.db.models.enums import UserRole
from app.infrastructure.db.models.user import User


def require_roles(*allowed_roles: UserRole) -> Callable:
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in {role.value for role in allowed_roles}:
            raise InsufficientPermissionError(
                f"Role '{current_user.role}' is not permitted to perform this action"
            )
        return current_user

    return dependency


# Convenience aliases matching the RBAC matrix defined in docs/api-spec.md
require_admin = require_roles(UserRole.ADMIN)
require_grid_operator_or_above = require_roles(UserRole.ADMIN, UserRole.GRID_OPERATOR)
require_engineer_or_above = require_roles(UserRole.ADMIN, UserRole.GRID_OPERATOR, UserRole.ENGINEER)
# All four roles can read — used for endpoints open to `researcher` too.
require_any_authenticated_role = require_roles(
    UserRole.ADMIN, UserRole.GRID_OPERATOR, UserRole.ENGINEER, UserRole.RESEARCHER
)
