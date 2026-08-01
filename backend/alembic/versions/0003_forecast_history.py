"""Add forecast_history table + real FK on optimization_history.forecast_id

Closes the gap flagged in optimization.py's ORM model docstring: forecast_id
existed as a plain nullable BIGINT with no table to reference. Now it does.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE forecast_history (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    horizon         VARCHAR(20) NOT NULL,
    as_of_date      DATE NOT NULL,
    target_date     DATE NOT NULL,
    predicted_mw    NUMERIC(10,2) NOT NULL,
    model_version   VARCHAR(50) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forecast_city_time ON forecast_history(city_id, created_at DESC);

ALTER TABLE optimization_history
    ADD CONSTRAINT fk_optimization_forecast
    FOREIGN KEY (forecast_id) REFERENCES forecast_history(id) ON DELETE SET NULL;
"""

DOWNGRADE_SQL = """
ALTER TABLE optimization_history DROP CONSTRAINT IF EXISTS fk_optimization_forecast;
DROP TABLE IF EXISTS forecast_history;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)