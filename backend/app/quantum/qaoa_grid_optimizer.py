from app.quantum.hamiltonian_builder import DispatchProblem
from app.quantum.interfaces import GridOptimizer
from app.quantum.qaoa_optimizer import run_qaoa
from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY

class QAOAGridOptimizer(GridOptimizer):
    def __init__(self, reps: int = 1, shots: int = 128, maxiter: int = 5, seed: int = 42):
        self.reps = reps
        self.shots = shots
        self.maxiter = maxiter
        self.seed = seed

    def optimize(self, problem: DispatchProblem) -> dict:
        print("🚀 Starting REAL Qiskit QAOA Optimization...")
        
        # --- MICRO-GRID OVERRIDE FOR FAST DEMO / TESTING ---
        # Overriding the massive city problem with a tiny 8-qubit problem
        tiny_problem = DispatchProblem(
            capacity=CITY_GENERATION_CAPACITY["Delhi"], 
            target_demand_mw=10, # Very low demand = very few qubits
            battery_power_rating_mw=0 
        )
        print(f"⚠️ Overriding with tiny problem: {tiny_problem.n_qubits} qubits")
        # ---------------------------------------------------
        
        return run_qaoa(
            problem=tiny_problem,
            reps=self.reps,
            shots=self.shots,
            maxiter=self.maxiter,
            seed=self.seed
        )