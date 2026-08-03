# Audit & Fix Log — Frontend Rewire to Real Backend

This document records every issue found while auditing the original AI
Studio-scaffolded frontend against the real FastAPI backend, and exactly
what was changed. Keep this for your own records / project report —
transparency about what was fabricated and how it was fixed is worth more
to an evaluator than pretending the scaffold was correct from the start.

## 1. Entire fake backend removed

`server/` (an Express server embedding Vite as middleware) has been deleted.
It:
- Accepted **any** username/password on login and always returned `role: 'admin'`.
- Read real data from `quantum_optimization/results/optimization_summary_next_day.csv`
  and `ml-training/results/*.json` **only** for the default-demand case.
- The moment a custom target demand was requested, it fell back to a
  **fabricated allocation formula** with a code comment falsely claiming to
  "match the Hamiltonian QAOA solver." It did not.
- Hardcoded `grid_stability_score: 98.5`, `cost_reduction_pct: 28.4`,
  `power_loss_reduction_pct: 14.2`, `co2_reduction_pct: 38.6` identically
  for every city, every run.
- Hardcoded circuit summary (`depth: 42`, `total_gates: 114`) identically
  for every city, regardless of real per-city qubit count differences.
- Generated loss curves and actual-vs-predicted charts via `Math.random()`
  and sine waves — not derived from any real training run.
- Generated all city grid-node topology (names, capacities) via a fixed
  formula (`Math.round(1200 * scale)`), with population figures that didn't
  even match the real backend's seed data.

The frontend now talks directly to the real FastAPI backend via a Vite dev
proxy (`vite.config.ts`: `/api` → `http://localhost:8000`).

## 2. `src/types/index.ts` — rewritten to match real Pydantic schemas

Every interface was checked field-by-field against the actual backend
schema files (`backend/app/schemas/*.py`) and corrected. Notable changes:
- `City`: removed `region`, `lat`, `lng`, `baseDemandMw`, `peakDemandMw`,
  `gridHealthScore` (none exist on the real `CityOut`). Added `latitude`,
  `longitude`, `timezone` (which do).
- `GridNode`: removed `name`, `node_type`, `capacity_mw`,
  `current_output_mw` (none exist on the real `GridNodeOut`). The real
  schema is just `{id, city_id, node_code, transmission_capacity_mw, status}`.
- `NationalOverview`/`CityOverview`/`OptimizationResult`: marked every
  metric field genuinely `| null`, since the real backend explicitly
  returns `null` for "no data yet" rather than a placeholder number.
