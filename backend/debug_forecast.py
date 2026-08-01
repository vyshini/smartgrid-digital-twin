from datetime import date
from app.api.deps_forecast import get_forecast_use_case
from app.application.forecasting.forecast_city_load_use_case import ForecastCityLoadInput
from app.ml.interfaces import ForecastHorizon

use_case = get_forecast_use_case()
result = use_case.execute(
    ForecastCityLoadInput(
        city="Delhi",
        horizon=ForecastHorizon.NEXT_DAY,
        as_of_date=date(2024, 9, 29),
    )
)
print(result)