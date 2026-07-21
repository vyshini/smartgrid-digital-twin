"""
Domain-level exceptions. These carry no HTTP knowledge — the API layer
(app/core/exceptions.py exception handlers) translates them into responses.
"""


class DomainError(Exception):
    """Base class for all domain/business-rule violations."""

    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidCredentialsError(DomainError):
    code = "INVALID_CREDENTIALS"


class InvalidTokenError(DomainError):
    code = "INVALID_TOKEN"


class UserAlreadyExistsError(DomainError):
    code = "USER_ALREADY_EXISTS"


class UserNotFoundError(DomainError):
    code = "USER_NOT_FOUND"


class InactiveUserError(DomainError):
    code = "INACTIVE_USER"


class CityNotFoundError(DomainError):
    code = "CITY_NOT_FOUND"


class GridNodeNotFoundError(DomainError):
    code = "GRID_NODE_NOT_FOUND"


class InsufficientPermissionError(DomainError):
    code = "INSUFFICIENT_PERMISSION"


class InvalidGridStateError(DomainError):
    """Raised when a battery/generation/transmission value violates a physical bound."""

    code = "INVALID_GRID_STATE"
