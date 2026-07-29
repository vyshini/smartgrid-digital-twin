"""
Population data and capacity apportionment, ported from
quantum-optimization/scripts/forecast_to_dispatch.py (validated via a real
8-city test run — see project history: without this apportionment, cities
were handed their entire state's generation capacity regardless of how
small their own demand share was, causing the optimizer to correctly-but-
uselessly avoid all real generation in favor of pure battery cycling).

Kept as a small, self-contained module here rather than importing across
into ml-training/ — that folder is Phase 3's offline training workspace,
not something this backend service should depend on at runtime.
"""
from app.quantum.generation_capacity import CITY_GENERATION_CAPACITY, GenerationCapacity

CITY_TO_STATE: dict[str, str] = {
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Bangalore": "Karnataka",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Kolkata": "West Bengal",
    "Ahmedabad": "Gujarat",
}

CITY_POPULATION: dict[str, int] = {
    "Delhi": 32_900_000,
    "Mumbai": 20_700_000,
    "Bangalore": 13_600_000,
    "Hyderabad": 10_500_000,
    "Chennai": 11_700_000,
    "Kolkata": 15_100_000,
    "Ahmedabad": 8_400_000,
    "Pune": 7_400_000,
}

# Census of India 2011 (last full census). Telangana's figure is the
# officially recognized bifurcated figure from undivided Andhra Pradesh's
# 2011 data.
STATE_POPULATION_CENSUS_2011: dict[str, int] = {
    "Delhi": 16_787_941,
    "Maharashtra": 112_374_333,
    "Karnataka": 61_095_297,
    "Gujarat": 60_439_692,
    "Tamil Nadu": 72_147_030,
    "West Bengal": 91_276_115,
    "Telangana": 35_003_674,
}


def city_capacity_share(city: str) -> float:
    """
    Capped at 1.0 — Delhi's raw ratio is 196% (a real data inconsistency:
    Phase 1's Delhi population figure appears to be a metro/NCR-area
    estimate including territory outside Delhi NCT, mixed against the
    state population which is the 2011 census count for NCT alone). A
    ratio above 100% would hand a city more capacity than physically
    exists, which is nonsensical regardless of the population data's
    quality — capped defensively; the underlying inconsistency is a
    separate issue worth fixing at the source, not resolved by this cap.
    """
    state = CITY_TO_STATE[city]
    ratio = CITY_POPULATION[city] / STATE_POPULATION_CENSUS_2011[state]
    return min(ratio, 1.0)


def apportioned_city_capacity(city: str) -> GenerationCapacity:
    """Scales the city's (full-state) capacity down by its population
    share, so it's consistent in scale with a population-apportioned
    demand forecast for that same city."""
    full_state_capacity = CITY_GENERATION_CAPACITY[city]
    share = city_capacity_share(city)
    return GenerationCapacity(
        coal_mw=full_state_capacity.coal_mw * share,
        hydro_mw=full_state_capacity.hydro_mw * share,
        wind_mw=full_state_capacity.wind_mw * share,
        solar_mw=full_state_capacity.solar_mw * share,
    )