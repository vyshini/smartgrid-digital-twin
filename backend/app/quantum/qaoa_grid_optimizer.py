from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.interfaces import GridOptimizer
from app.quantum.qaoa_optimizer import run_qaoa


class QAOAGridOptimizer(GridOptimizer):
    def __init__(self, reps: int = 2, shots: int = 1024, maxiter: int = 100, seed: int = 42):
        # These defaults were previously reps=1/shots=128/maxiter=5, which
        # gave COBYLA almost no room to converge on this 10-qubit problem
        # and reliably produced non-physical dispatch results (simultaneous
        # full-power battery charge+discharge -- see
        # backend/scripts/smoke_test_qaoa.py, which reproduced this exact
        # failure at reps=1/shots=256/maxiter=20, an already MORE generous
        # setting than the old default). At reps=2/shots=1024/maxiter=100,
        # the same smoke test reached the exact classical optimum
        # (objective_gap=0.0) in 1.3s real wall-clock time on a real Delhi
        # capacity problem -- fast enough that there is no performance
        # reason to keep the old, under-converged defaults.
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