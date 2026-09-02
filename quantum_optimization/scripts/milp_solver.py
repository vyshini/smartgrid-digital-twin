"""
Classical MILP baseline via PuLP + CBC (open-source, no license needed) --
adds an industry-standard comparison point alongside the brute-force
ground truth already in classical_solver.py.

Since the QUBO objective has quadratic terms (x_i * x_j), it's linearized
via standard McCormick envelope constraints before handing it to the MILP
solver: for each pair (i,j) with a nonzero Q_ij, an auxiliary binary
y_ij is introduced with:
    y_ij <= x_i
    y_ij <= x_j
    y_ij >= x_i + x_j - 1
which forces y_ij == x_i AND x_j exactly whenever x_i, x_j are binary --
this is exact, not an approximation, regardless of Q_ij's sign.

Install:
    pip install pulp --break-system-packages
"""
import time
import sys
from pathlib import Path

import pulp

sys.path.insert(0, str(Path(__file__).parent))
from hamiltonian_builder import DispatchProblem, build_qubo

def solve_milp(problem: DispatchProblem, time_limit_s: int = 60) -> dict:
    Q = build_qubo(problem)
    n = problem.n_qubits

    model = pulp.LpProblem("dispatch_qubo", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    objective_terms = []
    for i in range(n):
        if Q[i, i] != 0:
            objective_terms.append(Q[i, i] * x[i])

    y_vars = {}
    for i in range(n):
        for j in range(i + 1, n):
            if Q[i, j] == 0:
                continue
            y = pulp.LpVariable(f"y_{i}_{j}", cat="Binary")
            y_vars[(i, j)] = y
            model += y <= x[i]
            model += y <= x[j]
            model += y >= x[i] + x[j] - 1
            objective_terms.append(Q[i, j] * y)

    model += pulp.lpSum(objective_terms)

    solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=time_limit_s)   # *** msg=1: show solver output, not silent ***
    start = time.time()
    model.solve(solver)
    elapsed = time.time() - start

    status = pulp.LpStatus[model.status]

    # *** NEW: check status BEFORE reading values -- avoids the
    # "NoneType doesn't define __round__" crash by failing with a clear
    # message instead. ***
    if status != "Optimal":
        return {
            "x": None,
            "objective_value": None,
            "solve_time_s": round(elapsed, 4),
            "status": status,
            "error": f"Solver did not reach optimal status (got '{status}') -- see printed CBC output above for the real cause.",
        }

    x_solution = [int(round(pulp.value(x[i]))) for i in range(n)]
    objective_value = pulp.value(model.objective)

    return {
        "x": x_solution,
        "objective_value": objective_value,
        "solve_time_s": round(elapsed, 4),
        "status": status,
    }

if __name__ == "__main__":
    from generation_capacity import CITY_GENERATION_CAPACITY
    from classical_solver import solve_exact_brute_force
    from hamiltonian_builder import decode_solution, qubo_objective

    DEMANDS = {
        "Delhi": 234.95, "Mumbai": 89.99, "Pune": 32.41, "Bangalore": 50.8,
        "Hyderabad": 70.41, "Chennai": 54.38, "Kolkata": 31.43, "Ahmedabad": 52.69,
    }

    print(f"{'City':12s} {'MILP time (s)':>15s} {'Brute force time (s)':>22s} {'Same optimum?':>15s} {'Status':>12s}")
    for city, demand in DEMANDS.items():
        cap = CITY_GENERATION_CAPACITY[city]
        problem = DispatchProblem(capacity=cap, target_demand_mw=demand, battery_power_rating_mw=200.0)

        milp_result = solve_milp(problem)

        if milp_result["objective_value"] is None:
            print(f"{city:12s} {'FAILED':>15s} {'-':>22s} {'-':>15s} {milp_result['status']:>12s}")
            print(f"  -> {milp_result['error']}")
            continue

        Q = build_qubo(problem)
        start = time.time()
        bf_result = solve_exact_brute_force(problem, Q)
        bf_time = time.time() - start

        same = abs(milp_result["objective_value"] - bf_result["objective_value"]) < 1e-4
        print(f"{city:12s} {milp_result['solve_time_s']:>15.4f} {bf_time:>22.4f} {str(same):>15s} {milp_result['status']:>12s}")