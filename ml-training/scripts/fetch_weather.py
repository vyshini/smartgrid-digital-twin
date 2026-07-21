"""
Fetches REAL historical weather from Open-Meteo's Archive API (ERA5
reanalysis) for all 8 cities, over the same date range as the real demand
data. No API key required (see https://open-meteo.com/en/docs/historical-weather-api).

This script makes live network calls and must be run on a machine with
internet access — it was written against Open-Meteo's documented API but
could not be executed/tested in the sandbox this project was built in
(no network access there). Validate the first city's output carefully
before trusting the rest — cross-check a known date/value against
weather.com or another source for that city, the same way we validated
the demand data against the March 2020 lockdown.

Run from ml-training/scripts/:
    python fetch_weather.py

Outputs one CSV per city to ml-training/data/raw/weather_<city>.csv
"""
import time
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Real city coordinates, from Phase 1's seed data (docs/database-schema.sql).
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Bangalore": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Ahmedabad": (23.0225, 72.5714),
    "Pune": (18.5204, 73.8567),
}

# Match the real demand data's coverage window (see build_training_dataset.py output).
START_DATE = "2013-01-06"
END_DATE = "2024-09-29"

HOURLY_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation,precipitation"


def fetch_city_year(lat: float, lon: float, year: int) -> pd.DataFrame:
    """One year at a time — keeps individual requests small and reliable."""
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": HOURLY_VARS,
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time")


def fetch_city(city: str, lat: float, lon: float) -> pd.DataFrame:
    start_year = pd.Timestamp(START_DATE).year
    end_year = pd.Timestamp(END_DATE).year
    yearly_frames = []
    for year in range(start_year, end_year + 1):
        print(f"  {city}: fetching {year}...")
        yearly_frames.append(fetch_city_year(lat, lon, year))
        time.sleep(1)  # be a good API citizen — no key required, but don't hammer it

    hourly = pd.concat(yearly_frames).sort_index()
    hourly = hourly.loc[START_DATE:END_DATE]

    # Aggregate hourly -> daily to match the demand data's granularity.
    daily = hourly.resample("D").agg({
        "temperature_2m": "mean",
        "relative_humidity_2m": "mean",
        "wind_speed_10m": "max",
        "shortwave_radiation": "sum",  # proxy for daily solar irradiance total
        "precipitation": "sum",
    })
    daily.columns = [
        "temperature_c", "humidity_pct", "wind_speed_kmph",
        "solar_irradiance", "precipitation_mm",
    ]
    daily.index.name = "date"
    return daily


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for city, (lat, lon) in CITY_COORDINATES.items():
        out_path = RAW_DIR / f"weather_{city.lower()}.csv"
        if out_path.exists():
            print(f"{city}: {out_path} already exists, skipping (delete it to refetch)")
            continue
        print(f"Fetching real weather for {city} ({START_DATE} to {END_DATE})...")
        daily = fetch_city(city, lat, lon)
        daily.to_csv(out_path)
        print(f"  -> {out_path} ({len(daily)} rows)")


if __name__ == "__main__":
    main()