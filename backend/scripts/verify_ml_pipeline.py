"""
End-to-end smoke test for the backend/app/ml/ plugin layer.

This is deliberately NOT a pytest test (no fixtures, no assert-and-exit-1
on failure) — it's meant to be run once, by hand, after wiring up a new
piece, and read top to bottom. It exercises the full loop through the
REAL production interfaces:

    trainer.train_city()          (writes a version, promotes it)
        -> model_registry          (the version becomes "latest")
            -> LSTMForecaster.predict()   (the same class api/v1/forecast.py
                                            will eventually call)

If this script completes and prints sane-looking predictions, the ml/
plugin layer's pieces are correctly wired together — not just
individually correct in isolation (which the earlier unit tests already
covered without needing TensorFlow).

Run from repo root:
    python -m backend.scripts.verify_ml_pipeline --data-dir ml-training/data --city Delhi

Uses only 3 epochs and --force-promote by default, since this is about
confirming plumbing, not producing a good model — use trainer.py directly
with real epoch counts for that (see earlier conversation).
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from backend.app.ml import feature_engineering as fe
from backend.app.ml import trainer
from backend.app.ml.interfaces import ForecastHorizon, ForecastRequest
from backend.app.ml.lstm_model import LSTMForecaster


def make_feature_data_provider(data_dir: Path):
    """
    A minimal feature_data_provider for this smoke test — reads straight
    from ml-training/data's CSVs, same as trainer.py does. In the real
    backend this callable will instead be backed by a DB repository (see
    lstm_model.py's docstring on why LSTMForecaster doesn't import
    infrastructure/ directly) — this stand-in is intentionally simple so
    this script has no dependency on the DB/infrastructure layer being
    finished yet.
    """
    _cache: dict[str, "pd.DataFrame"] = {}

    def provider(city: str):
        if city not in _cache:
            df = fe.load_city_dataset(city, data_dir)
            df = fe.add_lag_features(df)
            _cache[city] = df
        return _cache[city]

    return provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--city", type=str, default="Delhi")
    parser.add_argument("--epochs", type=int, default=3, help="Kept tiny — this checks plumbing, not model quality.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    city = args.city

    print(f"### Step 1: train + promote a candidate for {city} (epochs={args.epochs}) ###")
    metrics = trainer.train_city(
        city, data_dir,
        epochs=args.epochs, patience=2, verbose=0,
        force_promote=True,
    )
    assert metrics["promoted"] is True, "Expected force_promote=True to promote unconditionally."
    print(f"-> trained + promoted version {metrics['version']}\n")

    print(f"### Step 2: load the promoted model through LSTMForecaster (same path api/v1/forecast.py uses) ###")
    provider = make_feature_data_provider(data_dir)
    forecaster = LSTMForecaster(feature_data_provider=provider, lookback=fe.LOOKBACK_DAYS)

    version = forecaster.model_version(city)
    assert version == metrics["version"], (
        f"Forecaster sees version {version}, trainer just promoted {metrics['version']} — "
        f"registry pointer mismatch, investigate model_registry.py."
    )
    print(f"-> LSTMForecaster.model_version('{city}') = {version} (matches what trainer just promoted)\n")

    print(f"### Step 3: request real predictions ###")
    df = provider(city)
    as_of = df.dropna(subset=fe.DEFAULT_FEATURE_COLUMNS).index.max().date()
    print(f"-> using as_of_date={as_of} (latest real, fully-featured date available for {city})")

    for horizon in (ForecastHorizon.NEXT_DAY, ForecastHorizon.NEXT_WEEK):
        result = forecaster.predict(ForecastRequest(city=city, horizon=horizon, as_of_date=as_of))
        print(
            f"   {horizon.value:10s} -> predicted={result.predicted_mw} MW "
            f"for {result.target_date} (model version {result.model_version})"
        )

    print(f"\n### ALL STEPS PASSED — train -> promote -> predict is wired correctly for {city} ###")
    print(
        "Note: this used only "
        f"{args.epochs} epochs to keep the check fast, so predicted_mw here is NOT "
        "a trustworthy forecast — re-run trainer.py directly with full epochs for a real model."
    )


if __name__ == "__main__":
    main()