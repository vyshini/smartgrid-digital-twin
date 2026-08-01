"""
Builds the QUBO (Quadratic Unconstrained Binary Optimization) formulation
of the single-city generation dispatch problem, then converts it to an
Ising Hamiltonian. Deliberately split into pure-numpy stages (fully
testable without Qiskit) and a final, minimal Qiskit-dependent wrapper
(qubo_to_qiskit_operator), so the actual optimization MATH can be verified
independently of whether Qiskit is installed.

PROBLEM FORMULATION
--------------------
Decision: for ONE city, at ONE forecasted demand level, which discrete
power "blocks" of each dispatchable source to activate, plus whether to
charge or discharge the battery, to meet demand at minimum cost while
preferring renewables — matching the spec's Load Balancing / Generator
Scheduling / Renewable Allocation / Battery Charging goals within a scope
tractable for a classically-simulated QAOA circuit (~20 qubits).

Sources (see generation_capacity.py): coal, hydro, wind, solar. Each is
split into N_BLOCKS equal-sized binary blocks — x[s,k]=1 means the k-th
block of source s is dispatched, contributing capacity_s / N_BLOCKS MW.
Nuclear is EXCLUDED — modeled as fixed baseload outside this decision
(see generation_capacity.py's docstring for why).

Battery: represented by N_BATTERY_BITS charge bits and N_BATTERY_BITS
discharge bits (a small binary/unary encoding of 0..2^N_BATTERY_BITS-1
discrete power levels), with a quadratic penalty discouraging simultaneous
nonzero charge AND discharge (can't do both at once).

Objective (minimize):
    cost term            — linear cost per dispatched block, CHEAPEST for
                            renewables, MOST EXPENSIVE for coal. These are
                            ILLUSTRATIVE RELATIVE WEIGHTS reflecting India's
                            real "must-run" renewable-priority dispatch
                            policy (CERC/state grid codes require preferential
                            dispatch of renewables when available) — not
                            measured per-unit rupee costs, which would need
                            separate sourcing. Documented here, not hidden.
  + demand-mismatch penalty — quadratic penalty forcing
                            (total generation + battery discharge - battery
                            charge) towards the target demand. This is what
                            makes the problem genuinely quadratic (not just
                            a knapsack), since (sum - D)^2 expands into
                            pairwise cross-terms between every block.
  + battery-conflict penalty — quadratic penalty on (any charge bit) x
                            (any discharge bit), discouraging simultaneous
                            charge and discharge.
"""
from dataclasses import dataclass, field

import numpy as np

from app.quantum.generation_capacity import GenerationCapacity

SOURCES = ("coal", "hydro", "wind", "solar")
N_BLOCKS = 1  # per source — validated local config. Reduced from an original
# N_BLOCKS=4 design (20 qubits total) for local StatevectorSampler
# feasibility. Empirically: 8 qubits (N_BLOCKS=1, no import) ran in
# ~15-18s; adding 2 qubits for the import variable (10 qubits total) grew
# runtime to ~140-235s under identical QAOA settings — a ~10x increase for
# a 2-qubit addition, consistent with state-vector simulation's exponential
# scaling. N_BLOCKS=2 (14 qubits) was evaluated as impractical for local
# iterative testing on this basis; restoring full granularity (N_BLOCKS=4,
# the original design) is left as a target configuration for dedicated
# hardware (e.g. IBM Quantum Cloud's free tier) rather than local
# simulation. This is a genuine scalability limitation of the local-testing
# setup, not a limitation of the QAOA formulation itself.
N_BATTERY_BITS = 2  # charge and discharge each get this many bits
N_IMPORT_BITS = 2   # grid-interconnect import, same binary-weighted encoding as battery


# Illustrative relative cost weights (dimensionless, NOT Rs/kWh) reflecting
# India's real renewable-must-run dispatch priority policy: renewables are
# cheapest to "use" in this objective, coal is most expensive. See module
# docstring — this encodes a real, citable dispatch PREFERENCE, not a
# measured cost figure.
RELATIVE_COST_WEIGHT = {
    "solar": 0.10,
    "wind": 0.15,
    "hydro": 0.25,
    "import": 0.60,
    "coal": 1.00,
    
}


