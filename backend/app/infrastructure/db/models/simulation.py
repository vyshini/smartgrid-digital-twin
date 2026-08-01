"""
ORM model for simulation_history — persists both weather scenarios
(LSTM re-forecast) and generation scenarios (QAOA capacity override) under
one shared table, since both are conceptually "a simulation run" even
though their underlying mechanism differs (see simulation/scenarios.py and
simulation/generation_scenarios.py for why they're built differently).
`scenario_type` distinguishes which mechanism produced a given row.
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SimulationHistory(Base):
    __tablename__ = "simulation_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "weather" | "generation"
    scenario_key: Mapped[str] = mapped_column(String(100), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(200), nullable=False)
    as_of_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date, nullable for generation scenarios that may omit it
    result: Mapped[dict] = mapped_column(JSON, nullable=False)  # the full response dict already built by each endpoint
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())