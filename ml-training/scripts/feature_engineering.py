"""
Merges the real per-city demand data (build_training_dataset.py output),
real weather data (fetch_weather.py output), and a real Indian public
holiday calendar (the `holidays` package, IN country code) into a single
feature table, then windows it into LSTM-ready supervised sequences for
the next_day and next_week horizons.

*** CHANGE (delta-target fix) ***
Targets are now DELTAS from the last real day in each window
(anchor = target_col value at window_end_date), not absolute demand
levels. This matches the fix already documented in
quantum_optimization/scripts/forecast_to_dispatch.py's module docstring:
an earlier version trained on absolute levels and was found to
underperform a trivial persistence baseline, because the model had to
relearn "tomorrow ~= today" from scratch instead of focusing purely on
the harder part (how much change, and why).

y_next_day  = demand(t+1) - demand(t)      where t = window_end_date
y_next_week = demand(t+7) - demand(t)

`anchors` (demand(t), i.e. the real value ON window_end_date) is returned
alongside the deltas so callers can reconstruct absolute MW:
    absolute_prediction = anchor + model_predicted_delta
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

FESTIVAL_NAME_KEYWORDS = ["Diwali", "Holi", "Dussehra", "Eid", "Christmas", "Navratri", "Durga Puja"]

LOOKBACK_DAYS = 14


def load_city_dataset(city: str) -> pd.DataFrame:
    demand_path = DATA_DIR / "processed" / f"{city.lower()}.csv"
    weather_path = DATA_DIR / "raw" / f"weather_{city.lower()}.csv"

    if not demand_path.exists():
        raise FileNotFoundError(
            f"Missing real demand file: {demand_path}. Run build_training_dataset.py first."
        )
    if not weather_path.exists():
        raise FileNotFoundError(
            f"Missing real weather file: {weather_path}. Run fetch_weather.py first "
            f"(requires internet access)."
        )

    demand = pd.read_csv(demand_path, index_col="date", parse_dates=True)
    weather = pd.read_csv(weather_path, index_col="date", parse_dates=True)

    df = demand.join(weather, how="inner")
    if len(df) == 0:
        raise ValueError(f"No overlapping dates between demand and weather data for {city}.")

    df = add_calendar_features(df)
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    *** CHANGE (cyclical encoding fix) ***
    day_of_week and month are no longer left as raw integers (0-6, 1-12).
    Fed raw, a neural net implicitly treats "6" as greater than "0", which
    is wrong for a cyclic quantity (Sunday isn't "more" than Monday,
    December isn't "more" than January). Replaced with sin/cos pairs,
    which preserve adjacency correctly (day 6 and day 0 are close in
    sin/cos space, matching reality).

    day_of_week / month are KEPT (not dropped) for backward compatibility
    with anything reading them directly, but DEFAULT_FEATURE_COLUMNS below
    now points the model at the cyclical versions instead.
    """
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
    df = df.copy()
    for lag in (1, 2, 3, 7, 14, 28):  # *** CHANGE: added 14, 28-day lags ***
        df[f"{target_col}_lag_{lag}"] = df[target_col].shift(lag)
    df[f"{target_col}_rolling_mean_3"] = df[target_col].shift(1).rolling(3).mean()   # *** NEW ***
    df[f"{target_col}_rolling_mean_7"] = df[target_col].shift(1).rolling(7).mean()
    df[f"{target_col}_rolling_std_7"] = df[target_col].shift(1).rolling(7).std()
    return df


def build_supervised_windows(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_demand_mw",
    lookback: int = LOOKBACK_DAYS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Builds sliding windows. X[i] = feature_cols over [i, i+lookback).

    *** CHANGE (delta-target fix) ***
    y_next_day / y_next_week are now DELTAS from the anchor (the real
    target_col value on window_end_date), not absolute levels:
        y_next_day[i]  = target[i+lookback]   - target[i+lookback-1]
        y_next_week[i] = target[i+lookback+6] - target[i+lookback-1]
    `anchors[i]` = target[i+lookback-1] is returned so callers can
    reconstruct the absolute prediction: anchor + predicted_delta.

    Returns (X, y_next_day_delta, y_next_week_delta, anchors, window_end_dates).
    NOTE: this return signature grew by one array (anchors) vs. the
    original version — update every call site.
    """
    df = df.dropna(subset=feature_cols + [target_col]).sort_index()
    values = df[feature_cols].to_numpy(dtype=np.float32)
    target = df[target_col].to_numpy(dtype=np.float32)
    dates = df.index.to_numpy()

    X, y_next_day, y_next_week, anchors, window_end_dates = [], [], [], [], []
    n = len(df)
    for i in range(n - lookback - 7 + 1):
        window = values[i : i + lookback]
        anchor_idx = i + lookback - 1        # last real day IN the window
        next_day_idx = i + lookback          # first day after the window
        next_week_idx = i + lookback + 6     # 7th day after the window (t+7)

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


# *** CHANGE: day_of_week/month replaced with their sin/cos pairs;
# rolling_mean_3 and 14/28-day lags added. ***
DEFAULT_FEATURE_COLUMNS = [
    "total_demand_mw", "residential_mw", "commercial_mw", "industrial_mw",
    "temperature_c", "humidity_pct", "wind_speed_kmph", "solar_irradiance", "precipitation_mm",
    "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos",
    "is_weekend", "is_holiday", "is_festival",
    "total_demand_mw_lag_1", "total_demand_mw_lag_2", "total_demand_mw_lag_3",
    "total_demand_mw_lag_7", "total_demand_mw_lag_14", "total_demand_mw_lag_28",
    "total_demand_mw_rolling_mean_3", "total_demand_mw_rolling_mean_7", "total_demand_mw_rolling_std_7",
]


if __name__ == "__main__":
    import sys

    city = sys.argv[1] if len(sys.argv) > 1 else "Delhi"
    df = load_city_dataset(city)
    df = add_lag_features(df)
    X, y_day, y_week, anchors, dates = build_supervised_windows(df, DEFAULT_FEATURE_COLUMNS)
    print(f"{city}: X={X.shape}, y_next_day(delta)={y_day.shape}, y_next_week(delta)={y_week.shape}")
    print(f"Date range of windows: {dates.min()} to {dates.max()}")
    print(f"Sample: anchor={anchors[0]:.1f} MW, next_day_delta={y_day[0]:+.1f} MW "
          f"-> absolute next_day={anchors[0] + y_day[0]:.1f} MW")