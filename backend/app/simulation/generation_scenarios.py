"""
Generation/infrastructure scenarios — mechanically distinct from weather
scenarios (see scenarios.py's module docstring): these override
DispatchProblem.capacity directly and re-run QAOA, rather than perturbing
LSTM input features. A city's generation capacity isn't a trained model
input, so there's no honest way to make the LSTM "know" about a plant
outage — this is squarely an optimization-layer concern, not a
forecasting one.
"""
from dataclasses import dataclass, replace

from app.quantum.generation_capacity import GenerationCapacity


@dataclass(frozen=True)
class CapacityPerturbation:
    """Multipliers applied to each source's capacity. 0.0 = fully offline,
    1.0 = unaffected, >1.0 = increased capacity (e.g. a positive-case
    scenario like added wind generation)."""
    coal_multiplier: float = 1.0
    hydro_multiplier: float = 1.0
    wind_multiplier: float = 1.0
    solar_multiplier: float = 1.0

    def apply(self, capacity: GenerationCapacity) -> GenerationCapacity:
        return replace(
            capacity,
            coal_mw=capacity.coal_mw * self.coal_multiplier,
            hydro_mw=capacity.hydro_mw * self.hydro_multiplier,
            wind_mw=capacity.wind_mw * self.wind_multiplier,
            solar_mw=capacity.solar_mw * self.solar_multiplier,
        )


@dataclass(frozen=True)
class GenerationScenario:
    key: str
    name: str
    city: str
    description: str
    perturbation: CapacityPerturbation


GENERATION_SCENARIOS: dict[str, GenerationScenario] = {
    "solar_failure_delhi": GenerationScenario(
        key="solar_failure_delhi",
        name="Solar Generation Failure",
        city="Delhi",
        description=(
            "All solar generation capacity taken offline (e.g. major "
            "inverter fault or grid-tie failure across solar assets). "
            "Tests whether QAOA compensates via coal, import, or battery."
        ),
        perturbation=CapacityPerturbation(solar_multiplier=0.0),
    ),
    "coal_shutdown_delhi": GenerationScenario(
        key="coal_shutdown_delhi",
        name="Coal Plant Shutdown",
        city="Delhi",
        description=(
            "All coal generation capacity taken offline (e.g. planned "
            "maintenance or emergency shutdown). Tests reliance on "
            "renewables, import, and battery when the single largest "
            "dispatchable source is unavailable."
        ),
        perturbation=CapacityPerturbation(coal_multiplier=0.0),
    ),
    "wind_increase_delhi": GenerationScenario(
        key="wind_increase_delhi",
        name="Wind Generation Increase",
        city="Delhi",
        description="Wind capacity increased 50% (e.g. new turbine capacity coming online).",
        perturbation=CapacityPerturbation(wind_multiplier=1.5),
    ),
}