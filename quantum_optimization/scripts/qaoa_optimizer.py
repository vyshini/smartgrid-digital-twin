"""
Runs QAOA (via the actively-maintained `qiskit_algorithms` package — NOT
the deprecated `qiskit.algorithms`, which many older tutorials still show)
against the Ising Hamiltonian built by hamiltonian_builder.py, using Qiskit
Aer's simulator as the sampler primitive (satisfying the spec's explicit
"Aer Simulator" + "COBYLA Optimizer" requirements).

NOTE ON SANDBOX EXECUTION: this file could not be imported or run in the
sandbox this project was authored in — no `qiskit`/`qiskit-aer`/
`qiskit-algorithms` installed, no network access to install them. Every
function it calls (build_qubo, qubo_to_ising, decode_solution) IS fully
tested — see hamiltonian_builder.py and classical_solver.py, verified
against real Delhi capacity data with an exact QUBO<->Ising round-trip
check and a classical brute-force ground truth. Only the Qiskit-specific
wiring below is unverified. Validate on your machine with a SMALL problem
first (few qubits, low reps, few COBYLA iterations) before trusting a full
run — see the __main__ block at the bottom for a ready-to-run smoke test.

VERSION NOTE: uses Aer's SamplerV2 (not the deprecated V1 Sampler, removed
in recent Aer releases). SamplerV2 requires an explicit transpiler/pass-
manager for any backend other than Qiskit's own StatevectorSampler —
without it, QAOA's internal SamplingVQE machinery fails with
"TypeError: Invalid circuits, expected Sequence[QuantumCircuit]" because
it passes V2-style "pubs" to a sampler that (without a pass-manager)
doesn't transpile them into a form the backend accepts.

Required packages: qiskit, qiskit-aer, qiskit-algorithms
    pip install qiskit qiskit-aer qiskit-algorithms
"""
from __future__ import annotations

import numpy as np
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_algorithms.utils import algorithm_globals

from classical_solver import solve_exact_brute_force, solve_greedy_heuristic
from generation_capacity import CITY_GENERATION_CAPACITY
from hamiltonian_builder import DispatchProblem, build_qubo, decode_solution, qubo_objective, qubo_to_ising


def _pauli_string(active_qubits: tuple[int, ...], n_qubits: int) -> str:
    """
    Builds a Qiskit-convention Pauli string: qubit 0 is the RIGHTMOST
    character (Qiskit's little-endian convention) — a common source of
    subtle bugs if built the naive left-to-right way. `active_qubits` are
    the indices that get a Z; everything else gets I.
    """
    chars = ["I"] * n_qubits
    for q in active_qubits:
        chars[n_qubits - 1 - q] = "Z"
    return "".join(chars)


def build_qiskit_operator(pauli_coefficients: dict[tuple[int, ...], float], n_qubits: int) -> SparsePauliOp:
    """
    The ONLY function in this file that touches Qiskit for the Hamiltonian
    itself — everything upstream (qubo_to_ising) is pure numpy and already
    tested. Converts the tested (pauli_indices -> coefficient) dict into a
    SparsePauliOp.
    """
    pauli_list = [
        (_pauli_string(key, n_qubits), coeff) for key, coeff in pauli_coefficients.items()
    ]
    return SparsePauliOp.from_list(pauli_list)


def sample_most_likely_bitstring(quasi_distribution, n_qubits: int) -> np.ndarray:
    """
    Fallback path: QAOA's `result.eigenstate` is a QuasiDistribution whose
    keys represent "a measured classical value" — in practice this can be
    an int OR a bitstring depending on Qiskit version/sampler, which is
    exactly the kind of thing that's safer to detect than assume. Prefer
    decode_best_measurement() below when available (Qiskit's own
    documented, purpose-built field for this) — this function exists only
    for older qiskit_algorithms versions that might lack best_measurement.
    """
    best_key = max(quasi_distribution.items(), key=lambda kv: kv[1])[0]
    if isinstance(best_key, str):
        bitstring = best_key.zfill(n_qubits)
        return np.array([int(b) for b in bitstring[::-1]])
    best_state_int = int(best_key)
    return np.array([(best_state_int >> i) & 1 for i in range(n_qubits)])


def decode_best_measurement(best_measurement, n_qubits: int) -> np.ndarray:
    """
    Preferred path: qiskit_algorithms' SamplingVQEResult.best_measurement
    exposes a directly-usable 'bitstring' field — the officially documented
    way to get the best sampled solution (accounts for the solver's
    aggregation method, e.g. CVaR, rather than just raw shot-count
    probability). Qiskit convention: leftmost character = highest qubit
    index, rightmost = qubit 0 — reversed here to match this project's
    var_index convention (index 0 = qubit 0).
    """
    bitstring = best_measurement["bitstring"] if isinstance(best_measurement, dict) else best_measurement.bitstring
    bitstring = bitstring.zfill(n_qubits)
    return np.array([int(b) for b in bitstring[::-1]])


