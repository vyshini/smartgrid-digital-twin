"""Unit tests for classical_solver.py — the ground truth QAOA gets
checked against. These must be trustworthy independent of QAOA/Qiskit."""
import numpy as np

from app.quantum.classical_solver import solve_exact_brute_force, solve_greedy_heuristic
from app.quantum.hamiltonian_builder import DispatchProblem, build_qubo, qubo_objective
from app.quantum.population_data import apportioned_city_capacity

DELHI_CAPACITY = apportioned_city_capacity("Delhi")


def test_brute_force_finds_global_minimum():
    """Brute force must genuinely check every bitstring's objective and
    return the true minimum — verified here by independently
    re-evaluating a handful of candidate bitstrings and confirming none
    beat the reported best."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=270, battery_power_rating_mw=100)
    Q = build_qubo(problem)
    result = solve_exact_brute_force(problem, Q)

    reported_best = result["objective_value"]

    rng = np.random.default_rng(0)
    for _ in range(200):
        x = rng.integers(0, 2, size=problem.n_qubits)
        assert qubo_objective(Q, x) >= reported_best - 1e-9


def test_brute_force_rejects_too_many_qubits():
    """The function's own safety guard against accidentally brute-forcing
    something intractable."""
    import pytest

    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=270, battery_power_rating_mw=100)
    problem.n_qubits = 25  # simulate a mis-configured, too-large problem
    Q = np.zeros((25, 25))
    with pytest.raises(ValueError):
        solve_exact_brute_force(problem, Q)


def test_greedy_heuristic_reasonably_close_to_exact():
    """Not guaranteed optimal by design, but shouldn't be far off on an
    easy, small-scale problem — a basic sanity floor. Uses an ABSOLUTE
    tolerance rather than a percentage one, since objective values here
    are commonly negative (percentage bounds flip direction incorrectly
    on negative numbers)."""
    problem = DispatchProblem(capacity=DELHI_CAPACITY, target_demand_mw=270, battery_power_rating_mw=100)
    Q = build_qubo(problem)
    exact = solve_exact_brute_force(problem, Q)
    greedy = solve_greedy_heuristic(problem, Q, n_restarts=20, seed=1)

    assert greedy["objective_value"] >= exact["objective_value"] - 1e-9
    # loose absolute tolerance: greedy shouldn't be more than 1000 units
    # worse than exact on this easy, small-scale case
    assert greedy["objective_value"] <= exact["objective_value"] + 1000