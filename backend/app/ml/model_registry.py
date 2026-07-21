"""
Versioned artifact storage for trained models.

Why this exists instead of trainer.py writing straight to a fixed path:
the spec explicitly requires "Model Versioning," and re-running training
for a city (new data, a bugfix, a hyperparameter change) must not silently
clobber the model currently being served — a bad retrain should be
recoverable by rolling back a pointer, not by hoping you still have the
old .keras file lying around.

Layout on disk:

    artifacts/
      <city>/
        <version>/                  e.g. "20260718-153000"
          model.keras
          feature_scaler.joblib
          next_day_target_scaler.joblib
          next_week_target_scaler.joblib
          feature_columns.joblib
          metrics.json
        latest.json                 -> {"version": "<version>"}

`latest.json` is the promotion pointer. train_lstm.py / trainer.py write a
new version directory and then call `promote()` only after the new
model's held-out test metrics look acceptable — training a candidate does
NOT automatically make it live.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


class ModelNotFoundError(Exception):
    """Raised when no promoted (or explicitly requested) version exists
    for a city. Caught at the use-case layer and mapped to a domain
    exception — see core/exceptions.py's domain exception -> HTTP mapping."""


@dataclass(frozen=True)
class ModelArtifactPaths:
    """Absolute paths to one version's saved files. `trainer.py` writes to
    these; `lstm_model.py`'s Forecaster implementation reads from these."""
    version_dir: Path
    model_path: Path
    feature_scaler_path: Path
    next_day_scaler_path: Path
    next_week_scaler_path: Path
    feature_columns_path: Path
    metrics_path: Path


def new_version_id() -> str:
    """UTC timestamp version id — sortable, unambiguous, no coordination
    needed between training runs (unlike an incrementing integer, which
    would require reading the registry first to avoid collisions)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _city_dir(city: str) -> Path:
    return ARTIFACTS_DIR / city.lower()


def paths_for(city: str, version: str) -> ModelArtifactPaths:
    version_dir = _city_dir(city) / version
    return ModelArtifactPaths(
        version_dir=version_dir,
        model_path=version_dir / "model.keras",
        feature_scaler_path=version_dir / "feature_scaler.joblib",
        next_day_scaler_path=version_dir / "next_day_target_scaler.joblib",
        next_week_scaler_path=version_dir / "next_week_target_scaler.joblib",
        feature_columns_path=version_dir / "feature_columns.joblib",
        metrics_path=version_dir / "metrics.json",
    )


def begin_version(city: str, version: str | None = None) -> ModelArtifactPaths:
    """Creates the directory for a new candidate version and returns the
    paths trainer.py should save into. Does NOT touch latest.json — the
    candidate is not live until promote() is called."""
    version = version or new_version_id()
    paths = paths_for(city, version)
    paths.version_dir.mkdir(parents=True, exist_ok=False)
    return paths


def promote(city: str, version: str) -> None:
    """Makes `version` the one served by load_latest(). Verifies the
    version's files actually exist first — refuses to promote a partial
    or missing artifact set, since that would only surface as a confusing
    failure at prediction time instead of here at promotion time."""
    paths = paths_for(city, version)
    required = [
        paths.model_path,
        paths.feature_scaler_path,
        paths.next_day_scaler_path,
        paths.next_week_scaler_path,
        paths.feature_columns_path,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise ModelNotFoundError(
            f"Cannot promote {city} version {version}: missing artifact file(s) {missing}"
        )

    city_dir = _city_dir(city)
    city_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = city_dir / "latest.json"
    pointer_path.write_text(json.dumps({"version": version, "promoted_at": datetime.now(timezone.utc).isoformat()}))


def current_version(city: str) -> str:
    pointer_path = _city_dir(city) / "latest.json"
    if not pointer_path.exists():
        raise ModelNotFoundError(
            f"No promoted model for '{city}'. Train and promote a version first "
            f"(see trainer.py / ml-training/scripts/train_lstm.py)."
        )
    return json.loads(pointer_path.read_text())["version"]


def latest_paths(city: str) -> ModelArtifactPaths:
    """What lstm_model.py's Forecaster.predict() actually loads from."""
    return paths_for(city, current_version(city))


def list_versions(city: str) -> list[str]:
    city_dir = _city_dir(city)
    if not city_dir.exists():
        return []
    return sorted(p.name for p in city_dir.iterdir() if p.is_dir())


def rollback(city: str, version: str) -> None:
    """Points `latest` back at an already-existing, already-validated
    older version. Thin wrapper over promote() with a clearer name at the
    call site (e.g. an ops runbook / admin endpoint), and it re-validates
    the artifact files exist rather than trusting the version string blindly."""
    if version not in list_versions(city):
        raise ModelNotFoundError(
            f"Cannot roll back {city} to version '{version}': not found. "
            f"Available versions: {list_versions(city)}"
        )
    promote(city, version)


def delete_version(city: str, version: str) -> None:
    """Deletes a version's files from disk. Refuses to delete the
    currently-promoted version — rollback or promote a replacement first —
    since deleting the live model out from under a running Forecaster
    would break predictions with no warning."""
    try:
        if current_version(city) == version:
            raise ModelNotFoundError(
                f"Refusing to delete '{city}' version {version}: it is currently promoted. "
                f"Promote a different version first."
            )
    except ModelNotFoundError as e:
        if "currently promoted" in str(e):
            raise
        # else: no promoted version at all, so nothing is "live" — deletion is safe

    version_dir = paths_for(city, version).version_dir
    if version_dir.exists():
        shutil.rmtree(version_dir)