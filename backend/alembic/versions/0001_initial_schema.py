"""Initial schema: auth, cities, grid topology, timeseries tables (Phase 2 scope)

Tables for forecast_history, ml_models, optimization_history, simulation_*,
alerts, and reports are added in later migrations as Phases 3/4/6 build the
layers that use them — see docs/database-schema.sql for the full target schema.

Revision ID: 0001
Revises:
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE user_role AS ENUM ('admin', 'grid_operator', 'engineer', 'researcher');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(150) NOT NULL,
    role            user_role NOT NULL DEFAULT 'researcher',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,
    entity          VARCHAR(100) NOT NULL,
    entity_id       VARCHAR(100),
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_logs_user_time ON audit_logs(user_id, created_at);

CREATE TABLE cities (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    state           VARCHAR(100) NOT NULL,
    latitude        NUMERIC(9,6) NOT NULL,
    longitude       NUMERIC(9,6) NOT NULL,
    population      BIGINT NOT NULL,
    timezone        VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE node_status AS ENUM ('healthy', 'degraded', 'critical', 'offline');

CREATE TABLE grid_nodes (
    id                          SERIAL PRIMARY KEY,
    city_id                     INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    node_code                   VARCHAR(20) UNIQUE NOT NULL,
    transmission_capacity_mw    NUMERIC(10,2) NOT NULL,
    status                      node_status NOT NULL DEFAULT 'healthy',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_grid_nodes_city ON grid_nodes(city_id);

CREATE TYPE line_status AS ENUM ('active', 'degraded', 'failed', 'maintenance');

CREATE TABLE transmission_lines (
    id              SERIAL PRIMARY KEY,
    from_node_id    INTEGER NOT NULL REFERENCES grid_nodes(id) ON DELETE CASCADE,
    to_node_id      INTEGER NOT NULL REFERENCES grid_nodes(id) ON DELETE CASCADE,
    capacity_mw     NUMERIC(10,2) NOT NULL,
    current_load_mw NUMERIC(10,2) NOT NULL DEFAULT 0,
    length_km       NUMERIC(8,2) NOT NULL,
    loss_pct        NUMERIC(5,2) NOT NULL DEFAULT 0,
    status          line_status NOT NULL DEFAULT 'active',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_distinct_nodes CHECK (from_node_id <> to_node_id)
);
CREATE INDEX idx_transmission_from ON transmission_lines(from_node_id);
CREATE INDEX idx_transmission_to ON transmission_lines(to_node_id);

CREATE TABLE weather_readings (
    id                  BIGSERIAL PRIMARY KEY,
    city_id             INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    recorded_at         TIMESTAMPTZ NOT NULL,
    temperature_c       NUMERIC(5,2) NOT NULL,
    humidity_pct        NUMERIC(5,2) NOT NULL,
    wind_speed_kmph     NUMERIC(6,2) NOT NULL,
    solar_irradiance    NUMERIC(7,2) NOT NULL,
    precipitation_mm    NUMERIC(6,2) NOT NULL DEFAULT 0,
    condition           VARCHAR(50) NOT NULL,
    is_holiday          BOOLEAN NOT NULL DEFAULT FALSE,
    is_weekend          BOOLEAN NOT NULL DEFAULT FALSE,
    is_festival         BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (city_id, recorded_at)
);
CREATE INDEX idx_weather_city_time ON weather_readings(city_id, recorded_at DESC);

CREATE TABLE power_generation (
    id              BIGSERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    recorded_at     TIMESTAMPTZ NOT NULL,
    solar_mw        NUMERIC(10,2) NOT NULL DEFAULT 0,
    wind_mw         NUMERIC(10,2) NOT NULL DEFAULT 0,
    hydro_mw        NUMERIC(10,2) NOT NULL DEFAULT 0,
    coal_mw         NUMERIC(10,2) NOT NULL DEFAULT 0,
    gas_mw          NUMERIC(10,2) NOT NULL DEFAULT 0,
    nuclear_mw      NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_mw        NUMERIC(10,2) GENERATED ALWAYS AS
                        (solar_mw + wind_mw + hydro_mw + coal_mw + gas_mw + nuclear_mw) STORED,
    UNIQUE (city_id, recorded_at)
);
CREATE INDEX idx_generation_city_time ON power_generation(city_id, recorded_at DESC);

CREATE TABLE renewables (
    id                      BIGSERIAL PRIMARY KEY,
    city_id                 INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    recorded_at             TIMESTAMPTZ NOT NULL,
    solar_capacity_mw       NUMERIC(10,2) NOT NULL,
    wind_capacity_mw        NUMERIC(10,2) NOT NULL,
    hydro_capacity_mw       NUMERIC(10,2) NOT NULL,
    solar_utilization_pct   NUMERIC(5,2) NOT NULL,
    wind_utilization_pct    NUMERIC(5,2) NOT NULL,
    hydro_utilization_pct   NUMERIC(5,2) NOT NULL,
    UNIQUE (city_id, recorded_at)
);
CREATE INDEX idx_renewables_city_time ON renewables(city_id, recorded_at DESC);

CREATE TABLE battery_storage (
    id                  BIGSERIAL PRIMARY KEY,
    city_id             INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    recorded_at         TIMESTAMPTZ NOT NULL,
    capacity_mwh        NUMERIC(10,2) NOT NULL,
    current_charge_mwh  NUMERIC(10,2) NOT NULL,
    charge_rate_mw      NUMERIC(10,2) NOT NULL DEFAULT 0,
    discharge_rate_mw   NUMERIC(10,2) NOT NULL DEFAULT 0,
    soc_pct             NUMERIC(5,2) GENERATED ALWAYS AS
                            (100 * current_charge_mwh / NULLIF(capacity_mwh, 0)) STORED,
    health_pct          NUMERIC(5,2) NOT NULL DEFAULT 100,
    UNIQUE (city_id, recorded_at)
);
CREATE INDEX idx_battery_city_time ON battery_storage(city_id, recorded_at DESC);

CREATE TABLE load_demand (
    id                  BIGSERIAL PRIMARY KEY,
    city_id             INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    recorded_at         TIMESTAMPTZ NOT NULL,
    residential_mw      NUMERIC(10,2) NOT NULL DEFAULT 0,
    commercial_mw       NUMERIC(10,2) NOT NULL DEFAULT 0,
    industrial_mw       NUMERIC(10,2) NOT NULL DEFAULT 0,
    ev_charging_mw      NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_mw            NUMERIC(10,2) GENERATED ALWAYS AS
                            (residential_mw + commercial_mw + industrial_mw + ev_charging_mw) STORED,
    UNIQUE (city_id, recorded_at)
);
CREATE INDEX idx_load_city_time ON load_demand(city_id, recorded_at DESC);

INSERT INTO cities (name, state, latitude, longitude, population) VALUES
    ('Delhi',      'Delhi',           28.6139, 77.2090, 32900000),
    ('Mumbai',     'Maharashtra',     19.0760, 72.8777, 20700000),
    ('Bangalore',  'Karnataka',       12.9716, 77.5946, 13600000),
    ('Hyderabad',  'Telangana',       17.3850, 78.4867, 10500000),
    ('Chennai',    'Tamil Nadu',      13.0827, 80.2707, 11700000),
    ('Kolkata',    'West Bengal',     22.5726, 88.3639, 15100000),
    ('Ahmedabad',  'Gujarat',         23.0225, 72.5714,  8400000),
    ('Pune',       'Maharashtra',     18.5204, 73.8567,  7400000);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS load_demand;
DROP TABLE IF EXISTS battery_storage;
DROP TABLE IF EXISTS renewables;
DROP TABLE IF EXISTS power_generation;
DROP TABLE IF EXISTS weather_readings;
DROP TABLE IF EXISTS transmission_lines;
DROP TABLE IF EXISTS grid_nodes;
DROP TABLE IF EXISTS cities;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS users;
DROP TYPE IF EXISTS line_status;
DROP TYPE IF EXISTS node_status;
DROP TYPE IF EXISTS user_role;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
