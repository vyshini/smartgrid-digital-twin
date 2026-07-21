"""LoadProfile domain entity — demand breakdown by consumer category for a city."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class LoadProfile:
    city_id: int
    residential_mw: float = 0.0
    commercial_mw: float = 0.0
    industrial_mw: float = 0.0
    ev_charging_mw: float = 0.0
    recorded_at: datetime | None = None

    def __post_init__(self):
        for field_name in ("residential_mw", "commercial_mw", "industrial_mw", "ev_charging_mw"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")

    @property
    def total_mw(self) -> float:
        return self.residential_mw + self.commercial_mw + self.industrial_mw + self.ev_charging_mw
