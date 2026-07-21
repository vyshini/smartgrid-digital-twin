"""
Central mapping of domain exceptions -> HTTP responses.
Keeps API routers free of try/except boilerplate: routers just let domain
exceptions bubble up, and FastAPI's exception_handler machinery does the rest.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    CityNotFoundError,
    DomainError,
    GridNodeNotFoundError,
    InactiveUserError,
    InsufficientPermissionError,
    InvalidCredentialsError,
    InvalidGridStateError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)

logger = logging.getLogger("app.exceptions")

_STATUS_MAP: dict[type[DomainError], int] = {
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InvalidTokenError: status.HTTP_401_UNAUTHORIZED,
    InactiveUserError: status.HTTP_403_FORBIDDEN,
    InsufficientPermissionError: status.HTTP_403_FORBIDDEN,
    UserAlreadyExistsError: status.HTTP_409_CONFLICT,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    CityNotFoundError: status.HTTP_404_NOT_FOUND,
    GridNodeNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidGridStateError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _error_response(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message, "status": http_status}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        http_status = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        if http_status >= 500:
            logger.exception("Unhandled domain error", exc_info=exc)
        return _error_response(exc.code, exc.message, http_status)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return _error_response(
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
