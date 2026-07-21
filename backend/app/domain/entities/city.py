"""
City domain entity — represents a smart grid node city (Delhi, Mumbai, ...).
Framework-free: no SQLAlchemy, no Pydantic. The infrastructure layer maps
to/from this via infrastructure/db/models and application-layer DTOs map
to/from schemas.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class City:
    id: int | None
    name: str
    state: str
    latitude: float
    longitude: float
    population: int
    timezone: str = "Asia/Kolkata"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("City name cannot be empty")
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"Invalid latitude: {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"Invalid longitude: {self.longitude}")
        if self.population < 0:
            raise ValueError("Population cannot be negative")
