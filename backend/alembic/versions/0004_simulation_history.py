"""Add simulation_history table (weather + generation scenarios)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE TABLE simulation_history (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    scenario_type   VARCHAR(20) NOT NULL,
    scenario_key    VARCHAR(100) NOT NULL,
    scenario_name   VARCHAR(200) NOT NULL,
    as_of_date      VARCHAR(10),
    result          JSONB NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_simulation_city_time ON simulation_history(city_id, run_at DESC);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS simulation_history;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)