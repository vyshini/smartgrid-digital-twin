"""GenerationMix domain entity — power generation by source, for a city, at a point in time."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class GenerationMix:
    city_id: int
    solar_mw: float = 0.0
    wind_mw: float = 0.0
    hydro_mw: float = 0.0
    coal_mw: float = 0.0
    gas_mw: float = 0.0
    nuclear_mw: float = 0.0
    recorded_at: datetime | None = None

    def __post_init__(self):
        for field_name in ("solar_mw", "wind_mw", "hydro_mw", "coal_mw", "gas_mw", "nuclear_mw"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def total_mw(self) -> float:
        return (
            self.solar_mw + self.wind_mw + self.hydro_mw
            + self.coal_mw + self.gas_mw + self.nuclear_mw
        )

    @property
    def renewable_mw(self) -> float:
        return self.solar_mw + self.wind_mw + self.hydro_mw

    @property
    def renewable_pct(self) -> float:
        return 0.0 if self.total_mw == 0 else round(100 * self.renewable_mw / self.total_mw, 2)