def run_qaoa(
    problem: DispatchProblem,
    reps: int = 2,
    shots: int = 2048,
    maxiter: int = 200,
    seed: int = 42,
) -> dict:
    """
    Runs QAOA against `problem` and returns a result dict in the same shape
    as classical_solver's outputs, PLUS a classical comparison — every QAOA
    run reports how it did against the known-optimal (or near-optimal,
    for larger problems) classical answer, not in isolation. This mirrors
    Phase 3's persistence-baseline discipline: a quantum result presented
    without a classical comparison alongside it is not something to trust
    at face value, regardless of how plausible it looks on its own.
    """
    algorithm_globals.random_seed = seed

    Q = build_qubo(problem)
    pauli_coefficients, offset = qubo_to_ising(Q)
    qubit_op = build_qiskit_operator(pauli_coefficients, problem.n_qubits)

    # SamplerV2 (unlike the now-deprecated V1 Sampler) requires an explicit
    # transpiler/pass-manager for any backend other than Qiskit's own
    # StatevectorSampler — QAOA's internal SamplingVQE machinery transpiles
    # the ansatz for the target backend before running it.
    backend = AerSimulator(method="statevector")
    pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend)

    sampler = SamplerV2(seed=seed, default_shots=shots)
    optimizer = COBYLA(maxiter=maxiter)
    qaoa = QAOA(sampler=sampler, optimizer=optimizer, reps=reps, transpiler=pass_manager)

    eigen_result = qaoa.compute_minimum_eigenvalue(qubit_op)

    best_measurement = getattr(eigen_result, "best_measurement", None)
    if best_measurement is not None:
        x_qaoa = decode_best_measurement(best_measurement, problem.n_qubits)
    else:
        x_qaoa = sample_most_likely_bitstring(eigen_result.eigenstate, problem.n_qubits)
    qaoa_objective_value = qubo_objective(Q, x_qaoa)

    # --- Classical ground truth for comparison — never report QAOA alone ---
    if problem.n_qubits <= 24:
        classical = solve_exact_brute_force(problem, Q)
        classical_label = "exact_brute_force"
    else:
        classical = solve_greedy_heuristic(problem, Q)
        classical_label = "greedy_heuristic"

    gap = qaoa_objective_value - classical["objective_value"]
    # Optimization score: 100 if QAOA matches classical optimum, degrading
    # as the gap grows, floored at 0. Normalized against the demand-penalty
    # term's own characteristic scale (lambda * D^2 — the dominant term in
    # this QUBO's objective), NOT the classical objective's raw value.
    # The classical objective_value itself can land near zero for
    # small-demand problems (when cost and penalty terms partially cancel),
    # which made this score wildly inconsistent across cities of different
    # scales — a real 8-city test run showed Pune (gap=3.0) scoring 0.00
    # while Hyderabad (also gap=3.0) scored 99.99, purely because their
    # classical objective_value magnitudes differed by chance, not because
    # one result was actually worse than the other.
    demand_scale = problem.demand_penalty_weight * max(problem.target_demand_mw, 1.0) ** 2
    optimization_score = max(0.0, 100.0 * (1 - abs(gap) / demand_scale))

    return {
        "qaoa": {
            "decoded": decode_solution(problem, x_qaoa),
            "objective_value": qaoa_objective_value,
            "n_qubits": problem.n_qubits,
            "reps": reps,
            "shots": shots,
            "cobyla_iterations": maxiter,
            "optimizer_evals": getattr(eigen_result, "cost_function_evals", None),
        },
        "classical_baseline": {
            "method": classical_label,
            "decoded": decode_solution(problem, classical["x"]),
            "objective_value": classical["objective_value"],
        },
        "objective_gap": gap,
        "optimization_score": round(optimization_score, 2),
        "qaoa_matches_classical_optimum": bool(abs(gap) < 1e-6),
    }


if __name__ == "__main__":
    # Smoke test — run this FIRST on your machine, before a full multi-city
    # run, per the module docstring's sandbox-execution caveat.
    cap = CITY_GENERATION_CAPACITY["Delhi"]
    problem = DispatchProblem(capacity=cap, target_demand_mw=1500, battery_power_rating_mw=200)
    print(f"Problem: {problem.n_qubits} qubits")

    result = run_qaoa(problem, reps=1, shots=512, maxiter=50)  # small/fast for a first smoke test
    print("QAOA decoded dispatch:", result["qaoa"]["decoded"])
    print("Classical baseline decoded dispatch:", result["classical_baseline"]["decoded"])
    print("Objective gap (QAOA - classical optimum):", result["objective_gap"])
    print("Optimization score:", result["optimization_score"])
    print("QAOA matched classical optimum exactly?", result["qaoa_matches_classical_optimum"])