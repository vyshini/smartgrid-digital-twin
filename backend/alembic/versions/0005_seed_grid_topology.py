"""Seed grid_nodes and transmission_lines for all 8 cities.

WHY THIS MIGRATION EXISTS: 0001_initial_schema.py seeds the `cities` table
but nothing seeds grid_nodes or transmission_lines against the real
database. The only place this data previously existed was
tests/integration/test_cities.py's _seed_city_with_nodes() -- an
in-memory SQLite fixture, torn down after each test. Confirmed empty
against the real (Neon) database via a direct check: 0 grid nodes across
all 8 cities. Without this migration, the "City Digital Twin" tab has
nothing to render for any city, in any real deployment.

HONESTY NOTE ON THE DATA ITSELF: unlike generation_capacity.py's MoSPI/
CEA-cited installed generation capacity, there is no equivalent public
dataset for per-substation transmission topology at this granularity.
These node/line capacity figures are ILLUSTRATIVE PLACEHOLDER TOPOLOGY,
scaled roughly by each city's relative size/population -- not measured
utility SCADA data. This is the same category of documented, undisguised
estimate as hamiltonian_builder.py's RELATIVE_COST_WEIGHT. Delhi's
figures (5000/4000 MW nodes, 1000 MW line, 750 MW load) deliberately
match tests/integration/test_cities.py's existing fixture values, so the
real seeded data and the test's expected data now agree.

Two nodes + one connecting line per city -- enough for the City Digital
Twin view to show a non-empty, non-trivial topology (a node list, at
least one transmission corridor to inspect, a real utilization_pct via
classify_grid_health) without asserting a level of real-world fidelity
this project doesn't have data to back.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (city_name, node_a_code, node_a_capacity_mw, node_b_code, node_b_capacity_mw,
#  line_capacity_mw, line_current_load_mw, line_length_km, line_loss_pct)
CITY_TOPOLOGY = [
    ("Delhi",     "IN-DEL-01", 5000, "IN-DEL-02", 4000, 1000, 750, 42.5, 2.10),
    ("Mumbai",    "IN-MUM-01", 6000, "IN-MUM-02", 5000, 1200, 900, 38.0, 1.95),
    ("Bangalore", "IN-BLR-01", 3500, "IN-BLR-02", 3000,  800, 600, 35.2, 2.30),
    ("Hyderabad", "IN-HYD-01", 3000, "IN-HYD-02", 2500,  700, 500, 33.0, 2.25),
    ("Chennai",   "IN-CHE-01", 3200, "IN-CHE-02", 2800,  750, 560, 40.1, 2.40),
    ("Kolkata",   "IN-KOL-01", 3800, "IN-KOL-02", 3200,  850, 680, 36.8, 2.50),
    ("Ahmedabad", "IN-AMD-01", 2600, "IN-AMD-02", 2200,  600, 420, 31.5, 2.15),
    ("Pune",      "IN-PUN-01", 2000, "IN-PUN-02", 1700,  500, 350, 28.7, 2.05),
]

_INSERT_NODE = sa.text(
    "INSERT INTO grid_nodes (city_id, node_code, transmission_capacity_mw, status) "
    "SELECT c.id, :node_code, :capacity, 'healthy' FROM cities c WHERE c.name = :city_name"
)

_INSERT_LINE = sa.text(
    "INSERT INTO transmission_lines "
    "(from_node_id, to_node_id, capacity_mw, current_load_mw, length_km, loss_pct, status) "
    "SELECT n1.id, n2.id, :line_capacity, :line_load, :length_km, :loss_pct, 'active' "
    "FROM grid_nodes n1, grid_nodes n2 "
    "WHERE n1.node_code = :node_a_code AND n2.node_code = :node_b_code"
)


def upgrade() -> None:
    conn = op.get_bind()
    for (city_name, node_a_code, node_a_cap, node_b_code, node_b_cap,
         line_cap, line_load, length_km, loss_pct) in CITY_TOPOLOGY:
        conn.execute(_INSERT_NODE, {"node_code": node_a_code, "capacity": node_a_cap, "city_name": city_name})
        conn.execute(_INSERT_NODE, {"node_code": node_b_code, "capacity": node_b_cap, "city_name": city_name})
        conn.execute(_INSERT_LINE, {
            "line_capacity": line_cap, "line_load": line_load,
            "length_km": length_km, "loss_pct": loss_pct,
            "node_a_code": node_a_code, "node_b_code": node_b_code,
        })


def downgrade() -> None:
    conn = op.get_bind()
    all_node_codes = [code for row in CITY_TOPOLOGY for code in (row[1], row[3])]
    conn.execute(
        sa.text(
            "DELETE FROM transmission_lines WHERE from_node_id IN "
            "(SELECT id FROM grid_nodes WHERE node_code = ANY(:codes)) "
            "OR to_node_id IN (SELECT id FROM grid_nodes WHERE node_code = ANY(:codes))"
        ),
        {"codes": all_node_codes},
    )
    conn.execute(
        sa.text("DELETE FROM grid_nodes WHERE node_code = ANY(:codes)"),
        {"codes": all_node_codes},
    )