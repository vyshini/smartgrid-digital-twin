"""Add optimization_history table (Phase 4: QAOA dispatch optimization)

forecast_id is intentionally NOT a foreign key here — forecast_history was
designed in Phase 1's docs/database-schema.sql but never actually migrated
into this database (Phase 3's LSTM models live as files in ml-training/,
not wired into Postgres). A real FK constraint gets added in a future
migration once that table exists, not invented here against a table that
isn't there.

objective_gap and matched_classical_optimum are additions beyond Phase 1's
original schema — added because a real 8-city validation run showed these
are essential for honestly reporting a QAOA result (see optimization.py's
ORM model docstring).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE optimization_history (
    id                          BIGSERIAL PRIMARY KEY,
    city_id                     INTEGER REFERENCES cities(id) ON DELETE CASCADE,
    forecast_id                 BIGINT,
    algorithm                   VARCHAR(50) NOT NULL DEFAULT 'QAOA-COBYLA',
    run_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    iterations                  INTEGER NOT NULL,
    optimization_score          NUMERIC(6,3) NOT NULL,
    cost_reduction_pct          NUMERIC(5,2),
    power_loss_reduction_pct    NUMERIC(5,2),
    grid_stability_score        NUMERIC(6,3),
    quantum_circuit_depth       INTEGER,
    execution_time_ms           INTEGER NOT NULL,
    allocation_result           JSONB NOT NULL,
    objective_gap               NUMERIC(12,4) NOT NULL DEFAULT 0.0,
    matched_classical_optimum   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_optimization_city_time ON optimization_history(city_id, run_at DESC);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS optimization_history;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)