@dataclass
class DispatchProblem:
    """One instance of the dispatch problem: a city's real capacity plus a
    target demand level to serve (e.g. from Phase 3's next_day forecast)."""

    capacity: GenerationCapacity
    target_demand_mw: float
    battery_power_rating_mw: float
    import_capacity_mw: float | None = None
    demand_penalty_weight: float = 5.0
    battery_conflict_penalty_weight: float = 3.0

    # populated by build_variable_index()
    var_index: dict = field(default_factory=dict, init=False)
    n_qubits: int = field(default=0, init=False)

    def __post_init__(self):
        if self.import_capacity_mw is None:
            # Grid interconnect can, in principle, cover the full forecasted
            # demand — matches the real-world observation (see Delhi's test
            # results) that this city relies heavily on inter-state import
            # rather than local generation alone.
            self.import_capacity_mw = self.target_demand_mw
        self.var_index = self._build_variable_index()
        self.n_qubits = len(self.var_index)

    def _build_variable_index(self) -> dict:
        """Maps every binary decision variable to a qubit index. Order is
        arbitrary but must be consistent across every function that reads
        it — this is the single source of truth for that ordering."""
        idx = {}
        i = 0
        for s in SOURCES:
            for k in range(N_BLOCKS):
                idx[("gen", s, k)] = i
                i += 1
        for k in range(N_BATTERY_BITS):
            idx[("battery_charge", k)] = i
            i += 1
        for k in range(N_BATTERY_BITS):
            idx[("battery_discharge", k)] = i
            i += 1
        for k in range(N_IMPORT_BITS):          # NEW
            idx[("import", k)] = i                # NEW
            i += 1  
        return idx

    def block_size_mw(self, source: str) -> float:
        capacity_mw = getattr(self.capacity, f"{source}_mw")
        return capacity_mw / N_BLOCKS

    def battery_bit_mw(self, bit_position: int) -> float:
        """Binary-weighted bits: bit 0 = rating/2^N, bit 1 = rating*2/2^N, etc.
        so N_BATTERY_BITS bits span 0..(2^N_BATTERY_BITS - 1) * (rating/2^N_BATTERY_BITS)
        ~= 0..rating MW in equal steps."""
        step = self.battery_power_rating_mw / (2 ** N_BATTERY_BITS - 1)
        return step * (2 ** bit_position)

    def import_bit_mw(self, bit_position: int) -> float:
        """Same binary-weighted scheme as battery_bit_mw, scaled to
        import_capacity_mw instead of battery_power_rating_mw."""
        step = self.import_capacity_mw / (2 ** N_IMPORT_BITS - 1)
        return step * (2 ** bit_position)

def build_qubo(problem: DispatchProblem) -> np.ndarray:
    """
    Builds the QUBO matrix Q (n_qubits x n_qubits, symmetric-upper-triangular
    convention: objective(x) = sum_i Q[i,i]*x_i + sum_{i<j} Q[i,j]*x_i*x_j).
    Pure numpy — no Qiskit dependency, fully unit-testable.
    """
    n = problem.n_qubits
    Q = np.zeros((n, n))
    idx = problem.var_index

    # --- 1. Linear cost terms (diagonal) ---
    for s in SOURCES:
        block_mw = problem.block_size_mw(s)
        cost = RELATIVE_COST_WEIGHT[s] * block_mw
        for k in range(N_BLOCKS):
            Q[idx[("gen", s, k)], idx[("gen", s, k)]] += cost


         # --- Import cost (linear, diagonal) — same illustrative-weight pattern
    for k in range(N_IMPORT_BITS):                                          # NEW
        cost = RELATIVE_COST_WEIGHT["import"] * problem.import_bit_mw(k)    # NEW
        Q[idx[("import", k)], idx[("import", k)]] += cost     

    # --- 2. Demand-mismatch penalty: lambda * (supply - target_demand)^2 ---
    # supply = sum(gen blocks) + sum(discharge bits) - sum(charge bits)
    # Build a linear "coefficient vector" w such that supply = w . x, then
    # expand lambda*(w.x - D)^2 = lambda*sum_i w_i^2 x_i^2
    #                            + 2*lambda*sum_{i<j} w_i w_j x_i x_j
    #                            - 2*lambda*D*sum_i w_i x_i   (+ const, dropped)
    # using x_i^2 = x_i for binary variables.
    w = np.zeros(n)
    for s in SOURCES:
        block_mw = problem.block_size_mw(s)
        for k in range(N_BLOCKS):
            w[idx[("gen", s, k)]] += block_mw
    for k in range(N_BATTERY_BITS):
        w[idx[("battery_discharge", k)]] += problem.battery_bit_mw(k)
        w[idx[("battery_charge", k)]] -= problem.battery_bit_mw(k)
    for k in range(N_IMPORT_BITS):                                    # NEW
        w[idx[("import", k)]] += problem.import_bit_mw(k)    

    lam = problem.demand_penalty_weight
    D = problem.target_demand_mw
    for i in range(n):
        if w[i] == 0:
            continue
        Q[i, i] += lam * (w[i] ** 2) - 2 * lam * D * w[i]
        for j in range(i + 1, n):
            if w[j] == 0:
                continue
            Q[i, j] += 2 * lam * w[i] * w[j]

    # --- 3. Battery conflict penalty: mu * (any charge bit)*(any discharge bit) ---
    mu = problem.battery_conflict_penalty_weight
    for kc in range(N_BATTERY_BITS):
        for kd in range(N_BATTERY_BITS):
            i, j = idx[("battery_charge", kc)], idx[("battery_discharge", kd)]
            lo, hi = min(i, j), max(i, j)
            Q[lo, hi] += mu

    return Q


