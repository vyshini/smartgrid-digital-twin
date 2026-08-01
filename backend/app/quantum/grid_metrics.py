"""
Post-hoc grid-quality metrics computed from an already-decoded QAOA
allocation — no new optimization runs needed. All three metrics compare
against a NAIVE BASELINE: "meet all demand from 100% coal, no
optimization" — representing what an unoptimized grid operator might
default to.

RELATIVE_LOSS_WEIGHT mirrors hamiltonian_builder.py's RELATIVE_COST_WEIGHT
pattern: illustrative, documented, not a measured per-unit figure. Local
generation (coal/hydro/wind/solar/battery) is assigned a low distribution-
loss weight; grid import is assigned a higher weight, reflecting the real,
well-established fact that inter-state transmission incurs materially
higher losses than local distribution. power_loss_reduction_pct CAN come
out negative — if an allocation leans on import for cost reasons, it may
genuinely have HIGHER transmission loss than an all-local-coal baseline.
That's a real tradeoff to report, not a bug to suppress.
"""
from __future__ import annotations

from app.quantum.hamiltonian_builder import RELATIVE_COST_WEIGHT, SOURCES

RELATIVE_LOSS_WEIGHT = {
    "coal": 0.03,
    "hydro": 0.03,
    "wind": 0.03,
    "solar": 0.03,
    "battery": 0.03,  # local storage, negligible extra transmission loss
    "import": 0.08,  # inter-state transfer — real, well-documented higher loss
}


def _naive_baseline_cost(target_demand_mw: float) -> float:
    """100% coal, no optimization — the naive comparison point."""
    return RELATIVE_COST_WEIGHT["coal"] * target_demand_mw


def _naive_baseline_loss_mw(target_demand_mw: float) -> float:
    return RELATIVE_LOSS_WEIGHT["coal"] * target_demand_mw


def compute_cost_reduction_pct(decoded: dict) -> float:
    """decoded is the dict from hamiltonian_builder.decode_solution (or
    the equivalent 'allocation_result' JSON already stored on an
    OptimizationHistory row)."""
    target_demand_mw = decoded["target_demand_mw"]
    if target_demand_mw <= 0:
        return 0.0

    optimized_cost = sum(RELATIVE_COST_WEIGHT[s] * decoded[f"{s}_mw"] for s in SOURCES)
    optimized_cost += RELATIVE_COST_WEIGHT["import"] * decoded.get("import_mw", 0.0)

    naive_cost = _naive_baseline_cost(target_demand_mw)
    if naive_cost <= 0:
        return 0.0

    return round(100 * (naive_cost - optimized_cost) / naive_cost, 2)


def compute_power_loss_reduction_pct(decoded: dict) -> float:
    """CAN be negative — see module docstring. Not clamped to [0, 100]
    deliberately; a clamped value would hide a real, reportable finding
    (cost-optimal dispatch isn't always loss-optimal)."""
    target_demand_mw = decoded["target_demand_mw"]
    if target_demand_mw <= 0:
        return 0.0

    optimized_loss = sum(RELATIVE_LOSS_WEIGHT[s] * decoded[f"{s}_mw"] for s in SOURCES)
    optimized_loss += RELATIVE_LOSS_WEIGHT["import"] * decoded.get("import_mw", 0.0)
    optimized_loss += RELATIVE_LOSS_WEIGHT["battery"] * decoded.get("battery_discharge_mw", 0.0)

    naive_loss = _naive_baseline_loss_mw(target_demand_mw)
    if naive_loss <= 0:
        return 0.0

    return round(100 * (naive_loss - optimized_loss) / naive_loss, 2)


def compute_grid_stability_score(decoded: dict) -> float:
    """
    Distinct from optimization_score (which measures QAOA-vs-classical-
    optimum closeness — a QUANTUM metric). This measures PHYSICAL dispatch
    quality: how close to zero the mismatch is, and whether a
    battery_conflict occurred (a real red flag, not just an objective-
    function artifact).

    Starts at 100, deducts for relative mismatch (capped at 50 points) and
    a flat 15-point penalty for battery_conflict. Floored at 0.
    """
    target_demand_mw = decoded["target_demand_mw"]
    mismatch_mw = abs(decoded.get("mismatch_mw", 0.0))

    score = 100.0
    if target_demand_mw > 0:
        mismatch_pct = 100 * mismatch_mw / target_demand_mw
        score -= min(50.0, mismatch_pct)

    if decoded.get("battery_conflict", False):
        score -= 15.0

    return round(max(0.0, score), 2)

# Illustrative CO2-intensity weights (dimensionless, relative ranking —
# NOT measured kg-CO2/MWh figures), same documented-estimate pattern as
# RELATIVE_COST_WEIGHT and RELATIVE_LOSS_WEIGHT above. Coal is the
# dominant emitter by a wide, well-established margin; renewables and
# battery are treated as near-zero at point of dispatch (upstream
# manufacturing emissions are out of scope here); import is assigned a
# moderate weight since the imported mix is unknown or unrepresented in
# this project's approximate scope.
RELATIVE_CO2_WEIGHT = {
    "coal": 1.00,
    "hydro": 0.02,
    "wind": 0.02,
    "solar": 0.02,
    "battery": 0.02,
    "import": 0.40,
}


def compute_co2_reduction_pct(decoded: dict) -> float:
    """Same naive-100%-coal-baseline comparison as compute_cost_reduction_pct.
    Not persisted to a DB column (no co2 field in optimization_history's
    current schema) — computed on-the-fly from allocation_result JSON,
    which already stores everything needed."""
    target_demand_mw = decoded["target_demand_mw"]
    if target_demand_mw <= 0:
        return 0.0

    optimized_co2 = sum(RELATIVE_CO2_WEIGHT[s] * decoded[f"{s}_mw"] for s in SOURCES)
    optimized_co2 += RELATIVE_CO2_WEIGHT["import"] * decoded.get("import_mw", 0.0)

    naive_co2 = RELATIVE_CO2_WEIGHT["coal"] * target_demand_mw
    if naive_co2 <= 0:
        return 0.0

    return round(100 * (naive_co2 - optimized_co2) / naive_co2, 2)