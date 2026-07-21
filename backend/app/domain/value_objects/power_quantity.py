"""
Value objects for power quantities. Immutable, self-validating — a MegaWatt can
never be negative, which lets every layer above trust the invariant instead of
re-checking it.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MegaWatt:
    value: float

    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"Power quantity cannot be negative, got {self.value} MW")

    def __add__(self, other: "MegaWatt") -> "MegaWatt":
        return MegaWatt(self.value + other.value)

    def __sub__(self, other: "MegaWatt") -> "MegaWatt":
        return MegaWatt(max(0.0, self.value - other.value))

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class MegaWattHour:
    value: float

    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"Energy quantity cannot be negative, got {self.value} MWh")

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class Percentage:
    value: float

    def __post_init__(self):
        if not 0.0 <= self.value <= 100.0:
            raise ValueError(f"Percentage must be within [0, 100], got {self.value}")

    def __float__(self) -> float:
        return self.value
