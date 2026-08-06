"""
Ported from ml-training/scripts/feature_engineering.py — kept in sync
with that file. *** UPDATED to match the delta-target / cyclical-encoding
/ extended-lag fixes applied there *** — this backend copy was missed
when those fixes were first made, causing GBTForecaster to fail with
"Missing expected feature columns" since the GBT models were trained on
the updated feature set but this file was still producing the old one.

data_dir stays a constructor/parameter argument (not hardcoded), same as
before — this backend copy runs with working directory not guaranteed to
be ml-training/scripts/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FESTIVAL_NAME_KEYWORDS = ["Diwali", "Holi", "Dussehra", "Eid", "Christmas", "Navratri", "Durga Puja"]

LOOKBACK_DAYS = 14

# *** UPDATED to match ml-training/scripts/feature_engineering.py exactly ***
DEFAULT_FEATURE_COLUMNS = [
    "total_demand_mw", "residential_mw", "commercial_mw", "industrial_mw",
    "temperature_c", "humidity_pct", "wind_speed_kmph", "solar_irradiance", "precipitation_mm",
    "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos",
    "is_weekend", "is_holiday", "is_festival",
    "total_demand_mw_lag_1", "total_demand_mw_lag_2", "total_demand_mw_lag_3",
    "total_demand_mw_lag_7", "total_demand_mw_lag_14", "total_demand_mw_lag_28",
    "total_demand_mw_rolling_mean_3", "total_demand_mw_rolling_mean_7", "total_demand_mw_rolling_std_7",
]


def load_city_dataset(city: str, data_dir: Path) -> pd.DataFrame:
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
    """*** UPDATED: cyclical sin/cos encoding, matching ml-training's fix. ***"""
    import holidays

    df = df.copy()
    years = sorted(set(df.index.year))
    in_holidays = holidays.country_holidays("IN", years=years)

    dow = df.index.dayofweek
    month = df.index.month

    df["day_of_week"] = dow
    df["month"] = month
    df["day_of_week_sin"] = np.sin(2 * np.pi * dow / 7)
    df["day_of_week_cos"] = np.cos(2 * np.pi * dow / 7)
    df["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    df["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)

    df["is_weekend"] = (df.index.dayofweek >= 5).astype(int)
    df["is_holiday"] = df.index.to_series().apply(lambda d: d in in_holidays).astype(int)
    df["is_festival"] = df.index.to_series().apply(
        lambda d: d in in_holidays and any(kw in in_holidays.get(d, "") for kw in FESTIVAL_NAME_KEYWORDS)
    ).astype(int)
    return df


def add_lag_features(df: pd.DataFrame, target_col: str = "total_demand_mw") -> pd.DataFrame:
    """*** UPDATED: added 14/28-day lags and 3-day rolling mean. ***"""
    df = df.copy()
    for lag in (1, 2, 3, 7, 14, 28):
        df[f"{target_col}_lag_{lag}"] = df[target_col].shift(lag)
    df[f"{target_col}_rolling_mean_3"] = df[target_col].shift(1).rolling(3).mean()
    df[f"{target_col}_rolling_mean_7"] = df[target_col].shift(1).rolling(7).mean()
    df[f"{target_col}_rolling_std_7"] = df[target_col].shift(1).rolling(7).std()
    return df


def build_supervised_windows(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_demand_mw",
    lookback: int = LOOKBACK_DAYS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """*** UPDATED: delta targets + anchors, matching ml-training's fix. ***"""
    df = df.dropna(subset=feature_cols + [target_col]).sort_index()
    values = df[feature_cols].to_numpy(dtype=np.float32)
    target = df[target_col].to_numpy(dtype=np.float32)
    dates = df.index.to_numpy()

    X, y_next_day, y_next_week, anchors, window_end_dates = [], [], [], [], []
    n = len(df)
    for i in range(n - lookback - 7 + 1):
        window = values[i : i + lookback]
        anchor_idx = i + lookback - 1
        next_day_idx = i + lookback
        next_week_idx = i + lookback + 6

        window_dates = dates[i : i + lookback + 7]
        if not _is_contiguous_daily(window_dates):
            continue

        anchor_value = target[anchor_idx]
        X.append(window)
        y_next_day.append(target[next_day_idx] - anchor_value)
        y_next_week.append(target[next_week_idx] - anchor_value)
        anchors.append(anchor_value)
        window_end_dates.append(dates[anchor_idx])

    return (
        np.array(X),
        np.array(y_next_day),
        np.array(y_next_week),
        np.array(anchors),
        np.array(window_end_dates),
    )


def _is_contiguous_daily(dates: np.ndarray) -> bool:
    diffs = np.diff(dates).astype("timedelta64[D]").astype(int)
    return bool(np.all(diffs == 1))