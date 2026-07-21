from pydantic import BaseModel

from app.infrastructure.db.models.enums import LineStatus, NodeStatus


class CityOut(BaseModel):
    id: int
    name: str
    state: str
    latitude: float
    longitude: float
    population: int
    timezone: str

    model_config = {"from_attributes": True}


class GridNodeOut(BaseModel):
    id: int
    city_id: int
    node_code: str
    transmission_capacity_mw: float
    status: NodeStatus

    model_config = {"from_attributes": True}


class TransmissionLineOut(BaseModel):
    id: int
    from_node_id: int
    to_node_id: int
    capacity_mw: float
    current_load_mw: float
    length_km: float
    loss_pct: float
    status: LineStatus
    utilization_pct: float

    model_config = {"from_attributes": True}


class CityDetailOut(BaseModel):
    city: CityOut
    grid_nodes: list[GridNodeOut]
    transmission_lines: list[TransmissionLineOut]
