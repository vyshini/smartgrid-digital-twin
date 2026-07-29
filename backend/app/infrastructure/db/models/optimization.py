"""
ORM model for optimization_history, matching Phase 1's
docs/database-schema.sql. `forecast_id` is a plain nullable BIGINT WITHOUT
an FK constraint for now — Phase 3's forecast_history table was designed
on paper but never actually migrated into this backend's Postgres database
(the trained LSTM models live as files in ml-training/, not wired into
this DB at all yet). Adding a real FK here would reference a table that
doesn't exist. This is a known gap to close once forecast_history gets
its own migration, not a design decision to leave permanently.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class OptimizationHistory(Base):
    __tablename__ = "optimization_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=True, index=True
    )  # NULL = national-level run (not yet implemented — see Phase 1 scope)
    forecast_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # see module docstring
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False, default="QAOA-COBYLA")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    optimization_score: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    cost_reduction_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    power_loss_reduction_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    grid_stability_score: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    quantum_circuit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    # objective_gap and matched_classical_optimum aren't in Phase 1's original
    # schema — added here since the real 8-city validation run showed these
    # are essential for honestly reporting a QAOA result (see project
    # history: distinguishing a real optimum match from a 349-unit gap is
    # exactly the kind of thing a dashboard showing only optimization_score
    # would otherwise hide).
    objective_gap: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)
    matched_classical_optimum: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)