- `ForecastResponse.confidence_interval_mw`: typed as `[number, number] | null`.
  It is **always** `null` on this backend by design (see
  `backend/app/ml/interfaces.py`'s docstring) — point forecasts only, no
  fabricated uncertainty band.
- Added `OptimizationExplanation` and `CircuitSummary` types matching real,
  previously-unused backend endpoints.

## 3. `src/api/client.ts`

- Now stores `refresh_token` alongside `access_token` (was previously
  discarded).
- Added `getLatestAvailableDate()`, `getCircuitSummary()`,
  `getCircuitDiagramUrl()` (fetches the auth-protected PNG as a blob since
  `<img src>` can't send an Authorization header), and
  `getOptimizationExplanation()` — all real endpoints the old UI never called.
- `runWeatherScenario()` no longer defaults to a hardcoded future date
  (`2026-08-01`, which is after the static training dataset ends) — callers
  now pass a real `as_of_date`.

## 4. `src/App.tsx` — auth-gating bug

The original version fired `getCities()`, `getNationalOverview()`, and
`getMe()` unconditionally on page load, before any login. The real backend
correctly rejects these with 401 (`require_any_authenticated_role`) — the
fake Express server never enforced auth at all, so this bug was invisible
until wired to the real backend. Fixed: protected data is only fetched
after a validated session exists; an expired/invalid token now triggers a
clean re-login instead of a silent permanent failure.

## 5. `src/components/DashboardView.tsx`

- Removed a fully-fabricated, always-on "QAOA Dispatched Energy Mix"
  5-source donut chart with hardcoded percentages. Replaced with a genuine
  2-slice Renewable/Non-Renewable chart derived from real
  `avg_renewable_pct`, shown only when that data exists.
- Removed `|| 2500`, `|| 75`, `|| 94` fallback values in the city demand
  bar chart — cities without a real forecast are now simply omitted from
  the chart rather than shown with a fake ~2500 MW bar.
- Removed `city.baseDemandMw` (nonexistent field, rendered blank) — city
  cards now show the real `latest_forecast_mw` from the dashboard overview,
  or an honest "—" if no forecast exists yet.
- Removed `cityData?.renewable_pct || 78` / `cost_reduction_pct || 24` —
  these silently displayed a fake 78%/24% for every city your own "Active
  Grid Telemetry Advisories" banner correctly flagged as having no real
  optimization run. Now shows "—" honestly.
- Removed `city.region` and `city.gridHealthScore` (neither exists on the
  real backend) — replaced with real `timezone` and `population`.

## 6. `src/components/CityExplorerView.tsx`

- Removed the fake generation-type node model (thermal/hydro/wind/solar
  icons keyed off a `node_type` field that doesn't exist on the real
  backend). Nodes are now rendered by their real `status`
  (healthy/degraded/critical/offline) with a matching icon.
- Removed `node.capacity_mw` / `current_output_mw` displays — real nodes
  only expose `transmission_capacity_mw`.
- Header now shows real `timezone`/`population` instead of fabricated
  `region`/`gridHealthScore`.
- Added a genuine "connected transmission lines" count per node, computed
  client-side from the real `transmission_lines` array.

## 7. `src/components/ForecastingView.tsx`

- **Fixed a real crash**: `forecast.confidence_interval_mw[0]}` would throw
  a `TypeError` the moment this ran against real data, since the backend
  deliberately returns `null` there, not a tuple. Now checks for null and
  shows "Not available — point forecast only," matching the backend's own
  stated design philosophy.
- Removed a hardcoded, fake `5.82%` "Validation MAPE Error" card — there is
  no live backend endpoint exposing per-city MAPE, so a fabricated number
  isn't an acceptable substitute. (If you want this back, it would need a
  new backend endpoint surfacing `ml-training/results/<city>_metrics.json`.)
- Removed a hardcoded "convergence over 30 training epochs" claim, which
  was wrong for 7 of 8 cities (real epoch counts range 18-31 depending on
  city, per each city's actual EarlyStopping run). Now derives the real
  epoch count from the length of the fetched loss-curve data.
- Wired `getLatestAvailableDate()` so the "As Of Date" field defaults to a
  real, valid date instead of failing against "today" on a static dataset
  that ends 2024-09-29.

## 8. `src/components/QAOAOptimizationView.tsx` (largest rewrite)

- Removed a hardcoded **"20 Qubits"** claim. Your real, currently-running
  configuration (`N_BLOCKS=1`) uses **10 qubits**, not 20 (the "20 qubits"
  figure belonged to an earlier, since-superseded design). This now reads
  live from `GET /optimization/{id}/circuit-summary`'s real `n_qubits`
  field, so it stays correct even if the backend's qubit configuration
  changes again.
- Removed a `non_local_gates` field reference — it doesn't exist on the
  real circuit-summary response at all. Replaced with the real
  `total_gates` and `gate_counts` fields.
- Removed `result.renewable_pct` and `result.co2_reduction_pct` reads —
  neither field exists on the real `OptimizationResultOut`. Renewable share
  is now correctly derived client-side from `allocation_result`.
- `result.circuit_summary` was previously assumed to be embedded in the
  optimization result — on the real backend it's a **separate** endpoint.
  Now fetched independently via `getCircuitSummary()`.
- Removed the `selectedCity.baseDemandMw`-seeded default target demand
  (nonexistent field). The demand field is now genuinely optional — leaving
  it blank lets the real backend auto-derive a target from a fresh LSTM
  forecast server-side, exactly as `RunGridOptimizationUseCase` already
  supports.
- Added real integrations that existed on the backend but were never
  called by the old UI: `GET /optimization/runs/{id}/explanation`
  (decision-support summary, risk level, expected savings) and
  `GET /optimization/{id}/circuit-diagram` (the actual QAOAAnsatz PNG,
  fetched as an authenticated blob since `<img src>` can't send bearer
  tokens directly).
- Run history table now reads `allocation_result.target_demand_mw`
  (correctly nested) instead of a nonexistent top-level field, and no
  longer shows a `co2_reduction_pct` column at this level since the real
  backend doesn't compute that per-run (only at the dashboard/report layer).

## 9. `src/components/SimulationView.tsx`

- `runWeatherScenario()` now fetches and passes a real `as_of_date`
  (via `getLatestAvailableDate()`) instead of relying on a hardcoded future
  date that would fail against the static dataset.
- Scenario lists are now filtered to the selected city (`s.city ===
  selectedCity.name`) rather than assuming every scenario key applies
  everywhere — the real backend's weather/generation scenarios are
  currently Delhi-scoped only (`heatwave_delhi`, `solar_failure_delhi`,
  etc.), so other cities will honestly show "no scenarios defined yet"
  instead of silently matching nothing.

## 10. `src/components/WeatherView.tsx` and `src/components/Navbar.tsx`

No changes needed to `WeatherView.tsx` — it already matched the real
backend's response shapes exactly. `Navbar.tsx` only needed a logout button
added (a genuine missing feature); the one purely cosmetic element (a
static "50.02 Hz" grid-frequency badge, not backed by any real telemetry
your backend measures) was left as decorative UI chrome, not a data claim.

## 11. Infrastructure

- `package.json`: removed `express`, `cors`, `jsonwebtoken`, `dotenv`,
  `tsx` (only needed by the deleted fake server). `npm run dev` now runs
  Vite directly.
- `vite.config.ts`: dev server now proxies `/api` to
  `http://localhost:8000` (your real backend) instead of embedding the fake
  server as middleware on the same port.
- `tsconfig.json`: removed the now-deleted `server` directory from
  `include`.
- Root `.env.example` was actually a misplaced copy of the **backend's**
  environment variables — replaced with an accurate note that this
  frontend has no environment configuration of its own.

## What to verify yourself before relying on this

I don't have network access to run `npm install && tsc --noEmit` against
the real npm registry in the environment these fixes were written in, so
this has been verified by:
- Grepping every file for any remaining reference to removed/fabricated
  fields (clean).
- Verifying every relative import resolves to a real file (clean).
- Checking brace/paren balance across every rewritten file (clean).

This is **not a substitute for an actual TypeScript compile**. Run
`npm install && npm run lint` yourself before trusting this fully, and
test each page against your live backend — paste me any compiler or
runtime errors you hit and I'll fix them.
