"""
Time-series ORM models. Each table shares the (city_id, recorded_at) unique
constraint and descending index pattern established in docs/database-schema.sql.
These are consumed starting Phase 3 (feature pipeline) but modeled now so the
schema and ORM layer stay in lockstep from day one.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class WeatherReading(Base):
    __tablename__ = "weather_readings"
    __table_args__ = (UniqueConstraint("city_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_c: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    wind_speed_kmph: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    solar_irradiance: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    precipitation_mm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    condition: Mapped[str] = mapped_column(String(50), nullable=False)
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_festival: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PowerGeneration(Base):
    __tablename__ = "power_generation"
    __table_args__ = (UniqueConstraint("city_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    solar_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    wind_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    hydro_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    coal_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    gas_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    nuclear_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # total_mw is a Postgres GENERATED ALWAYS column — read-only, computed by the DB.


class Renewables(Base):
    __tablename__ = "renewables"
    __table_args__ = (UniqueConstraint("city_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    solar_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    wind_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    hydro_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    solar_utilization_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    wind_utilization_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    hydro_utilization_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class BatteryStorage(Base):
    __tablename__ = "battery_storage"
    __table_args__ = (UniqueConstraint("city_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity_mwh: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_charge_mwh: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    charge_rate_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discharge_rate_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # soc_pct is a Postgres GENERATED ALWAYS column — read-only, computed by the DB.
    health_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=100)


class LoadDemand(Base):
    __tablename__ = "load_demand"
    __table_args__ = (UniqueConstraint("city_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    residential_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    commercial_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    industrial_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    ev_charging_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # total_mw is a Postgres GENERATED ALWAYS column — read-only, computed by the DB.
