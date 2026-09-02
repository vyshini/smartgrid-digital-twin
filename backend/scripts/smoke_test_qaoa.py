"""
QAOA smoke test -- run this BEFORE trusting any QAOA result the API
returns. qaoa_optimizer.py's own module docstring admits it was written
without qiskit installed and has never been executed end-to-end. This
script isolates every stage so a failure points at exactly which layer
broke, and prints real numbers (timing, objective gap, optimization
score) instead of asking you to trust the code on faith.

WHAT THIS DOES NOT DO: reduce problem size. hamiltonian_builder.py's
N_BLOCKS=1 already puts you at the smallest configured qubit count (10
qubits: 4 sources x 1 block + 2x2 battery bits + 2 import bits) --
see hamiltonian_builder.py's own comment on why N_BLOCKS was reduced
from 4 to 1 for local feasibility. This script keeps reps/shots/maxiter
low instead, since qubit count isn't the free variable here.

Run from repo root:
    python -m backend.scripts.smoke_test_qaoa
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

# --- Make `app.*` importable regardless of current working directory --
# backend/app/quantum/*.py uses ABSOLUTE imports like
# "from app.quantum.generation_capacity import ..." which only resolve if
# `backend/` itself is on sys.path (this is what pytest's
# pythonpath=["."] setting and `cd backend && uvicorn app.main:app` both
# provide implicitly). Running this script via `python -m
# backend.scripts.smoke_test_qaoa` from the repo root does NOT provide
# that -- it makes `backend` importable, not `app`. Inserting the path
# explicitly here removes the ambiguity instead of relying on whatever
# directory happens to be cwd.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --- Stage 0: package/version diagnostics -----------------------------
print("=" * 70)
print("STAGE 0: Package versions")
print("=" * 70)

try:
    import qiskit
    print(f"  qiskit: {qiskit.__version__}")
except ImportError as e:
    print(f"  [FATAL] qiskit not importable: {e}")
    sys.exit(1)

try:
    import qiskit_algorithms
    print(f"  qiskit_algorithms: {qiskit_algorithms.__version__}")
except ImportError as e:
    print(f"  [FATAL] qiskit_algorithms not importable: {e}")
    print("  Install with: pip install qiskit-algorithms")
    sys.exit(1)

try:
    import qiskit_aer
    print(f"  qiskit_aer: {qiskit_aer.__version__} (not required by the current")
    print("    qaoa_optimizer.py, which uses qiskit.primitives.Sampler instead --")
    print("    still listed in requirements.txt, so confirming it's present too)")
except ImportError:
    print("  qiskit_aer: not installed (fine -- qaoa_optimizer.py no longer requires it)")

# Check the QAOA constructor signature BEFORE running anything --
# qaoa_optimizer.py's module docstring flags a real version-fragility
# issue: a 'transpiler' kwarg that only exists in some qiskit_algorithms
# releases. Surface this now, not as a cryptic TypeError mid-run.
import inspect
from qiskit_algorithms import QAOA
qaoa_params = list(inspect.signature(QAOA.__init__).parameters.keys())
print(f"  QAOA.__init__ accepts: {qaoa_params}")
if "transpiler" in qaoa_params:
    print("  NOTE: this qiskit_algorithms version DOES accept 'transpiler' -- "
          "if you ever swap back to Aer's SamplerV2, that kwarg is available here.")
else:
    print("  NOTE: this qiskit_algorithms version does NOT accept 'transpiler' -- "
          "matches the current qaoa_optimizer.py, which avoids it by using "
          "qiskit.primitives.Sampler (V1) instead of Aer's SamplerV2. Good.")

# --- Stage 1: import project code --------------------------------------
print("\n" + "=" * 70)
print("STAGE 1: Import project modules")
print("=" * 70)
try:
    from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY
    from app.quantum.hamiltonian_builder import DispatchProblem, build_qubo, qubo_to_ising
    from app.quantum.qaoa_optimizer import build_qiskit_operator, run_qaoa
    from app.quantum.classical_solver import solve_exact_brute_force
    print("  OK -- all project modules imported cleanly.")
except Exception as e:
    print(f"  [FATAL] Import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--reps", type=int, default=1)
parser.add_argument("--shots", type=int, default=256)
parser.add_argument("--maxiter", type=int, default=20)
parser.add_argument("--target-demand-mw", type=float, default=270.0)
parser.add_argument("--battery-conflict-penalty-weight", type=float, default=3.0)
parser.add_argument("--seed", type=int, default=42)
args = parser.parse_args()

# --- Stage 2: build the problem (pure numpy, already unit-tested) ------
print("\n" + "=" * 70)
print(f"STAGE 2: Build DispatchProblem (Delhi, target={args.target_demand_mw} MW, "
      f"battery_conflict_penalty_weight={args.battery_conflict_penalty_weight})")
print("=" * 70)
# 270 MW is the SAME scenario test_hamiltonian_builder.py's
# test_exact_match_scenario_hydro_plus_solar already validates against a
# known correct classical answer (hydro=59, solar=211, coal=0) -- reusing
# it here means we have a known-good expected answer to sanity-check the
# QAOA result against, not just "did it run without crashing."
capacity = CITY_GENERATION_CAPACITY["Delhi"]
problem = DispatchProblem(
    capacity=capacity,
    target_demand_mw=args.target_demand_mw,
    battery_power_rating_mw=100,
    battery_conflict_penalty_weight=args.battery_conflict_penalty_weight,
)
print(f"  n_qubits = {problem.n_qubits}")
print(f"  capacity = {capacity}")

t0 = time.perf_counter()
Q = build_qubo(problem)
t1 = time.perf_counter()
print(f"  build_qubo: {t1 - t0:.3f}s, Q shape = {Q.shape}")

pauli_coefficients, offset = qubo_to_ising(Q)
t2 = time.perf_counter()
print(f"  qubo_to_ising: {t2 - t1:.3f}s, {len(pauli_coefficients)} nonzero Pauli terms")

# --- Stage 3: classical ground truth (already unit-tested, should be fast) ---
print("\n" + "=" * 70)
print("STAGE 3: Classical exact solve (ground truth QAOA gets checked against)")
print("=" * 70)
t3 = time.perf_counter()
classical = solve_exact_brute_force(problem, Q)
t4 = time.perf_counter()
print(f"  solve_exact_brute_force: {t4 - t3:.3f}s")
print(f"  classical objective_value = {classical['objective_value']:.4f}")

from app.quantum.hamiltonian_builder import decode_solution
classical_decoded = decode_solution(problem, classical["x"])
print(f"  classical decoded dispatch: {classical_decoded}")
print("  Expected (per test_hamiltonian_builder.py): hydro~59, solar~211, coal=0, mismatch~0")

# --- Stage 4: the actual QAOA run (THE UNVERIFIED PART) ----------------
print("\n" + "=" * 70)
print(f"STAGE 4: QAOA run (reps={args.reps}, shots={args.shots}, maxiter={args.maxiter})")
print("=" * 70)
print("  This is the part that has never executed before. Timing it fully.")

t5 = time.perf_counter()
try:
    result = run_qaoa(problem, reps=args.reps, shots=args.shots, maxiter=args.maxiter, seed=args.seed)
except Exception as e:
    print(f"\n  [FATAL] run_qaoa raised an exception: {type(e).__name__}: {e}")
    traceback.print_exc()
    print("\n  Paste this full traceback back to Claude -- the exception type and")
    print("  message tell us exactly which layer (Sampler construction, QAOA")
    print("  construction, compute_minimum_eigenvalue, or bitstring decoding) failed.")
    sys.exit(1)
t6 = time.perf_counter()

print(f"\n  run_qaoa completed in {t6 - t5:.1f}s")
print(f"  QAOA decoded dispatch:      {result['qaoa']['decoded']}")
print(f"  Classical baseline decoded: {result['classical_baseline']['decoded']}")
print(f"  Objective gap (QAOA - classical optimum): {result['objective_gap']:.6f}")
print(f"  Optimization score: {result['optimization_score']}")
print(f"  QAOA matched classical optimum exactly: {result['qaoa_matches_classical_optimum']}")

# --- Stage 5: sanity verdict --------------------------------------------
print("\n" + "=" * 70)
print("STAGE 5: Verdict")
print("=" * 70)
mismatch = abs(result["qaoa"]["decoded"].get("mismatch_mw", 999))
if result["qaoa_matches_classical_optimum"]:
    print("  PASS: QAOA found the exact classical optimum on this 10-qubit problem.")
    print("  This is a reps=1/shots=256/maxiter=20 result -- a real production run")
    print("  should use higher values (try reps=2, shots=1024, maxiter=100 next)")
    print("  and confirm it STILL matches, ideally across 2-3 different demand targets.")
elif mismatch < 20:
    print(f"  PARTIAL: QAOA did not match the exact optimum (score={result['optimization_score']}), "
          f"but landed physically close (mismatch={mismatch:.1f} MW). This can be a real, "
          f"honest quantum-optimizer limitation at low reps/shots/maxiter -- try increasing "
          f"reps/shots/maxiter before concluding something is broken.")
else:
    print(f"  CONCERNING: QAOA's dispatch mismatch is {mismatch:.1f} MW -- worth increasing "
          f"maxiter/reps before drawing conclusions, but if this persists at higher settings, "
          f"something in the Sampler/QAOA wiring likely needs investigation, not just more compute.")

print("\nNext step: paste this ENTIRE output back, including Stage 0's version info,")
print("even if everything passed -- the exact numbers matter for deciding what")
print("reps/shots/maxiter to use for the real 8-city production run.")