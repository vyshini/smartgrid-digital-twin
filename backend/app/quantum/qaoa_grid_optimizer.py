from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.interfaces import GridOptimizer
from app.quantum.qaoa_optimizer import run_qaoa


class QAOAGridOptimizer(GridOptimizer):
    def __init__(self, reps: int = 1, shots: int = 128, maxiter: int = 5, seed: int = 42):
        self.reps = reps
        self.shots = shots
        self.maxiter = maxiter
        self.seed = seed

    def optimize(self, problem: DispatchProblem) -> dict:
        return run_qaoa(
            problem=problem,
            reps=self.reps,
            shots=self.shots,
            maxiter=self.maxiter,
            seed=self.seed,
        )