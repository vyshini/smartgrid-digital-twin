"""
Unit tests for hamiltonian_builder.py's pure QUBO logic. No DB, no Qiskit,
no QAOA — these test the classical math directly, and double as regression
tests for real scenarios already manually validated via Swagger (see
project history: exact-match at 270MW, import displacing coal at ~9789MW).
"""
import numpy as np
import pytest

from app.quantum.generation_capacity import GenerationCapacity
from app.quantum.hamiltonian_builder import (
    N_BATTERY_BITS,
    N_BLOCKS,
    N_IMPORT_BITS,
    SOURCES,
    DispatchProblem,
    build_qubo,
    decode_solution,
    qubo_objective,
)
from app.quantum.classical_solver import solve_exact_brute_force
from app.quantum.population_data import apportioned_city_capacity

# Delhi's real apportioned capacity, per the actual population_data.py
# capping logic (Delhi's population/state-population ratio is capped at
# 1.0, so this equals its full state capacity) — same values used in every
# manual Swagger test throughout this project.
DELHI_CAPACITY = apportioned_city_capacity("Delhi")


def test_qubit_count_matches_constants():
    """4 sources * N_BLOCKS + 2*N_BATTERY_BITS + N_IMPORT_BITS. Locks in the
    current validated local-testing configuration (N_BLOCKS=1) — if this
    ever fails, someone changed a constant without updating the documented
    qubit count in hamiltonian_builder.py's own comments."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=1000, battery_power_rating_mw=100)
    expected = len(SOURCES) * N_BLOCKS + 2 * N_BATTERY_BITS + N_IMPORT_BITS
    assert problem.n_qubits == expected


def test_import_capacity_defaults_to_target_demand():
    """import_capacity_mw=None should default to target_demand_mw itself —
    the grid interconnect can, in principle, cover the full forecasted
    demand. See hamiltonian_builder.py's DispatchProblem docstring."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=5000, battery_power_rating_mw=100)
    assert problem.import_capacity_mw == 5000


def test_import_capacity_explicit_override_respected():
    problem = DispatchProblem(
        capacity=DELHI_CAPACITY, target_demand_mw=5000, battery_power_rating_mw=100, import_capacity_mw=2000
    )
    assert problem.import_capacity_mw == 2000


def test_decode_solution_total_supply_includes_import():
    """Regression test for a real bug: total_supply_mw once excluded
    import_mw entirely, silently reporting total_supply=0 even when
    import correctly supplied the full demand. This test would have
    caught that immediately."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=1000, battery_power_rating_mw=100)
    # All-zeros bitstring except the two import bits fully on
    x = np.zeros(problem.n_qubits, dtype=int)
    for k in range(N_IMPORT_BITS):
        x[problem.var_index[("import", k)]] = 1

    result = decode_solution(problem, x)
    expected_import = sum(problem.import_bit_mw(k) for k in range(N_IMPORT_BITS))

    assert result["import_mw"] == pytest.approx(expected_import, abs=0.01)
    assert result["total_supply_mw"] == pytest.approx(expected_import, abs=0.01)
    assert result["total_supply_mw"] != 0  # the exact failure mode of the real bug


def test_exact_match_scenario_hydro_plus_solar():
    """Regression test for the FIRST validated Swagger result: target=270MW
    should be met exactly by hydro(59) + solar(211), coal and import left
    off, since coal's cost weight (1.00) and its full-capacity block size
    make it far more expensive than the exact-fit renewable combination."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=270, battery_power_rating_mw=100)
    Q = build_qubo(problem)
    best = solve_exact_brute_force(problem, Q)

    decoded = decode_solution(problem, best["x"])
    assert decoded["hydro_mw"] == pytest.approx(59, abs=0.5)
    assert decoded["solar_mw"] == pytest.approx(211, abs=0.5)
    assert decoded["coal_mw"] == 0
    assert decoded["mismatch_mw"] == pytest.approx(0, abs=0.5)


def test_saturated_demand_scenario_maxes_all_sources():
    """Regression test for the 'Delhi can't locally meet ~9789 MW' finding
    — before the import variable existed, every dispatchable source
    (including coal) should max out, since any unused capacity only makes
    a large mismatch worse."""
    # import_capacity_mw=0 deliberately disables import, reproducing the
    # exact scenario tested before gap #2 (import-from-grid) was added.
    problem = DispatchProblem(
        capacity=DELHI_CAPACITY, target_demand_mw=9789.38, battery_power_rating_mw=100, import_capacity_mw=0.01,
    )
    Q = build_qubo(problem)
    best = solve_exact_brute_force(problem, Q)
    decoded = decode_solution(problem, best["x"])

    assert decoded["coal_mw"] == pytest.approx(DELHI_CAPACITY.coal_mw, abs=0.5)
    assert decoded["hydro_mw"] == pytest.approx(DELHI_CAPACITY.hydro_mw, abs=0.5)
    assert decoded["solar_mw"] == pytest.approx(DELHI_CAPACITY.solar_mw, abs=0.5)
    assert decoded["mismatch_mw"] < 0  # still short — the whole point of this finding


def test_import_displaces_coal_when_available():
    """Regression test for gap #2's validated result: with import enabled
    and cheaper than coal (weight 0.60 vs 1.00), a demand of 9789.38 MW
    should prefer maxing out import over turning on coal's single
    expensive 2360MW block."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=9789.38, battery_power_rating_mw=100)
    Q = build_qubo(problem)
    best = solve_exact_brute_force(problem, Q)
    decoded = decode_solution(problem, best["x"])

    assert decoded["coal_mw"] == 0
    assert decoded["import_mw"] > 0


def test_qubo_objective_matches_decode_mismatch_direction():
    """Sanity check that qubo_objective and decode_solution agree on which
    of two candidate solutions is better — catches any future drift
    between the two independent code paths that both read var_index."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=270, battery_power_rating_mw=100)
    Q = build_qubo(problem)

    x_good = np.zeros(problem.n_qubits, dtype=int)
    x_good[problem.var_index[("gen", "hydro", 0)]] = 1
    x_good[problem.var_index[("gen", "solar", 0)]] = 1

    x_bad = np.zeros(problem.n_qubits, dtype=int)
    x_bad[problem.var_index[("gen", "coal", 0)]] = 1  # wildly overshoots 270MW

    assert qubo_objective(Q, x_good) < qubo_objective(Q, x_bad)