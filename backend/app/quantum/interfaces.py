"""
GridOptimizer interface — the abstraction the application layer (use cases)
depends on, per Phase 1's Clean Architecture plan (app/quantum/interfaces.py
was planned there as the quantum-layer's plugin boundary, mirroring how
app/ml/interfaces.py's Forecaster ABC keeps the application layer decoupled
from TensorFlow). Concrete implementations (QAOA, classical-only) both
satisfy this same interface, so the use case that calls it never imports
Qiskit directly.
"""
from abc import ABC, abstractmethod

from app.quantum.hamiltonian_builder import DispatchProblem


class GridOptimizer(ABC):
    @abstractmethod
    def optimize(self, problem: DispatchProblem) -> dict:
        """
        Solves `problem` and returns a result dict containing at minimum:
        `decoded` (the human-readable MW dispatch — see
        hamiltonian_builder.decode_solution), `objective_value`, and
        whatever solver-specific diagnostics the implementation provides.
        Concrete implementations (QAOAGridOptimizer) additionally include a
        classical baseline comparison — see qaoa_optimizer.run_qaoa's
        module docstring on why that comparison is mandatory, not optional,
        for any quantum result reported by this project.
        """
        raise NotImplementedError