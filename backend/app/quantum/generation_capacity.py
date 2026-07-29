"""
Real installed generation capacity per city, for the QAOA generation-dispatch
problem (Phase 4).

SOURCE: Ministry of Statistics and Programme Implementation (MoSPI),
"Energy Statistics 2023", Chapter 2 — Installed Capacity and Capacity
Utilization. Table 2.4 (Regionwise and Statewise Installed Capacity of
Electricity Generation, Utilities) and Table 2.5 (State-wise cumulative
Installed Capacity of Grid Interactive Renewable Power), both sourced from
Central Electricity Authority (CEA) / Ministry of New and Renewable Energy
(MNRE) data, figures as on 31.03.2022.
https://www.mospi.gov.in/sites/default/files/publication_reports/Energy_Statistics_2023/Chapter%202-Installed%20Capacity%20and%20Capacity%20Utilization.pdf

WHY THIS SOURCE (not Phase 3's generation-mix file): Phase 3's
data.gov.in file gives actual annual GENERATION (energy produced, MU) —
useful for historical demand disaggregation, but wrong for a dispatch
optimization, which needs installed CAPACITY (the MW ceiling a source
could provide right now). Reusing the generation file here would have
quietly conflated "how much a source was used on average" with "how much
it could provide" — a real error, not a subtle style choice.

KNOWN LIMITATIONS — documented, not hidden:
1. NUCLEAR IS EXCLUDED FROM THE DISPATCH DECISION. India's nuclear plants
   are centrally owned (NPCIL) and this source's Table 2.4 books nuclear
   capacity to "Central Sector" by region, not to the state where the
   physical plant sits — so a clean per-state nuclear MW figure isn't
   directly available here. Separately, and more importantly: Indian
   nuclear plants operate as near-constant baseload with very little
   operational flexibility in practice. Both facts point the same way —
   nuclear is modeled as a FIXED contribution outside the QAOA decision
   variables, not something the optimizer chooses to dispatch up or down.
2. Small hydro, bio-power, and waste-to-energy capacity (Table 2.5) are
   folded into `hydro_mw`, matching the convention already established in
   Phase 3's data_preparation.py, for consistency across the project.
3. Delhi and West Bengal's exact wind/solar/bio split had some ambiguity
   in the source PDF's table extraction (their state TOTALS are solid;
   only the sub-category breakdown is lower-confidence). Resolved using
   the well-established fact that neither state has meaningful wind
   resource — flagged per-value below, not silently assumed.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenerationCapacity:
    """Real installed capacity (MW) for the sources QAOA is allowed to dispatch.
    Nuclear is deliberately absent — see module docstring, limitation 1."""

    coal_mw: float
    hydro_mw: float  # includes small hydro + bio-power + waste-to-energy, see limitation 2
    wind_mw: float
    solar_mw: float

    @property
    def total_dispatchable_mw(self) -> float:
        return self.coal_mw + self.hydro_mw + self.wind_mw + self.solar_mw


# Real capacity data, MoSPI Energy Statistics 2023, as on 31.03.2022.
# Confidence note: Delhi and West Bengal's wind/solar/bio split is
# lower-confidence than the other 5 states (see module docstring, limitation 3);
# their state TOTALS are not in question, only this specific sub-breakdown.
CITY_GENERATION_CAPACITY: dict[str, GenerationCapacity] = {
    "Delhi": GenerationCapacity(coal_mw=2360, hydro_mw=59, wind_mw=0, solar_mw=211),
    "Mumbai": GenerationCapacity(coal_mw=22260, hydro_mw=6343, wind_mw=5013, solar_mw=2631),
    "Pune": GenerationCapacity(coal_mw=22260, hydro_mw=6343, wind_mw=5013, solar_mw=2631),
    "Bangalore": GenerationCapacity(coal_mw=7110, hydro_mw=6813, wind_mw=5131, solar_mw=7591),
    "Hyderabad": GenerationCapacity(coal_mw=7460, hydro_mw=2791, wind_mw=128, solar_mw=4520),
    "Chennai": GenerationCapacity(coal_mw=9030, hydro_mw=3346, wind_mw=9866, solar_mw=5067),
    "Kolkata": GenerationCapacity(coal_mw=6950, hydro_mw=1255, wind_mw=0, solar_mw=320),
    "Ahmedabad": GenerationCapacity(coal_mw=20230, hydro_mw=969, wind_mw=9209, solar_mw=7180),
}
# NOTE: Mumbai and Pune share Maharashtra's full state capacity figures here —
# this is a known simplification (both cities draw from the same state grid,
# not from independently-sized city-specific plants), consistent with how
# Phase 3 apportions state totals to cities by population share. A future
# iteration could scale these down by each city's population share of the
# state, the same way Phase 3 apportions DEMAND — left as-is for Phase 4's
# first version since the QAOA problem cares about relative source mix and
# ratios more than absolute capacity, and both cities pull from an identical
# real source mix in this dataset.