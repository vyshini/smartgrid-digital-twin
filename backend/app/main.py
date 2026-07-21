"""
FastAPI application entrypoint. Run with:
    uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, cities
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.api.v1 import auth, cities, forecast
from app.api.v1 import forecast as forecast_router

settings = get_settings()
configure_logging(debug=settings.DEBUG)
logger = get_logger("app.main")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.2.0",
        description=(
            "Digital Twin backend for Indian Smart Grid load forecasting and "
            "optimization — Phase 2: auth, city/grid models."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(cities.router, prefix=settings.API_V1_PREFIX)
    app.include_router(forecast.router, prefix=f"{settings.API_V1_PREFIX}/forecast", tags=["forecast"])
    app.include_router(forecast_router.router, prefix="/api/v1/forecast", tags=["forecast"])
    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    logger.info("application_startup", environment=settings.ENVIRONMENT)
    return app


app = create_app()
