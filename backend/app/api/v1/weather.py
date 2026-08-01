"""
Weather API — reads directly from the real per-city weather CSVs
(fetch_weather.py's output, ml-training/data/raw/weather_<city>.csv)
rather than the WeatherReading DB table, which has no ingestion pipeline
populating it yet (see project scope notes — live ingestion is out of
scope for this timeline). This mirrors CSVForecastDataProvider's approach:
real historical data, honestly sourced, no fabrication.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.core.rbac import require_any_authenticated_role

router = APIRouter(prefix="/weather", tags=["weather"])

SUPPORTED_CITIES = {
    "Delhi", "Mumbai", "Pune", "Bangalore",
    "Hyderabad", "Chennai", "Kolkata", "Ahmedabad",
}


@lru_cache(maxsize=8)
def _load_weather_csv(city: str) -> pd.DataFrame:
    settings = get_settings()
    path = Path(settings.ML_DATA_DIR) / "raw" / f"weather_{city.lower()}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No weather data file for '{city}' at {path}")
    return pd.read_csv(path, index_col="date", parse_dates=True)


@router.get("/{city}/current")
async def get_current_weather(
    city: str, _user=Depends(require_any_authenticated_role)
) -> dict:
    """Returns the most recent real weather record on file for `city` —
    'current' in the sense of 'latest available real data', not a live
    reading, since no live weather feed exists in this project's scope."""
    if city not in SUPPORTED_CITIES:
        raise HTTPException(status_code=404, detail=f"'{city}' is not a supported city.")
    try:
        df = _load_weather_csv(city)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    latest = df.iloc[-1]
    return {
        "city": city,
        "date": str(df.index[-1].date()),
        "temperature_c": round(float(latest["temperature_c"]), 2),
        "humidity_pct": round(float(latest["humidity_pct"]), 2),
        "wind_speed_kmph": round(float(latest["wind_speed_kmph"]), 2),
        "solar_irradiance": round(float(latest["solar_irradiance"]), 2),
        "precipitation_mm": round(float(latest["precipitation_mm"]), 2),
    }


@router.get("/{city}/history")
async def get_weather_history(
    city: str,
    days: int = Query(default=14, ge=1, le=365),
    end_date: date | None = None,
    _user=Depends(require_any_authenticated_role),
) -> list[dict]:
    """Real historical weather for `city`, ending at end_date (defaults to
    the latest real date on file) going back `days` days."""
    if city not in SUPPORTED_CITIES:
        raise HTTPException(status_code=404, detail=f"'{city}' is not a supported city.")
    try:
        df = _load_weather_csv(city)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    end_ts = pd.Timestamp(end_date) if end_date else df.index.max()
    start_ts = end_ts - pd.Timedelta(days=days - 1)
    window = df.loc[start_ts:end_ts]

    return [
        {
            "date": str(idx.date()),
            "temperature_c": round(float(row["temperature_c"]), 2),
            "humidity_pct": round(float(row["humidity_pct"]), 2),
            "wind_speed_kmph": round(float(row["wind_speed_kmph"]), 2),
            "solar_irradiance": round(float(row["solar_irradiance"]), 2),
            "precipitation_mm": round(float(row["precipitation_mm"]), 2),
        }
        for idx, row in window.iterrows()
    ]