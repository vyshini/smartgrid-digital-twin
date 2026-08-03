# Smart Grid Digital Twin — Frontend

React + TypeScript + Tailwind console for the Quantum-AI Digital Twin
(Indian Smart Grid Load Forecasting & QAOA Optimization) project.

This UI was originally scaffolded from an AI Studio template with a fabricated
mock Express backend. That mock backend has been **removed entirely**. This
version talks exclusively to the real FastAPI backend in `backend/` — real
bcrypt-authenticated JWT login, real trained LSTM forecasts, real QUBO/QAOA
optimization runs via Qiskit, real Postgres-backed history. See `CHANGES.md`
for a full audit of what was fabricated in the original scaffold and how each
issue was fixed.

## Prerequisites

- Node.js 20+
- Your real FastAPI backend (`backend/`) running and reachable at
  `http://localhost:8000` — see `backend/README.md` for setup
  (`alembic upgrade head`, `bootstrap_admin.py`, `uvicorn`/`run_dev.py`)

## Run Locally

```bash
npm install
npm run dev
```

Opens at `http://localhost:5173`. The dev server proxies all `/api/*`
requests to `http://localhost:8000` (see `vite.config.ts`) — no `.env`
configuration needed for local development.

**You must have the real backend running first**, with at least one admin
user bootstrapped (`python backend/bootstrap_admin.py` or your own reset
script), since this frontend requires a genuine login — there is no mock/
demo account.

## Build

```bash
npm run build   # outputs to dist/
npm run preview # serve the production build locally
```

If you deploy the built frontend on a different origin than the backend,
update the proxy target in `vite.config.ts`, or put both behind a reverse
proxy that forwards `/api` to the FastAPI backend.

## Type-checking

```bash
npm run lint    # tsc --noEmit
```

## Feature Map (real backend endpoint each page depends on)

| Page | Backend endpoints |
|---|---|
| National Grid Overview | `GET /dashboard/overview`, `GET /cities` |
| City Digital Twin | `GET /cities/{id}` |
| LSTM Load Forecast | `GET /forecast/{city}/{horizon}`, `/loss-curve`, `/actual-vs-predicted`, `/latest-available-date` |
| Quantum QAOA Engine | `POST /optimization/{id}/run` (async job), `/jobs/{job_id}`, `/latest`, `/history`, `/circuit-summary`, `/circuit-diagram`, `/runs/{id}/explanation` |
| Scenario Sandbox | `GET/POST /simulation/weather-scenarios*`, `GET/POST /optimization/{id}/generation-scenarios*` |
| Weather Telemetry | `GET /weather/{city}/current`, `/history` |

## Known limitations (stated plainly, not hidden)

- **No client-side generation-type breakdown per grid node.** The real
  backend's `GridNodeOut` schema is a generic substation model (id, node
  code, transmission capacity, health status) — there's no thermal/hydro/
  wind/solar categorization at the node level. The City Digital Twin page
  reflects this honestly rather than inventing a richer node taxonomy.
- **National "Renewable vs Non-Renewable" mix is a 2-slice aggregate**,
  derived from `avg_renewable_pct`. A full per-source (coal/hydro/wind/
  solar) national breakdown would require fetching every city's latest
  `allocation_result` and summing client-side — not yet implemented.
- **Dashboard metrics reflect however many cities currently have real
  optimization/forecast runs** — `cities_with_data` is shown alongside
  `total_cities` so this isn't hidden. Run more cities through the QAOA
  Engine tab to populate more of the dashboard with real numbers.
