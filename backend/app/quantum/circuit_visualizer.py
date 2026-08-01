"""
Quantum circuit visualization for the QAOA dispatch optimizer.

Builds a real QAOAAnsatz circuit from the same DispatchProblem ->
hamiltonian_builder.py pipeline run_qaoa() itself uses (build_qubo,
qubo_to_ising, then qaoa_optimizer.build_qiskit_operator to get a
SparsePauliOp) — so what gets drawn here is genuinely the circuit that
runs, not a stand-in illustration built separately from the real path.

IMPORTANT: this module only CONSTRUCTS and DRAWS the circuit — it never
runs/simulates it. Building a QAOAAnsatz is just assembling gate objects
(no state-vector simulation, no COBYLA), so unlike run_qaoa() this is fast
regardless of qubit count — expect this to run in well under a second even
at 10+ qubits, since none of the exponential simulation cost applies here.

NOTE ON SANDBOX EXECUTION: same caveat as qaoa_optimizer.py — written
against qiskit/qiskit.circuit.library, not executable in the authoring
sandbox (no qiskit installed). Validate on your machine first (see
__main__ block) before trusting the output.

Requires matplotlib for circuit.draw(output="mpl") — not a hard Qiskit
dependency, add it to requirements.txt if it's not already installed:
    pip install matplotlib
"""
from __future__ import annotations

from pathlib import Path

from qiskit.circuit.library import QAOAAnsatz

from app.quantum.hamiltonian_builder import DispatchProblem, build_qubo, qubo_to_ising
from app.quantum.qaoa_optimizer import build_qiskit_operator


def build_qaoa_circuit(problem: DispatchProblem, reps: int = 1):
    """
    Builds (but does not run) the QAOAAnsatz circuit for `problem`, using
    the exact same QUBO -> Ising -> SparsePauliOp pipeline run_qaoa() uses
    internally. Returns an unbound QuantumCircuit (parameterized gamma/beta
    angles, not yet optimized) — this shows the CIRCUIT STRUCTURE QAOA
    explores, not one specific solved instance's numeric values.
    """
    Q = build_qubo(problem)
    pauli_coefficients, _offset = qubo_to_ising(Q)
    qubit_op = build_qiskit_operator(pauli_coefficients, problem.n_qubits)
    return QAOAAnsatz(cost_operator=qubit_op, reps=reps)


def save_circuit_diagram(
    problem: DispatchProblem,
    output_path: str | Path,
    reps: int = 1,
    decompose_level: int = 0,
    fold: int = 25,
) -> Path:
    """
    Renders the QAOA ansatz circuit to a PNG via Qiskit's own matplotlib
    drawer — no custom rendering invented here, matching how the rest of
    this project prefers real library functionality over reinventing it
    (see qaoa_optimizer.py's StatevectorSampler choice for the same
    reasoning).

    decompose_level controls readability vs. detail:
      0 = opaque "Cost"/"Mixer" ansatz blocks — readable at a glance,
          good for a report figure or dashboard card
      2 = expanded into real RX/RZZ/etc. gates — useful for verifying the
          actual circuit, harder to read visually past ~8-10 qubits
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    circuit_to_draw = build_qaoa_circuit(problem, reps=reps)
    for _ in range(decompose_level):
        circuit_to_draw = circuit_to_draw.decompose()

    fig = circuit_to_draw.draw(output="mpl", fold=fold, style="iqp")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return output_path


def circuit_summary(problem: DispatchProblem, reps: int = 1) -> dict:
    """
    Cheap, non-graphical circuit stats — for an API response / dashboard
    card where headline numbers are wanted, not a full image. Decomposes
    two levels deep so `circuit_depth` reflects real gates, matching what
    an expanded diagram (decompose_level=2) would actually show.
    """
    ansatz = build_qaoa_circuit(problem, reps=reps)
    decomposed = ansatz.decompose(reps=2)

    gate_counts = decomposed.count_ops()
    return {
        "n_qubits": problem.n_qubits,
        "reps": reps,
        "circuit_depth": decomposed.depth(),
        "total_gates": sum(gate_counts.values()),
        "gate_counts": dict(gate_counts),
    }


if __name__ == "__main__":
    from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY

    cap = CITY_GENERATION_CAPACITY["Delhi"]
    problem = DispatchProblem(capacity=cap, target_demand_mw=9789.38, battery_power_rating_mw=100)
    print(f"Problem: {problem.n_qubits} qubits")

    print("Circuit summary:", circuit_summary(problem, reps=1))

    out = save_circuit_diagram(problem, "circuit_output/delhi_qaoa_ansatz.png", reps=1, decompose_level=0)
    print(f"Saved ansatz-block diagram -> {out}")

    out2 = save_circuit_diagram(problem, "circuit_output/delhi_qaoa_expanded.png", reps=1, decompose_level=2)
    print(f"Saved expanded-gate diagram -> {out2}")