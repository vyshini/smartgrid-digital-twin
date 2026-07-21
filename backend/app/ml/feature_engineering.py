"""
Ported from ml-training/scripts/feature_engineering.py. Logic is
unchanged — same merge, same calendar features, same windowing — but the
data location is now a constructor/parameter argument instead of a
hardcoded relative path, since this module now runs as part of a
deployed backend (working directory is not guaranteed to be
ml-training/scripts/ anymore).

trainer.py is the only caller of build_supervised_windows here; the
online prediction path (lstm_model.LSTMForecaster) does NOT use this
module directly — it receives an already-built DataFrame via its
feature_data_provider callable (see lstm_model.py's docstring). This
module produces the OFFLINE, historical-window shape training needs;
preprocessing.build_prediction_window produces the ONLINE, single-window
shape prediction needs. Both must agree on feature_cols and lookback, or
a served model's inputs won't match what it was trained on — trainer.py
saves feature_cols alongside the model specifically to guard against this
drifting apart silently (see model_registry.py).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FESTIVAL_NAME_KEYWORDS = ["Diwali", "Holi", "Dussehra", "Eid", "Christmas", "Navratri", "Durga Puja"]

LOOKBACK_DAYS = 14

DEFAULT_FEATURE_COLUMNS = [
    "total_demand_mw", "residential_mw", "commercial_mw", "industrial_mw",
    "temperature_c", "humidity_pct", "wind_speed_kmph", "solar_irradiance", "precipitation_mm",
    "day_of_week", "month", "is_weekend", "is_holiday", "is_festival",
    "total_demand_mw_lag_1", "total_demand_mw_lag_2", "total_demand_mw_lag_3", "total_demand_mw_lag_7",
    "total_demand_mw_rolling_mean_7", "total_demand_mw_rolling_std_7",
]


def load_city_dataset(city: str, data_dir: Path) -> pd.DataFrame:
    """
    Merges real demand + real weather for one city. `data_dir` must
    contain `processed/<city>.csv` (build_training_dataset.py output) and
    `raw/weather_<city>.csv` (fetch_weather.py output) — same file
    layout as ml-training/data/, just passed in explicitly rather than
    assumed relative to this file's location.
    """
    demand_path = data_dir / "processed" / f"{city.lower()}.csv"
    weather_path = data_dir / "raw" / f"weather_{city.lower()}.csv"

    if not demand_path.exists():
        raise FileNotFoundError(f"Missing real demand file: {demand_path}.")
    if not weather_path.exists():
        raise FileNotFoundError(f"Missing real weather file: {weather_path}.")

    demand = pd.read_csv(demand_path, index_col="date", parse_dates=True)
    weather = pd.read_csv(weather_path, index_col="date", parse_dates=True)

    df = demand.join(weather, how="inner")
    if len(df) == 0:
        raise ValueError(f"No overlapping dates between demand and weather data for {city}.")

    df = add_calendar_features(df)
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    import holidays

    df = df.copy()
    years = sorted(set(df.index.year))
    in_holidays = holidays.country_holidays("IN", years=years)

    df["day_of_week"] = df.index.dayofweek
    df["month"] = df.index.month
    df["is_weekend"] = (df.index.dayofweek >= 5).astype(int)
    df["is_holiday"] = df.index.to_series().apply(lambda d: d in in_holidays).astype(int)
    df["is_festival"] = df.index.to_series().apply(
        lambda d: d in in_holidays and any(kw in in_holidays.get(d, "") for kw in FESTIVAL_NAME_KEYWORDS)
    ).astype(int)
    return df


def add_lag_features(df: pd.DataFrame, target_col: str = "total_demand_mw") -> pd.DataFrame:
    df = df.copy()
    for lag in (1, 2, 3, 7):
        df[f"{target_col}_lag_{lag}"] = df[target_col].shift(lag)
    df[f"{target_col}_rolling_mean_7"] = df[target_col].shift(1).rolling(7).mean()
    df[f"{target_col}_rolling_std_7"] = df[target_col].shift(1).rolling(7).std()
    return df


def build_supervised_windows(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_demand_mw",
    lookback: int = LOOKBACK_DAYS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    df = df.dropna(subset=feature_cols + [target_col]).sort_index()
    values = df[feature_cols].to_numpy(dtype=np.float32)
    target = df[target_col].to_numpy(dtype=np.float32)
    dates = df.index.to_numpy()

    X, y_next_day, y_next_week, window_end_dates = [], [], [], []
    n = len(df)
    for i in range(n - lookback - 7 + 1):
        window = values[i : i + lookback]
        next_day_idx = i + lookback
        next_week_idx = i + lookback + 6

        window_dates = dates[i : i + lookback + 7]
        if not _is_contiguous_daily(window_dates):
            continue

        X.append(window)
        y_next_day.append(target[next_day_idx])
        y_next_week.append(target[next_week_idx])
        window_end_dates.append(dates[i + lookback - 1])

    return (
        np.array(X),
        np.array(y_next_day),
        np.array(y_next_week),
        np.array(window_end_dates),
    )


def _is_contiguous_daily(dates: np.ndarray) -> bool:
    diffs = np.diff(dates).astype("timedelta64[D]").astype(int)
    return bool(np.all(diffs == 1))