def qubo_objective(Q: np.ndarray, x: np.ndarray) -> float:
    """Evaluates x^T-style QUBO objective for a given bitstring x (0/1 array).
    Used by both the classical brute-force solver and to sanity-check QAOA's
    returned solution — same formula, single source of truth."""
    n = len(x)
    value = 0.0
    for i in range(n):
        if x[i] == 0:
            continue
        value += Q[i, i]
        for j in range(i + 1, n):
            if x[j] == 1:
                value += Q[i, j]
    return value


def qubo_to_ising(Q: np.ndarray) -> tuple[dict[tuple[int, ...], float], float]:
    """
    Converts a QUBO matrix to Ising form via x_i = (1 - z_i) / 2, z_i in {-1,+1}.
    Returns (pauli_coefficients, constant_offset), where pauli_coefficients
    maps a tuple of qubit indices to a coefficient:
      - () -> coefficient of the identity (folded into the returned offset instead)
      - (i,)   -> coefficient of Z_i
      - (i, j) -> coefficient of Z_i Z_j  (i < j)
    Pure numpy/python — no Qiskit dependency. The only Qiskit-dependent step
    is turning this dict into a SparsePauliOp, done separately in
    qubo_to_qiskit_operator() so this conversion itself stays testable.
    """
    n = Q.shape[0]
    linear = {}
    quadratic = {}
    offset = 0.0

    for i in range(n):
        qii = Q[i, i]
        # x_i = (1-z_i)/2  =>  qii*x_i = qii/2 - (qii/2)*z_i
        offset += qii / 2
        linear[i] = linear.get(i, 0.0) - qii / 2

        for j in range(i + 1, n):
            qij = Q[i, j]
            if qij == 0:
                continue
            # x_i*x_j = (1-z_i)(1-z_j)/4 = 1/4 - z_i/4 - z_j/4 + z_i*z_j/4
            offset += qij / 4
            linear[i] = linear.get(i, 0.0) - qij / 4
            linear[j] = linear.get(j, 0.0) - qij / 4
            quadratic[(i, j)] = quadratic.get((i, j), 0.0) + qij / 4

    pauli_coefficients = {(i,): c for i, c in linear.items() if c != 0}
    pauli_coefficients.update({(i, j): c for (i, j), c in quadratic.items() if c != 0})
    return pauli_coefficients, offset


def decode_solution(problem: DispatchProblem, x: np.ndarray) -> dict:
    """Turns a bitstring into human-readable dispatch decisions (MW per
    source, battery action) — used by both the classical solver's output
    and the QAOA result, so both report results in the same shape."""
    idx = problem.var_index
    result = {}
    for s in SOURCES:
        block_mw = problem.block_size_mw(s)
        n_active = sum(int(x[idx[("gen", s, k)]]) for k in range(N_BLOCKS))
        result[f"{s}_mw"] = round(n_active * block_mw, 2)

    charge_mw = sum(
        int(x[idx[("battery_charge", k)]]) * problem.battery_bit_mw(k) for k in range(N_BATTERY_BITS)
    )
    discharge_mw = sum(
        int(x[idx[("battery_discharge", k)]]) * problem.battery_bit_mw(k) for k in range(N_BATTERY_BITS)
    )
    result["battery_charge_mw"] = round(charge_mw, 2)
    result["battery_discharge_mw"] = round(discharge_mw, 2)

    import_mw = sum(                                                       # NEW
        int(x[idx[("import", k)]]) * problem.import_bit_mw(k)              # NEW
        for k in range(N_IMPORT_BITS)                                      # NEW
    )                                                                      # NEW
    result["import_mw"] = round(import_mw, 2) 

    total_supply = sum(result[f"{s}_mw"] for s in SOURCES) + discharge_mw - charge_mw + import_mw
    result["total_supply_mw"] = round(total_supply, 2)
    result["target_demand_mw"] = round(problem.target_demand_mw, 2)
    result["mismatch_mw"] = round(total_supply - problem.target_demand_mw, 2)
    result["battery_conflict"] = bool(charge_mw > 0 and discharge_mw > 0)
    return result