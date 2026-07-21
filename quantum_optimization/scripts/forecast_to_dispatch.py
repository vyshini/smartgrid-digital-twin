"""
Bridges Phase 3 (real trained LSTM forecasts) to Phase 4 (QAOA dispatch
optimization): loads a city's saved model + scalers, produces a real
next-day/next-week demand forecast from the most recent real feature
window, and packages it into a DispatchProblem for QAOA to optimize
against.

NOTE ON SANDBOX EXECUTION: requires TensorFlow and the actual trained
model artifacts (ml-training/models/<city>/), neither of which exist in
the sandbox this was authored in. The model-loading and inference path
(load_model_artifacts, forecast_next_day_mw) is UNTESTED end-to-end.

What IS tested here (pure numpy/pandas, no TensorFlow needed):
get_latest_feature_window()'s window/anchor extraction logic, and
_find_file()'s fallback behavior — see the bottom of this file's
companion test output for details.

CRITICAL: predictions from saved models may be either SCALED DELTAS
(post-residual-fix — Phase 3 found the model underperforming a trivial
persistence baseline when trained on raw levels, and fixed it by training
on the CHANGE from today's real value instead) or already-complete
ABSOLUTE LEVELS (pre-fix models). This file DETECTS which convention is
in play (via which scaler filename actually matched — see
DELTA_SCALER_NAMES) rather than assuming, after a real diagnostic caught
a bug here: a "next-day" forecast that was 106% above today's real value,
traced to a pre-fix (absolute-level) model having its already-complete
prediction incorrectly added to the anchor a second time.

IMPORTANT FOLLOW-UP THIS RAISES: if your model.keras is a pre-fix
(absolute-level) model, it was never confirmed to beat the persistence
baseline — that was the entire reason the residual-target fix existed in
the first place (see train_lstm.py's module docstring). A "reasonable-
looking" forecast from this bridge script does NOT mean the underlying
model is good, only that this script's own double-counting bug is fixed.
Check your training_summary.csv's `beats_persistence` columns (if you
have one from a post-fix training run) before trusting this model's
accuracy — if you don't have one, or it shows the model losing to
persistence, retraining with the current (delta-based) train_lstm.py is
the real fix, not just this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np

ML_TRAINING_SCRIPTS = Path(__file__).parent.parent.parent / "ml-training" / "scripts"
sys.path.insert(0, str(ML_TRAINING_SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

from data_preparation import (  # noqa: E402
    CITY_POPULATION,
    CITY_TO_STATE,
    STATE_POPULATION_CENSUS_2011,
)
from feature_engineering import LOOKBACK_DAYS, add_lag_features, load_city_dataset  # noqa: E402
from generation_capacity import CITY_GENERATION_CAPACITY, GenerationCapacity  # noqa: E402
from hamiltonian_builder import DispatchProblem  # noqa: E402

MODELS_DIR = Path(__file__).parent.parent.parent / "ml-training" / "models"

# Candidate filenames, tried in order. This project's train_lstm.py went
# through a residual/delta-target fix mid-Phase-3 (see its module
# docstring) — different training runs may have used slightly different
# scaler names before/after that fix, so this tries the current
# (post-fix) name first, falling back to the pre-fix name rather than
# hard-failing on a naming assumption I can't verify from this sandbox.
FEATURE_SCALER_CANDIDATES = ["feature_scaler.joblib"]
DAY_SCALER_CANDIDATES = ["next_day_delta_target_scaler.joblib", "next_day_target_scaler.joblib"]
WEEK_SCALER_CANDIDATES = ["next_week_delta_target_scaler.joblib", "next_week_target_scaler.joblib"]
FEATURE_COLUMNS_CANDIDATES = ["feature_columns.joblib"]

# Which of the above candidate names indicate a genuine DELTA scaler
# (post-residual-fix) vs. the pre-fix RAW LEVEL scaler. This distinction is
# not cosmetic: adding the anchor back to an already-complete raw-level
# prediction silently ~doubles the forecast. This was caught via a real
# diagnostic — a "next-day" forecast that jumped 106% above today's real
# value, traced to day_scaler.mean_ being ~167 (a plausible average RAW
# DEMAND LEVEL, not a plausible average day-to-day CHANGE, which would
# imply demand growing by 167 MW every single day).
DELTA_SCALER_NAMES = {"next_day_delta_target_scaler.joblib", "next_week_delta_target_scaler.joblib"}


def _find_file(city_dir: Path, candidates: list[str]) -> Path:
    """Tries each candidate filename in order; fails with a clear, actionable
    message (listing what's actually in the directory) rather than a bare
    FileNotFoundError on a single guessed name."""
    for name in candidates:
        path = city_dir / name
        if path.exists():
            return path
    actual_files = sorted(p.name for p in city_dir.glob("*")) if city_dir.exists() else []
    raise FileNotFoundError(
        f"None of {candidates} found in {city_dir}.\n"
        f"Files actually present: {actual_files}\n"
        f"Update the *_CANDIDATES lists at the top of forecast_to_dispatch.py "
        f"to match your actual filenames if none of these match."
    )


def load_model_artifacts(city: str) -> dict:
    """UNTESTED in this sandbox — requires TensorFlow (not installed here)
    and real trained model files (don't exist in this sandbox)."""
    from tensorflow import keras  # imported here so the rest of this module
    # (get_latest_feature_window, _find_file) stays importable/testable
    # without TensorFlow installed — same pattern as feature_engineering.py's
    # lazy `import holidays`.

    city_dir = MODELS_DIR / city.lower()
    if not city_dir.exists():
        raise FileNotFoundError(
            f"No trained model directory for {city} at {city_dir}. "
            f"Run train_lstm.py --city {city} first (see ml-training/scripts/)."
        )

    day_scaler_path = _find_file(city_dir, DAY_SCALER_CANDIDATES)
    week_scaler_path = _find_file(city_dir, WEEK_SCALER_CANDIDATES)
    targets_are_deltas = day_scaler_path.name in DELTA_SCALER_NAMES

    print(
        f"[{city}] using scaler '{day_scaler_path.name}' -> "
        f"interpreting model output as {'DELTA (change from anchor)' if targets_are_deltas else 'ABSOLUTE LEVEL (pre-residual-fix model)'}"
    )

    return {
        "model": keras.models.load_model(city_dir / "model.keras"),
        "feature_scaler": joblib.load(_find_file(city_dir, FEATURE_SCALER_CANDIDATES)),
        "day_scaler": joblib.load(day_scaler_path),
        "week_scaler": joblib.load(week_scaler_path),
        "feature_columns": joblib.load(_find_file(city_dir, FEATURE_COLUMNS_CANDIDATES)),
        "targets_are_deltas": targets_are_deltas,
    }


def get_latest_feature_window(
    city: str, feature_columns: list[str], lookback: int = LOOKBACK_DAYS
) -> tuple[np.ndarray, float, "pd.Timestamp"]:  # noqa: F821
    """
    TESTED (see test output) — pure pandas/numpy, no TensorFlow needed.
    Returns (window, anchor, window_end_date) using the most recent real
    `lookback` days for `city`, reusing Phase 3's real data pipeline
    (load_city_dataset + add_lag_features) rather than a separate copy of it.
    """
    df = load_city_dataset(city)
    df = add_lag_features(df)
    df = df.dropna(subset=feature_columns + ["total_demand_mw"]).sort_index()

    if len(df) < lookback:
        raise ValueError(
            f"{city}: only {len(df)} real rows available after dropping NaNs — "
            f"need at least {lookback} for a full lookback window."
        )

    window_df = df.iloc[-lookback:]
    window = window_df[feature_columns].to_numpy(dtype=np.float32)
    anchor = float(window_df["total_demand_mw"].iloc[-1])  # today's real value
    window_end_date = window_df.index[-1]
    return window, anchor, window_end_date


def forecast_next_day_mw(city: str) -> dict:
    """
    UNTESTED end-to-end (needs TensorFlow + real model files). Produces a
    real forecast using the actual trained model + the most recent real
    feature window. Returns absolute MW levels (already anchor-corrected),
    not the raw deltas the model internally predicts.
    """
    artifacts = load_model_artifacts(city)
    window, anchor, window_end_date = get_latest_feature_window(city, artifacts["feature_columns"])

    n_features = window.shape[1]
    X = window.reshape(1, len(window), n_features)
    X_scaled = (
        artifacts["feature_scaler"]
        .transform(X.reshape(-1, n_features))
        .reshape(X.shape)
        .astype(np.float32)
    )

    preds = artifacts["model"].predict(X_scaled, verbose=0)

    day_value = artifacts["day_scaler"].inverse_transform(preds["next_day"].reshape(-1, 1)).ravel()[0]
    week_value = artifacts["week_scaler"].inverse_transform(preds["next_week"].reshape(-1, 1)).ravel()[0]

    if artifacts["targets_are_deltas"]:
        # Post-residual-fix model: descaled value is a CHANGE from today —
        # add the anchor back to reconstruct the absolute MW level.
        next_day_mw = anchor + day_value
        next_week_mw = anchor + week_value
    else:
        # Pre-fix model: descaled value IS ALREADY the absolute level.
        # Adding the anchor here would double-count it — this is exactly
        # the bug a real diagnostic caught (a "next-day" forecast 106%
        # above today's real value, traced to this).
        next_day_mw = day_value
        next_week_mw = week_value

    return {
        "city": city,
        "window_end_date": str(window_end_date.date()),
        "anchor_mw": round(anchor, 2),
        "targets_were_deltas": artifacts["targets_are_deltas"],
        "next_day_mw": round(float(next_day_mw), 2),
        "next_week_mw": round(float(next_week_mw), 2),
    }


def city_capacity_share(city: str) -> float:
    """
    The same population ratio Phase 3 uses to apportion DEMAND from a
    state total down to a city (see data_preparation.py's
    apportion_to_city) — applied here to CAPACITY instead, so a city's
    dispatch problem uses a slice of its state's generation fleet
    consistent in scale with its own apportioned demand, not the entire
    state's capacity regardless of how small the city's demand share is.

    Without this, a city apportioned ~20% of its state's demand would
    still be handed 100% of the state's generation capacity — meaning
    every single generation block vastly overshoots the tiny target
    demand, and the optimizer (correctly, given that flawed setup) avoids
    using any real generation at all, relying purely on the battery's
    finer discretization. That's not a QAOA or classical-solver bug; it's
    a scale mismatch between Phase 3's city-level demand and Phase 4's
    state-level capacity, caught via exactly this symptom across a real
    8-city run.

    CAPPED AT 1.0: Delhi's population ratio is 196% (a real data
    inconsistency — Phase 1's Delhi population figure appears to be a
    metro/NCR-area estimate that includes territory outside Delhi NCT,
    while the state population is the 2011 census count for NCT alone).
    A ratio above 100% would hand a city MORE capacity than physically
    exists, which is nonsensical regardless of population data quality —
    so it's capped here as a defensive minimum. The underlying Phase 1
    population data inconsistency for Delhi is a separate issue worth
    fixing at the source, not something this cap resolves.
    """
    state = CITY_TO_STATE[city]
    ratio = CITY_POPULATION[city] / STATE_POPULATION_CENSUS_2011[state]
    return min(ratio, 1.0)


def apportioned_city_capacity(city: str) -> GenerationCapacity:
    """Scales the city's (currently full-state) capacity down by its
    population share — see city_capacity_share() for why this matters."""
    full_state_capacity = CITY_GENERATION_CAPACITY[city]
    share = city_capacity_share(city)
    return GenerationCapacity(
        coal_mw=full_state_capacity.coal_mw * share,
        hydro_mw=full_state_capacity.hydro_mw * share,
        wind_mw=full_state_capacity.wind_mw * share,
        solar_mw=full_state_capacity.solar_mw * share,
    )


def build_dispatch_problem_from_forecast(
    city: str,
    horizon: str = "next_day",
    battery_power_rating_mw: float = 200.0,
    battery_conflict_penalty_weight: float | None = None,
) -> tuple[DispatchProblem, dict]:
    """The actual Task 1 bridge: real forecast -> DispatchProblem ready for QAOA.
    Capacity is apportioned to city-scale (see apportioned_city_capacity) so
    it's consistent with the already city-scale forecasted demand.

    `battery_conflict_penalty_weight` overrides DispatchProblem's default
    (3.0) if given — exposed here after a real 8-city test showed QAOA
    repeatedly converging to solutions with a partial battery charge/
    discharge conflict (exactly explained by the default penalty weight:
    2 conflicting bit-pairs x 3.0 = the observed gap of 6.0 in 3 of 4
    mismatched cities). Testing a higher weight is a concrete next step to
    try before assuming this needs a QAOA hyperparameter fix instead."""
    if horizon not in ("next_day", "next_week"):
        raise ValueError("horizon must be 'next_day' or 'next_week'")

    forecast = forecast_next_day_mw(city)
    target_mw = forecast[f"{horizon}_mw"]

    capacity = apportioned_city_capacity(city)
    kwargs = {}
    if battery_conflict_penalty_weight is not None:
        kwargs["battery_conflict_penalty_weight"] = battery_conflict_penalty_weight

    problem = DispatchProblem(
        capacity=capacity,
        target_demand_mw=target_mw,
        battery_power_rating_mw=battery_power_rating_mw,
        **kwargs,
    )
    return problem, forecast


if __name__ == "__main__":
    from qaoa_optimizer import run_qaoa

    city = sys.argv[1] if len(sys.argv) > 1 else "Delhi"
    horizon = sys.argv[2] if len(sys.argv) > 2 else "next_day"

    problem, forecast = build_dispatch_problem_from_forecast(city, horizon=horizon)
    print(f"Real forecast for {city}: {forecast}")
    print(f"Dispatching against target_demand_mw={problem.target_demand_mw} ({horizon})")

    result = run_qaoa(problem, reps=2, shots=1024, maxiter=100)
    print("QAOA decoded dispatch:", result["qaoa"]["decoded"])
    print("Classical baseline decoded dispatch:", result["classical_baseline"]["decoded"])
    print("Optimization score:", result["optimization_score"])
    print("QAOA matched classical optimum?", result["qaoa_matches_classical_optimum"])