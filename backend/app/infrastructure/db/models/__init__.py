"""
Importing this module registers every ORM model against Base.metadata —
required for Alembic autogenerate to see the full schema. Tables not yet
backed by a repository (ml_models, forecast_history, optimization_history,
simulation_scenarios, simulation_history, alerts, reports) are added here in
Phase 3/4/6 as those layers are built; the SQL DDL in docs/database-schema.sql
already defines their final shape.
"""
from app.infrastructure.db.models.city import City, GridNode, TransmissionLine  # noqa: F401
from app.infrastructure.db.models.optimization import OptimizationHistory  # noqa: F401
from app.infrastructure.db.models.timeseries import (  # noqa: F401
    BatteryStorage,
    LoadDemand,
    PowerGeneration,
    Renewables,
    WeatherReading,
)
from app.infrastructure.db.models.user import AuditLog, RefreshToken, User  # noqa: F401