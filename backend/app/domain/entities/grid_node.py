"""
GridNode domain entity — a physical substation/node within a city's grid.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NodeStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass(slots=True)
class GridNode:
    id: int | None
    city_id: int
    node_code: str
    transmission_capacity_mw: float
    status: NodeStatus = NodeStatus.HEALTHY
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        if self.transmission_capacity_mw <= 0:
            raise ValueError("Transmission capacity must be positive")
        if not self.node_code.strip():
            raise ValueError("Node code cannot be empty")

    def mark_offline(self) -> None:
        self.status = NodeStatus.OFFLINE

    def restore(self) -> None:
        self.status = NodeStatus.HEALTHY
