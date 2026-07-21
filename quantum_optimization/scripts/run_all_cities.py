"""
Task 3: runs the full real-forecast -> QAOA-dispatch pipeline across all
8 cities, collecting results into a summary CSV. Same discipline as
train_lstm.py's training_summary.csv: one city's failure doesn't abort
the whole run, and QAOA is NEVER reported without its classical baseline
comparison alongside it.

NOTE ON SANDBOX EXECUTION: requires TensorFlow, Qiskit, and real trained
model artifacts, none of which exist in this sandbox. Untested end-to-end
— every underlying function it calls has been individually validated on
your machine already (forecast_to_dispatch.py, qaoa_optimizer.py), this
script is straightforward orchestration on top of those.

WATCH FOR: Delhi and Kolkata have wind_mw=0 in generation_capacity.py's
real data (see its docstring on the Delhi/West Bengal extraction
confidence caveat). Their 4 "wind block" qubits contribute zero to every
term in the QUBO (capacity=0 -> cost=0 and the demand-matching weight for
those qubits is also 0) — mathematically correct (unused capacity truly
doesn't matter), not a bug, but worth noting: those qubits are functionally
inert for these two cities, simulating 4 qubits' worth of Aer computation
for zero optimization benefit. Flagged here rather than silently accepted;
a future iteration could dynamically exclude zero-capacity sources from
DispatchProblem's variable index instead — not done in this pass to avoid
touching hamiltonian_builder.py's already-tested, already-verified code
without a concrete correctness reason to do so.

Run from quantum-optimization/scripts/:
    python run_all_cities.py              # next_day horizon (default)
    python run_all_cities.py next_week    # next_week horizon
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from forecast_to_dispatch import build_dispatch_problem_from_forecast  # noqa: E402
from generation_capacity import CITY_GENERATION_CAPACITY  # noqa: E402
from qaoa_optimizer import run_qaoa  # noqa: E402

RESULTS_DIR = Path(__file__).parent.parent / "results"

SOURCES = ("coal", "hydro", "wind", "solar")


def run_city(
    city: str,
    horizon: str = "next_day",
    reps: int = 2,
    shots: int = 1024,
    maxiter: int = 100,
    battery_power_rating_mw: float = 200.0,
    battery_conflict_penalty_weight: float | None = None,
) -> dict:
    """
    Real forecast -> DispatchProblem -> QAOA + classical baseline, for one
    city. `battery_power_rating_mw` is currently a FIXED value across all
    cities (see generation_capacity.py's docstring — no real per-city
    battery rating dataset exists yet), which is more noticeable for
    small-capacity cities (Delhi: ~2,630 MW total dispatchable, so 200 MW
    battery = ~7.6% of capacity) vs large ones (Gujarat: ~37,600 MW total,
    so 200 MW = ~0.5%) — worth deciding whether to scale this per-city
    once a real source is found, not silently treated as equally
    significant everywhere.
    """
    problem, forecast = build_dispatch_problem_from_forecast(
        city,
        horizon=horizon,
        battery_power_rating_mw=battery_power_rating_mw,
        battery_conflict_penalty_weight=battery_conflict_penalty_weight,
    )
    result = run_qaoa(problem, reps=reps, shots=shots, maxiter=maxiter)

    capacity = CITY_GENERATION_CAPACITY[city]
    zero_capacity_sources = [s for s in SOURCES if getattr(capacity, f"{s}_mw") == 0]

    return {
        "city": city,
        "forecast": forecast,
        "n_qubits": problem.n_qubits,
        "zero_capacity_sources": zero_capacity_sources,
        "qaoa_dispatch": result["qaoa"]["decoded"],
        "classical_dispatch": result["classical_baseline"]["decoded"],
        "classical_method": result["classical_baseline"]["method"],
        "objective_gap": result["objective_gap"],
        "optimization_score": result["optimization_score"],
        "matched_optimum": result["qaoa_matches_classical_optimum"],
    }


def main(
    horizon: str = "next_day",
    battery_conflict_penalty_weight: float | None = None,
    reps: int = 2,
    shots: int = 1024,
    maxiter: int = 100,
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []
    failures = []
    for city in CITY_GENERATION_CAPACITY:
        print(f"\n{'=' * 60}\n{city}\n{'=' * 60}")
        try:
            result = run_city(
                city,
                horizon=horizon,
                reps=reps,
                shots=shots,
                maxiter=maxiter,
                battery_conflict_penalty_weight=battery_conflict_penalty_weight,
            )
            all_results.append(result)
            print(f"  forecast: {result['forecast']}")
            print(
                f"  n_qubits: {result['n_qubits']} "
                f"(zero-capacity sources: {result['zero_capacity_sources'] or 'none'})"
            )
            print(f"  QAOA dispatch: {result['qaoa_dispatch']}")
            print(
                f"  optimization_score: {result['optimization_score']}, "
                f"matched_optimum: {result['matched_optimum']}"
            )
        except Exception as e:  # noqa: BLE001 — one city's failure shouldn't abort the run
            print(f"  [FAILED] {city}: {e}")
            failures.append({"city": city, "error": str(e)})

    if all_results:
        summary_rows = []
        for r in all_results:
            qd, cd = r["qaoa_dispatch"], r["classical_dispatch"]
            row = {
                "city": r["city"],
                "n_qubits": r["n_qubits"],
                "zero_capacity_sources": ", ".join(r["zero_capacity_sources"]) or "none",
                "anchor_mw": r["forecast"]["anchor_mw"],
                f"{horizon}_forecast_mw": r["forecast"][f"{horizon}_mw"],
                "targets_were_deltas": r["forecast"]["targets_were_deltas"],
                "qaoa_coal_mw": qd["coal_mw"], "qaoa_hydro_mw": qd["hydro_mw"],
                "qaoa_wind_mw": qd["wind_mw"], "qaoa_solar_mw": qd["solar_mw"],
                "qaoa_battery_charge_mw": qd["battery_charge_mw"],
                "qaoa_battery_discharge_mw": qd["battery_discharge_mw"],
                "qaoa_mismatch_mw": qd["mismatch_mw"],
                "qaoa_battery_conflict": qd["battery_conflict"],
                "classical_coal_mw": cd["coal_mw"], "classical_hydro_mw": cd["hydro_mw"],
                "classical_wind_mw": cd["wind_mw"], "classical_solar_mw": cd["solar_mw"],
                "classical_battery_charge_mw": cd["battery_charge_mw"],
                "classical_battery_discharge_mw": cd["battery_discharge_mw"],
                "classical_mismatch_mw": cd["mismatch_mw"],
                "classical_battery_conflict": cd["battery_conflict"],
                "classical_method": r["classical_method"],
                "objective_gap": r["objective_gap"],
                "optimization_score": r["optimization_score"],
                "matched_optimum": r["matched_optimum"],
            }
            summary_rows.append(row)

        summary_df = pd.DataFrame(summary_rows)
        summary_path = RESULTS_DIR / f"optimization_summary_{horizon}.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"\n{'=' * 60}\nSummary written to {summary_path}\n{'=' * 60}")
        print(summary_df.to_string(index=False))

        n_matched = int(summary_df["matched_optimum"].sum())
        print(f"\n{n_matched}/{len(summary_df)} cities: QAOA matched classical optimum exactly")

        not_matched = summary_df[~summary_df["matched_optimum"]]
        if len(not_matched) > 0:
            print("\nCities where QAOA did NOT match the classical optimum (worth investigating, not averaging away):")
            print(not_matched[["city", "objective_gap", "optimization_score"]].to_string(index=False))

    if failures:
        print(f"\n{len(failures)} cit{'y' if len(failures) == 1 else 'ies'} failed:")
        for f in failures:
            print(f"  - {f['city']}: {f['error']}")


if __name__ == "__main__":
    horizon_arg = sys.argv[1] if len(sys.argv) > 1 else "next_day"
    penalty_arg = float(sys.argv[2]) if len(sys.argv) > 2 else None
    reps_arg = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    maxiter_arg = int(sys.argv[4]) if len(sys.argv) > 4 else 100
    main(
        horizon_arg,
        battery_conflict_penalty_weight=penalty_arg,
        reps=reps_arg,
        maxiter=maxiter_arg,
    )