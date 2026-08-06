# Quantum-AI Digital Twin — Indian Smart Grid

Power grid optimizer for 8 Indian cities (Delhi, Mumbai, Pune, Bangalore, Hyderabad, Chennai, Kolkata, Ahmedabad). Forecasts electricity demand with an LSTM model, then optimizes generation dispatch using a hybrid classical + quantum (QAOA) algorithm.

## Architecture

| Layer | Tech | Role |
|---|---|---|
| **Forecasting** | LSTM (TensorFlow) | Predict next-day / next-week load from demand, weather, and calendar features |
| **Optimization** | QUBO → QAOA (Qiskit) + classical solver | Min-cost dispatch across coal / hydro / wind / solar + battery |
| **Backend** | FastAPI + PostgreSQL | JWT auth, REST APIs, async QAOA job polling |
| **Frontend** | React + TypeScript + Vite | Dashboard, city explorer, forecast, QAOA engine, simulation |

## Quick start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

cp .env.example .env           # set JWT_SECRET_KEY and DATABASE_URL
alembic upgrade head           # requires PostgreSQL
python bootstrap_admin.py      # create first admin user
python run_dev.py              # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173 (proxies /api → :8000)
```

### Tests (no Postgres needed)

```bash
cd backend
pytest
```

## ML data & models

Forecasting and weather endpoints need processed CSVs and trained LSTM models:

1. **Data** — generate under `ml-training/data/`:
   ```bash
   cd ml-training/scripts
   python build_training_dataset.py
   python fetch_weather.py
   ```

2. **Train models** — either via the offline scripts or the backend trainer:
   ```bash
   python train_lstm.py                          # offline
   python -m app.ml.trainer --city Delhi         # from backend/
   ```

3. **Set `ML_DATA_DIR`** in `backend/.env` to the absolute path of `ml-training/data` if you run uvicorn from `backend/`.

Trained artifacts live in `backend/app/ml/artifacts/<city>/`.

## Project layout

```
smartgrid/
├── backend/              FastAPI app (canonical runtime code)
│   ├── app/ml/           LSTM forecasting (serves predictions)
│   ├── app/quantum/      QAOA optimization (serves dispatch)
│   └── tests/            Unit + integration tests
├── frontend/             React UI
├── ml-training/scripts/  Offline data prep + LSTM training pipeline
└── quantum_optimization/scripts/  Standalone QAOA experiments (optional)
```

The integrated code in `backend/app/ml/` and `backend/app/quantum/` is what the API uses. The standalone script folders are for offline experimentation only.

## What works without ML setup

- Health check, auth, cities / grid nodes API
- QAOA optimization with an explicit `target_demand_mw` (no forecast needed)
- Dashboard and reports (empty until data is loaded)

## What needs ML artifacts

- Load forecasting (`/api/v1/forecast/...`)
- Weather telemetry
- Forecast-driven optimization (auto demand from LSTM)
