"""
Integration tests for RunGridOptimizationUseCase's orchestration logic —
demand resolution (explicit vs. forecast), forecast persistence, and
error translation. Uses lightweight fakes for repositories/forecaster/
optimizer rather than a real DB or a real Keras model — fast, and tests
the use case's actual decision logic in isolation from infrastructure.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.application.optimization.run_grid_optimization_use_case import (
    ForecastRequiredButUnavailableError,
    RunGridOptimizationUseCase,
)
from app.domain.exceptions import CityNotFoundError, CityNotSupportedForOptimizationError
from app.ml.interfaces import ForecastHorizon, ForecastResult
from app.ml.model_registry import ModelNotFoundError
from app.ml.preprocessing import InsufficientHistoryError


class FakeCityRepository:
    def __init__(self, city=None):
        self._city = city

    async def get_by_id(self, city_id):
        return self._city


class FakeForecastRepository:
    def __init__(self):
        self.created = []
        self._next_id = 1

    async def create(self, **fields):
        record = SimpleNamespace(id=self._next_id, **fields)
        self._next_id += 1
        self.created.append(record)
        return record


class FakeOptimizationRepository:
    def __init__(self):
        self.created = []

    async def create(self, **fields):
        record = SimpleNamespace(id=len(self.created) + 1, **fields)
        self.created.append(record)
        return record


class FakeForecaster:
    """Returns a fixed prediction, or raises whatever exception was
    configured — lets tests simulate ModelNotFoundError /
    InsufficientHistoryError without needing a real trained model."""

    def __init__(self, predicted_mw=None, raise_exc=None):
        self._predicted_mw = predicted_mw
        self._raise_exc = raise_exc
        self.calls = []

    def predict(self, request):
        self.calls.append(request)
        if self._raise_exc:
            raise self._raise_exc
        return ForecastResult(
            city=request.city,
            horizon=request.horizon,
            predicted_mw=self._predicted_mw,
            as_of_date=request.as_of_date,
            target_date=request.as_of_date,
            model_version="fake-version",
        )


def _delhi_city():
    return SimpleNamespace(id=1, name="Delhi")


async def test_explicit_demand_skips_forecast_entirely():
    forecaster = FakeForecaster(predicted_mw=9999)  # would be wrong if accidentally used
    forecast_repo = FakeForecastRepository()
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
        forecaster=forecaster,
        forecast_repository=forecast_repo,
    )

    problem, forecast_id = await use_case.build_problem(
        city_id=1, target_demand_mw=270, forecast_as_of_date=None, battery_power_rating_mw=100
    )

    assert problem.target_demand_mw == 270
    assert forecast_id is None
    assert forecaster.calls == []          # forecaster never called
    assert forecast_repo.created == []     # nothing persisted


async def test_forecast_driven_demand_persists_and_returns_id():
    forecaster = FakeForecaster(predicted_mw=9789.38)
    forecast_repo = FakeForecastRepository()
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
        forecaster=forecaster,
        forecast_repository=forecast_repo,
    )

    problem, forecast_id = await use_case.build_problem(
        city_id=1, target_demand_mw=None, forecast_as_of_date=date(2024, 9, 29), battery_power_rating_mw=100
    )

    assert problem.target_demand_mw == 9789.38
    assert forecast_id == 1
    assert len(forecast_repo.created) == 1
    assert forecast_repo.created[0].predicted_mw == 9789.38
    assert forecast_repo.created[0].city_id == 1


async def test_city_not_found_raises_domain_error():
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(None),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
    )
    with pytest.raises(CityNotFoundError):
        await use_case.build_problem(
            city_id=999, target_demand_mw=270, forecast_as_of_date=None, battery_power_rating_mw=100
        )


async def test_unsupported_city_raises_domain_error():
    unsupported_city = SimpleNamespace(id=2, name="NotARealCity")
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(unsupported_city),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
    )
    with pytest.raises(CityNotSupportedForOptimizationError):
        await use_case.build_problem(
            city_id=2, target_demand_mw=270, forecast_as_of_date=None, battery_power_rating_mw=100
        )


async def test_forecast_omitted_with_no_forecaster_raises():
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
        forecaster=None,  # deliberately not injected
    )
    with pytest.raises(ForecastRequiredButUnavailableError):
        await use_case.build_problem(
            city_id=1, target_demand_mw=None, forecast_as_of_date=date(2024, 9, 29), battery_power_rating_mw=100
        )


async def test_model_not_found_translated_to_domain_error():
    forecaster = FakeForecaster(raise_exc=ModelNotFoundError("no promoted model"))
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
        forecaster=forecaster,
        forecast_repository=FakeForecastRepository(),
    )
    with pytest.raises(ForecastRequiredButUnavailableError):
        await use_case.build_problem(
            city_id=1, target_demand_mw=None, forecast_as_of_date=date(2024, 9, 29), battery_power_rating_mw=100
        )


async def test_insufficient_history_translated_to_domain_error():
    """Regression test for the real error you hit: as_of_date defaulting
    to today() against the static 2024-09-29 dataset."""
    forecaster = FakeForecaster(
        raise_exc=InsufficientHistoryError("No real data row for as_of_date=2026-07-31")
    )
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=FakeOptimizationRepository(),
        optimizer=None,
        forecaster=forecaster,
        forecast_repository=FakeForecastRepository(),
    )
    with pytest.raises(ForecastRequiredButUnavailableError, match="2024-09-29"):
        await use_case.build_problem(
            city_id=1, target_demand_mw=None, forecast_as_of_date=None, battery_power_rating_mw=100
        )


async def test_persist_result_threads_forecast_id_through():
    opt_repo = FakeOptimizationRepository()
    use_case = RunGridOptimizationUseCase(
        city_repository=FakeCityRepository(_delhi_city()),
        optimization_repository=opt_repo,
        optimizer=None,
    )
    fake_raw_result = {
        "qaoa": {
            "cobyla_iterations": 5,
            "reps": 1,
            "decoded": {
                "coal_mw": 0,
                "hydro_mw": 59,
                "wind_mw": 0,
                "solar_mw": 211,
                "import_mw": 0,
                "battery_charge_mw": 0,
                "battery_discharge_mw": 0,
                "total_supply_mw": 270,
                "target_demand_mw": 270,
                "mismatch_mw": 0,
                "battery_conflict": False,
            },
        },
        "optimization_score": 100.0,
        "objective_gap": 0.0,
        "qaoa_matches_classical_optimum": True,
    }

    record = await use_case.persist_result(
        city_id=1, raw_result=fake_raw_result, execution_time_ms=15000, forecast_id=42
    )

    assert record.forecast_id == 42
    assert record.city_id == 1
    assert opt_repo.created[0].forecast_id == 42