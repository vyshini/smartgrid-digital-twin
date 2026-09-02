"""
Promotes GBT artifacts from the offline training workspace into the path
the running backend actually reads from.

WHY THIS EXISTS: gbt_full.py (ml-training/scripts/) trains and saves to
    ml-training/models_gbt/<city>/{next_day,next_week}_model.joblib
    ml-training/models_gbt/<city>/feature_columns.joblib

but backend/app/ml/gbt_model.py's GBTForecaster reads from
    backend/app/ml/artifacts_gbt/<city>/{next_day,next_week}_model.joblib
    backend/app/ml/artifacts_gbt/<city>/feature_columns.joblib

These paths never matched. Without this script, GBTForecaster raises
ModelNotFoundError for every city routed to "gbt" in model_routing.json --
currently Delhi, Ahmedabad, Mumbai, Pune, Bangalore (5 of 8 cities, per
at least one horizon) -- on every single request, unconditionally.

This mirrors model_registry.promote()'s discipline for LSTM: training and
serving are different concerns, and a fresh training run should not
silently become "live" just because it finished. Since GBT has no
versioning yet (see GBTForecaster.model_version()'s "gbt-unversioned"
honesty note), this script's promotion gate is simple existence +
sanity-loadability of the joblib files, not a metrics comparison like
trainer.py's _should_promote() -- a real gap, not hidden: if you want
"don't promote a regression" behavior for GBT like the LSTM has, that
needs comparing against gbt_summary.csv the same way trainer.py compares
against metrics.json. Flagged as a followup, not silently skipped.

Run from ml-training/scripts/ (after gbt_full.py has produced artifacts):
    python promote_gbt.py                  # promote all cities present
    python promote_gbt.py --city Delhi      # promote a single city
    python promote_gbt.py --dry-run         # show what would be copied, do nothing
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import joblib

SOURCE_DIR = Path(__file__).parent.parent / "models_gbt"
DEST_DIR = Path(__file__).parent.parent.parent / "backend" / "app" / "ml" / "artifacts_gbt"

REQUIRED_FILES = ["next_day_model.joblib", "next_week_model.joblib", "feature_columns.joblib"]


def _sanity_load(path: Path) -> None:
    """Actually unpickles the file, not just checks it exists -- catches a
    truncated/corrupt copy or a LightGBM version mismatch NOW, at promotion
    time, rather than the first time a real API request hits it."""
    joblib.load(path)


def promote_city(city: str, dry_run: bool = False) -> dict:
    src_dir = SOURCE_DIR / city.lower()
    dest_dir = DEST_DIR / city.lower()

    missing = [f for f in REQUIRED_FILES if not (src_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"{city}: missing {missing} in {src_dir}. Run gbt_full.py --city {city} first."
        )

    for fname in REQUIRED_FILES:
        _sanity_load(src_dir / fname)  # raises loudly if unpicklable

    if dry_run:
        return {"city": city, "action": "would copy", "src": str(src_dir), "dest": str(dest_dir)}

    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in REQUIRED_FILES:
        shutil.copy2(src_dir / fname, dest_dir / fname)

    return {"city": city, "action": "promoted", "dest": str(dest_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--city", type=str, default=None, help="Promote a single city. Default: all cities found in models_gbt/.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without copying anything.")
    args = parser.parse_args()

    if not SOURCE_DIR.exists():
        print(f"ERROR: {SOURCE_DIR} does not exist. Run gbt_full.py first (from ml-training/scripts/).")
        sys.exit(1)

    if args.city:
        cities = [args.city]
    else:
        cities = sorted(p.name for p in SOURCE_DIR.iterdir() if p.is_dir())

    if not cities:
        print(f"No trained GBT artifacts found in {SOURCE_DIR}.")
        sys.exit(1)

    failures = []
    for city in cities:
        try:
            result = promote_city(city, dry_run=args.dry_run)
            print(f"  {result['city']:12s} -> {result['action']} ({result.get('dest', result.get('src'))})")
        except Exception as e:  # noqa: BLE001 -- one city's failure shouldn't abort the batch
            print(f"  [FAILED] {city}: {e}")
            failures.append(city)

    if failures:
        print(f"\n{len(failures)} cit{'y' if len(failures) == 1 else 'ies'} failed to promote: {failures}")
        sys.exit(1)

    print(f"\nDone. {DEST_DIR} now matches what GBTForecaster will serve.")


if __name__ == "__main__":
    main()