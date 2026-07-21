import pytest

from app.domain.entities.battery import Battery
from app.domain.entities.city import City
from app.domain.entities.generation_mix import GenerationMix
from app.domain.entities.transmission_line import TransmissionLine
from app.domain.exceptions import InvalidGridStateError
from app.domain.value_objects.grid_health import GridHealthStatus, classify_grid_health


def test_city_rejects_invalid_latitude():
    with pytest.raises(ValueError):
        City(id=None, name="Nowhere", state="X", latitude=200.0, longitude=0.0, population=1000)


def test_city_valid_construction():
    city = City(id=1, name="Delhi", state="Delhi", latitude=28.6139, longitude=77.2090, population=32900000)
    assert city.name == "Delhi"


def test_battery_soc_calculation():
    battery = Battery(city_id=1, capacity_mwh=500, current_charge_mwh=250)
    assert battery.soc_pct == 50.0


def test_battery_rejects_overcharge_construction():
    with pytest.raises(InvalidGridStateError):
        Battery(city_id=1, capacity_mwh=500, current_charge_mwh=600)


def test_battery_charge_clamps_at_capacity():
    battery = Battery(city_id=1, capacity_mwh=500, current_charge_mwh=490)
    battery.charge(50)
    assert battery.current_charge_mwh == 500


def test_battery_discharge_clamps_at_zero():
    battery = Battery(city_id=1, capacity_mwh=500, current_charge_mwh=10)
    battery.discharge(50)
    assert battery.current_charge_mwh == 0


def test_generation_mix_renewable_pct():
    mix = GenerationMix(city_id=1, solar_mw=100, wind_mw=50, hydro_mw=50, coal_mw=800)
    assert mix.total_mw == 1000
    assert mix.renewable_pct == 20.0


def test_transmission_line_rejects_self_loop():
    with pytest.raises(ValueError):
        TransmissionLine(
            id=None, from_node_id=1, to_node_id=1, capacity_mw=100, current_load_mw=10, length_km=5
        )


def test_transmission_line_overload_detection():
    line = TransmissionLine(
        id=None, from_node_id=1, to_node_id=2, capacity_mw=100, current_load_mw=120, length_km=5
    )
    assert line.is_overloaded
    assert line.utilization_pct == 120.0


@pytest.mark.parametrize(
    "load,capacity,expected",
    [
        (500, 1000, GridHealthStatus.HEALTHY),
        (850, 1000, GridHealthStatus.DEGRADED),
        (960, 1000, GridHealthStatus.CRITICAL),
        (100, 0, GridHealthStatus.OFFLINE),
    ],
)
def test_classify_grid_health(load, capacity, expected):
    assert classify_grid_health(load, capacity) == expected
