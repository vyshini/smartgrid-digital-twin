# Quantum-AI Digital Twin Frontend

Frontend console for the Indian Smart Grid Digital Twin platform.

## Stack

- React + TypeScript + Vite
- Material UI (dark glassmorphism theme)
- Redux Toolkit (session + UI state)
- React Query (server-state + polling)
- React Router
- Framer Motion
- Recharts
- Leaflet (India grid node map)

## Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Default backend target: `http://localhost:8000/api/v1`

## Integrated Modules

- JWT login flow (`/auth/login`, refresh, `/auth/me`)
- National dashboard (`/dashboard/overview`)
- India city/grid map (`/cities`, `/cities/{id}`)
- LSTM forecasting UI (`/forecast/...`)
- QAOA optimization UI + job polling (`/optimization/...`)
- Weather + generation scenarios (`/simulation/...`, `/optimization/.../generation-scenarios/...`)
- Analytics charts (loss curve, actual vs predicted)
- CSV report export from live API data

## Quality Checks

```bash
npm run lint
npm run build
```
