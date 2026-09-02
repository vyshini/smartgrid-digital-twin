"""
CO2 and cost reduction, v3 -- differentiated CO2 weights so the metric
can actually distinguish between renewable-heavy and battery-heavy
dispatch mixes, instead of collapsing to a uniform 98.0% whenever coal
is absent (see v2's finding: hydro/wind/solar/battery-discharge were all
weighted identically at 0.02, so ANY zero-coal dispatch produced the
exact same reduction% regardless of actual source mix).

Weights below still keep coal as overwhelmingly the worst emitter (a
real, well-established fact) while giving renewables/storage small,
distinct values reflecting real documented differences (e.g. reservoir
hydro has a small but real methane footprint; wind/solar have near-zero
operational emissions; battery-discharge is stored energy, priced
slightly above wind/solar since SOME of what's stored may originally
have come from non-renewable charging). These remain illustrative
relative weights, NOT measured kg-CO2/MWh figures -- same documented-
estimate pattern as this project's original RELATIVE_CO2_WEIGHT.
"""
import pandas as pd
from pathlib import Path

RESULTS_PATH = Path(__file__).parent.parent / "results" / "optimization_summary_next_day.csv"

RELATIVE_CO2_WEIGHT_V2 = {
    "coal": 1.00,
    "hydro": 0.03,
    "wind": 0.01,
    "solar": 0.02,
}
BATTERY_DISCHARGE_CO2_WEIGHT_V2 = 0.015

RELATIVE_COST_WEIGHT = {"coal": 1.00, "hydro": 0.25, "wind": 0.15, "solar": 0.10}
BATTERY_DISCHARGE_COST_WEIGHT = 0.05

SOURCES = ("coal", "hydro", "wind", "solar")


def co2_reduction_pct_v3(row: pd.Series, prefix: str) -> float:
    generation_co2 = sum(RELATIVE_CO2_WEIGHT_V2[s] * row[f"{prefix}_{s}_mw"] for s in SOURCES)
    discharge_co2 = BATTERY_DISCHARGE_CO2_WEIGHT_V2 * row[f"{prefix}_battery_discharge_mw"]
    optimized_co2 = generation_co2 + discharge_co2

    total_energy_served = sum(row[f"{prefix}_{s}_mw"] for s in SOURCES) + row[f"{prefix}_battery_discharge_mw"]
    naive_co2 = RELATIVE_CO2_WEIGHT_V2["coal"] * total_energy_served
    return round(100 * (naive_co2 - optimized_co2) / naive_co2, 2) if naive_co2 > 0 else 0.0


def cost_reduction_pct_v3(row: pd.Series, prefix: str) -> float:
    generation_cost = sum(RELATIVE_COST_WEIGHT[s] * row[f"{prefix}_{s}_mw"] for s in SOURCES)
    discharge_cost = BATTERY_DISCHARGE_COST_WEIGHT * row[f"{prefix}_battery_discharge_mw"]
    optimized_cost = generation_cost + discharge_cost

    total_energy_served = sum(row[f"{prefix}_{s}_mw"] for s in SOURCES) + row[f"{prefix}_battery_discharge_mw"]
    naive_cost = RELATIVE_COST_WEIGHT["coal"] * total_energy_served
    return round(100 * (naive_cost - optimized_cost) / naive_cost, 2) if naive_cost > 0 else 0.0


df = pd.read_csv(RESULTS_PATH)

rows = []
for _, r in df.iterrows():
    rows.append({
        "city": r["city"],
        "qaoa_co2_reduction_pct": co2_reduction_pct_v3(r, "qaoa"),
        "classical_co2_reduction_pct": co2_reduction_pct_v3(r, "classical"),
        "qaoa_cost_reduction_pct": cost_reduction_pct_v3(r, "qaoa"),
        "classical_cost_reduction_pct": cost_reduction_pct_v3(r, "classical"),
        "matched_optimum": r["matched_optimum"],
    })

out = pd.DataFrame(rows)
out_path = Path(__file__).parent.parent / "results" / "co2_cost_summary_v3.csv"
out.to_csv(out_path, index=False)
print(out.to_string(index=False))
print(f"\nSaved -> {out_path}")
print(f"\nAvg QAOA CO2 reduction:  {out['qaoa_co2_reduction_pct'].mean():.2f}%")
print(f"Avg QAOA cost reduction: {out['qaoa_cost_reduction_pct'].mean():.2f}%")