"""Battery storage domain entity — tracks state of charge for a city."""
from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import InvalidGridStateError


@dataclass(slots=True)
class Battery:
    city_id: int
    capacity_mwh: float
    current_charge_mwh: float
    charge_rate_mw: float = 0.0
    discharge_rate_mw: float = 0.0
    health_pct: float = 100.0
    recorded_at: datetime | None = None

    def __post_init__(self):
        if self.capacity_mwh <= 0:
            raise ValueError("Battery capacity must be positive")
        if not 0.0 <= self.current_charge_mwh <= self.capacity_mwh:
            raise InvalidGridStateError(
                f"Battery charge {self.current_charge_mwh} MWh out of bounds "
                f"[0, {self.capacity_mwh}] MWh"
            )

    @property
    def soc_pct(self) -> float:
        """State of charge as a percentage."""
        return round(100 * self.current_charge_mwh / self.capacity_mwh, 2)

    def charge(self, amount_mwh: float) -> None:
        if amount_mwh < 0:
            raise ValueError("Charge amount cannot be negative")
        self.current_charge_mwh = min(self.capacity_mwh, self.current_charge_mwh + amount_mwh)

    def discharge(self, amount_mwh: float) -> None:
        if amount_mwh < 0:
            raise ValueError("Discharge amount cannot be negative")
        self.current_charge_mwh = max(0.0, self.current_charge_mwh - amount_mwh)
