"""
Calls the exact same code path api/v1/forecast.py's predict_city_load()
uses, but as a plain script — so if something breaks, Python prints the
full, real traceback to this terminal instead of it being caught and
reformatted by core/exceptions.py's register_exception_handlers.

Run from backend/ (same place you run uvicorn from):
    python debug_forecast.py
"""
from app.api.deps_forecast import get_forecast_use_case
from app.application.forecasting.forecast_city_load_use_case import ForecastCityLoadInput
from app.ml.interfaces import ForecastHorizon

use_case = get_forecast_use_case()
result = use_case.execute(
    ForecastCityLoadInput(city="Delhi", horizon=ForecastHorizon.NEXT_DAY)
)
print(result)