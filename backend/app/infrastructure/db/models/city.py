from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.enums import LineStatus, NodeStatus


def _pg_enum(enum_cls, name: str):
    """
    Enum(..., create_type=False) binds to the Postgres enum type already created
    by the Alembic migration, and ensures the driver sends correctly-typed
    parameters rather than raw strings (a common driver + native-enum pitfall).
    On SQLite (unit tests) this degrades gracefully to a VARCHAR + CHECK constraint.
    """
    return Enum(enum_cls, name=name, create_type=False, values_callable=lambda e: [m.value for m in e])


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    population: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    grid_nodes: Mapped[list["GridNode"]] = relationship(back_populates="city", cascade="all, delete-orphan")


class GridNode(Base):
    __tablename__ = "grid_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    node_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    transmission_capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[NodeStatus] = mapped_column(
        _pg_enum(NodeStatus, "node_status"), nullable=False, default=NodeStatus.HEALTHY
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    city: Mapped["City"] = relationship(back_populates="grid_nodes")


class TransmissionLine(Base):
    __tablename__ = "transmission_lines"
    __table_args__ = (CheckConstraint("from_node_id <> to_node_id", name="chk_distinct_nodes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_node_id: Mapped[int] = mapped_column(
        ForeignKey("grid_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_node_id: Mapped[int] = mapped_column(
        ForeignKey("grid_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capacity_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_load_mw: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    length_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    loss_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    status: Mapped[LineStatus] = mapped_column(
        _pg_enum(LineStatus, "line_status"), nullable=False, default=LineStatus.ACTIVE
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
