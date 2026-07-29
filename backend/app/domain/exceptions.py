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


class CityNotSupportedForOptimizationError(CityNotFoundError):
    """Raised when a city exists in the DB but has no real capacity data
    in generation_capacity.py (currently only the original 8 seeded cities
    are supported — see Phase 1 scope)."""

    code = "CITY_NOT_SUPPORTED_FOR_OPTIMIZATION"


class GridNodeNotFoundError(DomainError):
    code = "GRID_NODE_NOT_FOUND"


class InsufficientPermissionError(DomainError):
    code = "INSUFFICIENT_PERMISSION"


class InvalidGridStateError(DomainError):
    """Raised when a battery/generation/transmission value violates a physical bound."""

    code = "INVALID_GRID_STATE"


class OptimizationJobNotFoundError(DomainError):
    code = "OPTIMIZATION_JOB_NOT_FOUND"


class OptimizationRunNotFoundError(DomainError):
    code = "OPTIMIZATION_RUN_NOT_FOUND"