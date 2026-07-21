"""TransmissionLine domain entity connecting two grid nodes."""
from dataclasses import dataclass
from enum import StrEnum


class LineStatus(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


@dataclass(slots=True)
class TransmissionLine:
    id: int | None
    from_node_id: int
    to_node_id: int
    capacity_mw: float
    current_load_mw: float
    length_km: float
    loss_pct: float = 0.0
    status: LineStatus = LineStatus.ACTIVE

    def __post_init__(self):
        if self.from_node_id == self.to_node_id:
            raise ValueError("A transmission line cannot connect a node to itself")
        if self.capacity_mw <= 0:
            raise ValueError("Transmission line capacity must be positive")
        if not 0.0 <= self.loss_pct <= 100.0:
            raise ValueError("Loss percentage must be within [0, 100]")

    @property
    def utilization_pct(self) -> float:
        return 0.0 if self.capacity_mw == 0 else round(100 * self.current_load_mw / self.capacity_mw, 2)

    @property
    def is_overloaded(self) -> bool:
        return self.current_load_mw > self.capacity_mw
