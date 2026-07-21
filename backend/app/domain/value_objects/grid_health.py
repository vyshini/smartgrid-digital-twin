"""
Grid health classification — a pure function of load vs capacity, shared by
the dashboard, city detail view, and simulation engine so the definition of
"healthy vs critical" lives in exactly one place.
"""
from enum import StrEnum


class GridHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


def classify_grid_health(current_load_mw: float, transmission_capacity_mw: float) -> GridHealthStatus:
    """
    Utilization thresholds are intentionally conservative — Indian transmission
    corridors are typically de-rated well before nameplate capacity in practice.
    """
    if transmission_capacity_mw <= 0:
        return GridHealthStatus.OFFLINE

    utilization = current_load_mw / transmission_capacity_mw
    if utilization >= 0.95:
        return GridHealthStatus.CRITICAL
    if utilization >= 0.80:
        return GridHealthStatus.DEGRADED
    return GridHealthStatus.HEALTHY
