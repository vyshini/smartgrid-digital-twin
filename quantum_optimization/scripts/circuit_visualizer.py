"""
Builds and renders the QAOA ansatz circuit for a given dispatch problem —
satisfies the spec's "Quantum Circuit Visualization" requirement.

NOTE ON SANDBOX EXECUTION: same caveat as qaoa_optimizer.py — written
against Qiskit's documented QAOAAnsatz API but not executable here (no
qiskit installed, no network to install it). Validate on your machine.

Required packages: qiskit, qiskit-aer, matplotlib (for circuit.draw('mpl'))
"""
from __future__ import annotations

from qiskit.circuit.library import QAOAAnsatz

from generation_capacity import CITY_GENERATION_CAPACITY
from hamiltonian_builder import DispatchProblem, build_qubo, qubo_to_ising
from qaoa_optimizer import build_qiskit_operator


def build_qaoa_circuit(problem: DispatchProblem, reps: int = 2):
    """
    Returns the (unbound-parameter) QAOA ansatz circuit for `problem` —
    useful for visualizing circuit STRUCTURE (depth, gate layout, qubit
    count) independent of any specific trained parameters. To visualize
    the circuit with the actual optimized angles from a completed run,
    bind eigen_result.optimal_parameters to this circuit instead (see
    bind_optimal_parameters below).
    """
    Q = build_qubo(problem)
    pauli_coefficients, _offset = qubo_to_ising(Q)
    qubit_op = build_qiskit_operator(pauli_coefficients, problem.n_qubits)
    return QAOAAnsatz(cost_operator=qubit_op, reps=reps)


def bind_optimal_parameters(ansatz, optimal_parameters: dict):
    """Binds a completed QAOA run's optimized angles onto the ansatz, for
    visualizing the actual circuit that produced a specific result (as
    opposed to the generic parameterized structure from build_qaoa_circuit)."""
    return ansatz.assign_parameters(optimal_parameters)


def circuit_summary(ansatz) -> dict:
    """Basic structural stats for the dashboard's 'Quantum Circuit' panel —
    depth and gate counts, not a rendered image (see render_circuit_png for that)."""
    decomposed = ansatz.decompose()
    return {
        "n_qubits": ansatz.num_qubits,
        "depth": decomposed.depth(),
        "gate_counts": dict(decomposed.count_ops()),
        "num_parameters": ansatz.num_parameters,
    }


def render_circuit_png(ansatz, output_path: str) -> None:
    """
    Saves a circuit diagram image. Requires matplotlib. If the ansatz still
    has unbound parameters (from build_qaoa_circuit, not bind_optimal_parameters),
    the diagram shows symbolic parameter names (β_0, γ_0, ...) rather than
    numeric angles — both are valid, just show different things.
    """
    fig = ansatz.decompose().draw("mpl")
    fig.savefig(output_path, bbox_inches="tight", dpi=150)


if __name__ == "__main__":
    cap = CITY_GENERATION_CAPACITY["Delhi"]
    problem = DispatchProblem(capacity=cap, target_demand_mw=1500, battery_power_rating_mw=200)
    ansatz = build_qaoa_circuit(problem, reps=2)
    print("Circuit summary:", circuit_summary(ansatz))
    render_circuit_png(ansatz, "delhi_qaoa_circuit.png")
    print("Saved circuit diagram to delhi_qaoa_circuit.png")
