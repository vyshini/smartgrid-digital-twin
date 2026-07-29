"""
Classical solver for the dispatch QUBO — serves two purposes:

1. A real, usable optimizer on its own (works today, no quantum hardware
   or simulator needed) — the spec's "classical fallback" requirement.
2. Critically, the GROUND TRUTH that QAOA's result gets checked against.
   For a ~20-qubit problem, brute force over all 2^20 (~1M) bitstrings is
   classically trivial — this is exactly the same discipline as Phase 3's
   persistence-baseline check: a quantum result that doesn't match or
   nearly match the known true optimum is not something to report as
   "the optimizer found a good answer" without that comparison alongside it.
"""
import numpy as np

from app.quantum.hamiltonian_builder import DispatchProblem, qubo_objective


def solve_exact_brute_force(problem: DispatchProblem, Q: np.ndarray, chunk_size: int = 100_000) -> dict:
    """
    Exhaustively evaluates every possible bitstring, in bounded-memory
    CHUNKS rather than building the full 2^n array at once. Still exact —
    every bitstring is checked, just in batches.

    WHY CHUNKED: the naive vectorized approach (build all 2^n rows, then a
    (2^n, n_pairs) intermediate array for cross-terms) can need 1.5+ GB for
    a single ~20-qubit problem with no zero-capacity sources (worst case:
    all C(20,2)=190 pairs non-zero) — and this crashed in practice on a
    real 8-city run (Mumbai: "Unable to allocate 1.48 GiB"), likely because
    the process also holds TensorFlow and Qiskit Aer in memory
    simultaneously. Chunking bounds peak memory to ~chunk_size x n_pairs
    regardless of total problem size, at a small, worthwhile speed cost.

    Only tractable for small n_qubits (fine up to ~22-24 on a laptop; this
    project's problems are ~20). Returns the best bitstring and its
    objective value.
    """
    n = problem.n_qubits
    if n > 24:
        raise ValueError(
            f"Brute force over 2^{n} bitstrings is not practical — reduce "
            f"N_BLOCKS or N_BATTERY_BITS, or use solve_greedy_heuristic instead."
        )

    diag = np.diag(Q)
    iu, ju = np.triu_indices(n, k=1)
    nonzero_mask = Q[iu, ju] != 0
    iu, ju, qvals = iu[nonzero_mask], ju[nonzero_mask], Q[iu, ju][nonzero_mask]

    total = 2**n
    bit_positions = np.arange(n)
    best_value = float("inf")
    best_x = None

    for start in range(0, total, chunk_size):
        end = min(start + chunk_size, total)
        idx = np.arange(start, end)
        chunk_bits = (idx[:, None] >> bit_positions[None, :]) & 1

        values = chunk_bits.astype(np.float64) @ diag
        if len(qvals) > 0:
            values += (chunk_bits[:, iu] * chunk_bits[:, ju]) @ qvals

        chunk_best_idx = int(np.argmin(values))
        if values[chunk_best_idx] < best_value:
            best_value = float(values[chunk_best_idx])
            best_x = chunk_bits[chunk_best_idx]

    return {"x": best_x, "objective_value": best_value}


def solve_greedy_heuristic(problem: DispatchProblem, Q: np.ndarray, n_restarts: int = 50, seed: int = 42) -> dict:
    """
    A faster classical heuristic (local search from random starts) for
    problems too large to brute-force — not needed at our current ~20-qubit
    scale, but included so the classical fallback still works if the
    problem is scaled up later (e.g. more blocks, more sources, multi-city).
    Not guaranteed optimal, unlike solve_exact_brute_force.
    """
    n = problem.n_qubits
    rng = np.random.default_rng(seed)
    best_x, best_value = None, float("inf")

    for _ in range(n_restarts):
        x = rng.integers(0, 2, size=n)
        value = qubo_objective(Q, x)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                x_flipped = x.copy()
                x_flipped[i] = 1 - x_flipped[i]
                flipped_value = qubo_objective(Q, x_flipped)
                if flipped_value < value:
                    x, value = x_flipped, flipped_value
                    improved = True
        if value < best_value:
            best_x, best_value = x, value

    return {"x": best_x, "objective_value": best_value}