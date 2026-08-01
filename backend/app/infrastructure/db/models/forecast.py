"""
ORM model for forecast_history — closes the gap flagged in optimization.py's
docstring: forecast_id existed as a column with nowhere real to point.
Every forecast call the optimization pipeline makes (not manual overrides)
now gets persisted here, so an OptimizationHistory row's forecast_id is a
real, followable reference instead of always null.
"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ForecastHistory(Base):
    __tablename__ = "forecast_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    horizon: Mapped[str] = mapped_column(String(20), nullable=False)  # "next_day" | "next_week"
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())