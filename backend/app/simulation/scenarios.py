"""Scenario definitions — pure data, no logic. Weather scenarios only for
now; generation/infrastructure scenarios (solar failure, coal shutdown,
transmission failure) use a different mechanism (QAOA capacity override,
not LSTM re-forecast) and get their own module later."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherPerturbation:
    """Deltas applied to real weather feature columns across the LSTM's
    lookback window. Additive where a shift makes physical sense
    (temperature, wind, precipitation); multiplicative for solar
    irradiance (cloud cover scales it, doesn't just shift it)."""
    temperature_c_delta: float = 0.0
    humidity_pct_delta: float = 0.0
    wind_speed_kmph_delta: float = 0.0
    solar_irradiance_multiplier: float = 1.0
    precipitation_mm_delta: float = 0.0


@dataclass(frozen=True)
class WeatherScenario:
    key: str
    name: str
    city: str
    description: str
    perturbation: WeatherPerturbation


WEATHER_SCENARIOS: dict[str, WeatherScenario] = {
    "heatwave_delhi": WeatherScenario(
        key="heatwave_delhi",
        name="Heatwave in Delhi",
        city="Delhi",
        description=(
            "+8°C temperature spike with reduced humidity across the "
            "forecast's 14-day lookback window, consistent with a real "
            "North Indian summer heatwave event."
        ),
        perturbation=WeatherPerturbation(temperature_c_delta=8.0, humidity_pct_delta=-10.0),
    ),
}