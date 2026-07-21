# Phase 4 — Hybrid Quantum-Classical QAOA Optimization

## Scope (as agreed)
Single city, single time-step generation dispatch: given a target demand
(e.g. from Phase 3's next_day forecast) and a city's real installed
capacity, decide how much of each source to dispatch — plus battery
charge/discharge — to meet demand at minimum cost while preferring
renewables, formulated as a QUBO and solved via QAOA (Qiskit + Aer +
COBYLA), with a classical exact solver as the mandatory ground-truth
comparison.

## Files, in the order to read/run them

1. **`generation_capacity.py`** — real installed capacity (MoSPI Energy
   Statistics 2023, CEA/MNRE source, as on 31.03.2022) for all 8 cities.
   Nuclear deliberately excluded — see its docstring for why (centrally-owned
   accounting + genuinely low operational flexibility in practice).
2. **`hamiltonian_builder.py`** — QUBO construction and QUBO→Ising
   conversion. **Fully tested** — verified exact (to float64 precision) via
   200 random bitstring trials against real Delhi capacity data.
3. **`classical_solver.py`** — exact brute-force solver (vectorized numpy,
   ~4s for a 20-qubit problem) and a greedy heuristic fallback for larger
   problems. **Fully tested** — verified against real Delhi capacity across
   4 different demand targets, producing physically sensible dispatch
   decisions (e.g. battery charging to absorb excess generation, discharging
   to cover shortfalls).
4. **`qaoa_optimizer.py`** — the actual QAOA run, via `qiskit_algorithms`
   (NOT the deprecated `qiskit.algorithms`) + `qiskit_aer`'s Sampler +
   COBYLA. **Partially tested**: the two pure-Python helper functions
   (`_pauli_string`, `sample_most_likely_bitstring`) are verified correct
   in isolation. The actual QAOA execution could not be run in this
   sandbox — no qiskit/qiskit-aer/qiskit-algorithms installed, no network
   to install them.
5. **`circuit_visualizer.py`** — circuit diagram + structural stats.
   **Untested** for the same reason as (4).

## What you need to validate on your machine

```bash
pip install qiskit qiskit-aer qiskit-algorithms matplotlib
cd quantum-optimization/scripts
python qaoa_optimizer.py      # smoke test: 1 city, reps=1, 512 shots, 50 iterations (fast)
```

This prints QAOA's dispatch decision **alongside the classical optimum**,
the objective gap between them, and an `optimization_score`. That
comparison is the whole point — a QAOA result reported without it isn't
trustworthy on its own, the same reasoning that caught the LSTM
underperforming the persistence baseline in Phase 3. Please paste me the
output before we build anything on top of this (API integration, running
all 8 cities, etc.) — there are a few things I genuinely can't verify
without a real quantum-circuit execution: whether `compute_minimum_eigenvalue`
converges sensibly with these defaults, whether the QAOAAnsatz renders
correctly, and whether reps=1/2 is even enough for a 20-qubit problem
(real QAOA often needs more depth than you'd guess, and this is exactly
the kind of parameter I flagged as "not tuned" rather than pretend to
have validated).

## Known modeling limitations (stated plainly, not hidden)

- **Nuclear excluded** from the dispatch decision (treated as fixed
  baseload) — see `generation_capacity.py`.
- **Cost weights are illustrative relative preferences** (solar cheapest,
  coal most expensive), reflecting India's real renewable-must-run dispatch
  policy — not measured Rs/kWh figures.
- **Battery power rating has no real per-city sourced value** — India's
  grid-scale battery storage is still nascent with sparse public
  per-city data. Passed as a parameter (`battery_power_rating_mw`), not
  hardcoded, so a real figure can be substituted once available.
- **Delhi and Mumbai/Pune share Maharashtra's full state capacity** in the
  current data — not scaled by city population share yet (see
  `generation_capacity.py`'s note on this).
- **This is single-city, single-time-step** — the spec's fuller scope
  (national optimization, multi-period scheduling, transmission routing
  between cities) is future work, not yet attempted.
