"""
Merges the real per-city demand data (build_training_dataset.py output),
real weather data (fetch_weather.py output), and a real Indian public
holiday calendar (the `holidays` package, IN country code) into a single
feature table, then windows it into LSTM-ready supervised sequences for
the next_day and next_week horizons (see project decision: next_hour is
NOT modeled as real ML — it's illustrative-only on the dashboard, since no
public source provides real hourly ground truth at city level).

Targets are point forecasts: next_day = total_demand_mw at t+1,
next_week = total_demand_mw at t+7 — not an average over the week.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

# A handful of major nationally-observed festivals, used to derive
# `is_festival` as a subset of `is_holiday` (the `holidays` package's India
# calendar includes these by name; we flag known festival names rather than
# treating every public holiday as a "festival" in the demand-pattern sense).
FESTIVAL_NAME_KEYWORDS = ["Diwali", "Holi", "Dussehra", "Eid", "Christmas", "Navratri", "Durga Puja"]

LOOKBACK_DAYS = 14  # how many past days of features feed the LSTM per prediction


def load_city_dataset(city: str) -> pd.DataFrame:
    """
    Merges real demand + real weather for one city. Raises clearly if either
    real file is missing — this function never fabricates a substitute.
    """
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

    df = demand.join(weather, how="inner")  # inner join: only dates with BOTH real demand and real weather
    if len(df) == 0:
        raise ValueError(f"No overlapping dates between demand and weather data for {city}.")

    df = add_calendar_features(df)
    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    import holidays  # imported here, not at module level, so the rest of this
    # module works even before `pip install holidays` has been run

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
    """
    Builds sliding windows: X[i] = feature_cols over [i, i+lookback), predicting
    next_day = target at (i+lookback) and next_week = target at (i+lookback+6).

    Returns (X, y_next_day, y_next_week, window_end_dates). Rows requiring
    data outside the real date range (start-of-series lag NaNs, end-of-series
    horizon lookahead) are dropped — never filled with fabricated values.
    """
    df = df.dropna(subset=feature_cols + [target_col]).sort_index()
    values = df[feature_cols].to_numpy(dtype=np.float32)
    target = df[target_col].to_numpy(dtype=np.float32)
    dates = df.index.to_numpy()

    X, y_next_day, y_next_week, window_end_dates = [], [], [], []
    n = len(df)
    for i in range(n - lookback - 7 + 1):
        window = values[i : i + lookback]
        next_day_idx = i + lookback  # first day after the window
        next_week_idx = i + lookback + 6  # 7th day after the window (t+7)

        # Guard against gaps: only build a window if the dates are actually
        # contiguous daily steps, not spanning one of the real missing-day gaps.
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


DEFAULT_FEATURE_COLUMNS = [
    "total_demand_mw", "residential_mw", "commercial_mw", "industrial_mw",
    "temperature_c", "humidity_pct", "wind_speed_kmph", "solar_irradiance", "precipitation_mm",
    "day_of_week", "month", "is_weekend", "is_holiday", "is_festival",
    "total_demand_mw_lag_1", "total_demand_mw_lag_2", "total_demand_mw_lag_3", "total_demand_mw_lag_7",
    "total_demand_mw_rolling_mean_7", "total_demand_mw_rolling_std_7",
]


if __name__ == "__main__":
    import sys

    city = sys.argv[1] if len(sys.argv) > 1 else "Delhi"
    df = load_city_dataset(city)
    df = add_lag_features(df)
    X, y_day, y_week, dates = build_supervised_windows(df, DEFAULT_FEATURE_COLUMNS)
    print(f"{city}: X={X.shape}, y_next_day={y_day.shape}, y_next_week={y_week.shape}")
    print(f"Date range of windows: {dates.min()} to {dates.max()}")