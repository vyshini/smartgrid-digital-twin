"""
Real-data preparation pipeline for Phase 3 LSTM forecasting.

Data sources (full provenance, cite these — not the file-hosting site — in
your report):

- Daily state-wise electricity consumption: POSOCO daily/weekly reports,
  compiled via Kaggle (aryankhurana1701/state-wise-electricity-consumption-in-india).
  POSOCO/Grid-India is the true data origin; Kaggle is merely where it was
  accessed.
- State/UT-wise generation by source, FY2021-22: Ministry of Power via
  data.gov.in (Rajya Sabha Session 267, Unstarred Question 944). Units = MU
  (Million Units), confirmed against the Ministry of Power's own reported
  all-India total of 1,491.859 BU for FY2021-22 (powermin.gov.in).
- State populations: Census of India 2011 (the last full census — the 2021
  census was postponed and has not been conducted as of this writing).
  Telangana's figure is the officially recognized bifurcated figure derived
  from undivided Andhra Pradesh's 2011 data.
- Sector-wise consumption shares: CEA data as reported via CAG's published
  analysis for FY2022-23 (cag.org.in): Industrial 41.2%, Domestic 24.5%,
  Agriculture 16.9%, Commercial 8.1%, Others 9.3%.

Known limitations — documented here rather than silently absorbed:

1. The "Thermal" generation column in the data.gov.in source aggregates
   coal, lignite, gas, and diesel generation into a single bucket; this
   source does not allow splitting coal vs. gas separately. We map the full
   thermal share to `coal_mw` since coal is the dominant component of
   India's thermal fleet, and leave `gas_mw` at zero. This is a simplifying
   assumption, not a measurement — a more granular fuel-mix source would
   improve on this if you find one.

2. EV charging load has no real historical sector-level measurement in any
   published Indian source at this granularity. `ev_charging_mw` is set to
   zero in historical training data; EV load is only introduced later as a
   simulation-scenario input (Phase 4/6's "high EV demand" scenario), never
   presented as a historical ground-truth feature.

3. Agriculture (16.9% of national consumption) is excluded from city-level
   disaggregation since all 8 modeled cities are major urban centers where
   agricultural load is not meaningfully present. The three urban categories
   (Domestic, Commercial, Industrial — 73.8% combined) are renormalized to
   sum to 100%. This is a documented scope decision, not an oversight.

4. City-level demand is APPORTIONED from real state totals using population
   share (city population / state population), not measured directly — no
   public Indian source publishes city-level demand. A city's modeled
   demand is therefore a fraction of its state's real total, and should be
   described that way in your report, not as an independent measurement.
"""
from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Real, cited constants
# ---------------------------------------------------------------------------

# City -> state mapping (Phase 1's 8 cities).
CITY_TO_STATE: dict[str, str] = {
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Bangalore": "Karnataka",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Kolkata": "West Bengal",
    "Ahmedabad": "Gujarat",
}

# City populations, from Phase 1's seed data (docs/database-schema.sql).
CITY_POPULATION: dict[str, int] = {
    "Delhi": 32_900_000,
    "Mumbai": 20_700_000,
    "Bangalore": 13_600_000,
    "Hyderabad": 10_500_000,
    "Chennai": 11_700_000,
    "Kolkata": 15_100_000,
    "Ahmedabad": 8_400_000,
    "Pune": 7_400_000,
}

# State populations, Census of India 2011 (last full census; see docstring).
STATE_POPULATION_CENSUS_2011: dict[str, int] = {
    "Delhi": 16_787_941,
    "Maharashtra": 112_374_333,
    "Karnataka": 61_095_297,
    "Gujarat": 60_439_692,
    "Tamil Nadu": 72_147_030,
    "West Bengal": 91_276_115,
    "Telangana": 35_003_674,
}

# Sector-wise consumption shares, CEA via CAG (FY2022-23).
SECTOR_SHARE_NATIONAL: dict[str, float] = {
    "industrial": 0.412,
    "domestic": 0.245,
    "agriculture": 0.169,
    "commercial": 0.081,
    "others": 0.093,
}

# Renormalized to the three urban categories only (agriculture + others
# excluded — see module docstring, point 3). Sums to 1.0.
_URBAN_TOTAL = (
    SECTOR_SHARE_NATIONAL["industrial"]
    + SECTOR_SHARE_NATIONAL["domestic"]
    + SECTOR_SHARE_NATIONAL["commercial"]
)
SECTOR_SHARE_URBAN: dict[str, float] = {
    "industrial_mw_share": SECTOR_SHARE_NATIONAL["industrial"] / _URBAN_TOTAL,
    "residential_mw_share": SECTOR_SHARE_NATIONAL["domestic"] / _URBAN_TOTAL,
    "commercial_mw_share": SECTOR_SHARE_NATIONAL["commercial"] / _URBAN_TOTAL,
}

# Non-state columns present in the daily demand CSV that must be excluded
# from any per-state analysis (utilities/industrial consumers tracked
# separately, not geographic states).
DEMAND_CSV_NON_STATE_COLUMNS = ["Unnamed: 0", "DVC", "Essar steel"]

# Rows in the generation-mix CSV that are not real states/UTs.
GENERATION_CSV_NON_STATE_ROWS = ["Bhutan", "Grand Total"]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_daily_demand(path: str) -> pd.DataFrame:
    """
    Loads the real POSOCO-sourced daily state-wise consumption CSV.
    Returns a DataFrame indexed by date, columns = our 7 target states only.
    Call report_coverage() on the result before training — do not assume
    the date range is gap-free.
    """
    df = pd.read_csv(path)
    df = df.drop(columns=[c for c in DEMAND_CSV_NON_STATE_COLUMNS if c in df.columns])
    df["Dates"] = pd.to_datetime(df["Dates"], errors="coerce", dayfirst=False)
    df = df.dropna(subset=["Dates"]).set_index("Dates").sort_index()

    target_states = sorted(set(CITY_TO_STATE.values()))
    missing = [s for s in target_states if s not in df.columns]
    if missing:
        raise ValueError(
            f"Expected state columns not found in demand CSV: {missing}. "
            f"Available columns: {df.columns.tolist()}"
        )
    return df[target_states]


def report_coverage(df: pd.DataFrame) -> dict:
    """
    Real gap analysis — how much of the real date range is actually present.
    Inspect this before training; do not silently interpolate over large
    gaps as if they were measured data.
    """
    full_range = pd.date_range(df.index.min(), df.index.max(), freq="D")
    missing_dates = full_range.difference(df.index)
    return {
        "date_range": (str(df.index.min().date()), str(df.index.max().date())),
        "expected_days": len(full_range),
        "actual_rows": len(df),
        "missing_days": len(missing_dates),
        "coverage_pct": round(100 * len(df) / len(full_range), 2),
        "per_state_nulls": df.isna().sum().to_dict(),
    }


def load_generation_mix(path: str) -> pd.DataFrame:
    """
    Loads the real data.gov.in generation-by-source CSV (FY2021-22, MU),
    restricted to our 7 target states, and returns per-state SHARES
    (proportions, not absolute MU) of each generation source. See module
    docstring point 1 on the "Thermal" aggregation limitation.
    """
    df = pd.read_csv(path)
    df = df[~df["State/UT"].isin(GENERATION_CSV_NON_STATE_ROWS)].copy()

    numeric_cols = [c for c in df.columns if c not in ("Sl. No.", "State/UT")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.set_index("State/UT")
    target_states = sorted(set(CITY_TO_STATE.values()))
    missing = [s for s in target_states if s not in df.index]
    if missing:
        raise ValueError(f"Expected states not found in generation-mix CSV: {missing}")
    df = df.loc[target_states]

    grand_total = df["Grand Total"]
    shares = pd.DataFrame(index=df.index)
    # Thermal aggregates coal+lignite+gas+diesel in this source (see
    # docstring point 1); mapped entirely to coal_mw_share downstream.
    shares["thermal_share"] = df["Conventional Sources - Thermal"] / grand_total
    shares["hydro_share"] = df["Conventional Sources - Hydro"] / grand_total
    shares["nuclear_share"] = df["Conventional Sources - Nuclear"] / grand_total
    shares["wind_share"] = df["Renewable Sources - Wind"] / grand_total
    shares["solar_share"] = df["Renewable Sources - Solar"] / grand_total
    shares["bio_small_hydro_other_share"] = (
        df["Renewable Sources - Bio Power"]
        + df["Renewable Sources - Small Hydro"]
        + df["Renewable Sources - Others"]
    ) / grand_total
    return shares


# ---------------------------------------------------------------------------
# City apportionment + disaggregation
# ---------------------------------------------------------------------------

def apportion_to_city(state_demand: pd.Series, city: str) -> pd.Series:
    """
    Real state total -> approximate city share, via population weighting.
    NOTE: this is a fraction of the real state total, not an independent
    city measurement — see module docstring point 4.
    """
    state = CITY_TO_STATE[city]
    city_pop = CITY_POPULATION[city]
    state_pop = STATE_POPULATION_CENSUS_2011[state]
    share = city_pop / state_pop
    return (state_demand * share).rename(city)


def disaggregate_by_category(city_total_mw: pd.Series) -> pd.DataFrame:
    """
    Splits a city's total demand into residential/commercial/industrial
    using the real CEA sector shares (renormalized to exclude agriculture —
    see module docstring point 3). ev_charging_mw is real-zero historically
    — see module docstring point 2.
    """
    return pd.DataFrame({
        "residential_mw": city_total_mw * SECTOR_SHARE_URBAN["residential_mw_share"],
        "commercial_mw": city_total_mw * SECTOR_SHARE_URBAN["commercial_mw_share"],
        "industrial_mw": city_total_mw * SECTOR_SHARE_URBAN["industrial_mw_share"],
        "ev_charging_mw": 0.0,
    })


def apply_generation_mix(city_total_mw: pd.Series, state_shares: pd.Series) -> pd.DataFrame:
    """
    Applies a state's real generation-mix proportions (FY2021-22,
    data.gov.in) to a city's apportioned demand, approximating that city's
    generation-by-source breakdown. See module docstring point 1 for the
    coal/gas caveat.

    Our schema (GenerationMix entity, Phase 1) has no slot for bio-power —
    `bio_small_hydro_other_share` (up to ~7% for Karnataka, not negligible)
    is folded into `hydro_mw` as the closest existing renewable bucket,
    rather than silently dropped. This keeps the six columns summing back
    to the real city total, at the cost of `hydro_mw` slightly overstating
    true hydro for states with meaningful bio-power generation.
    """
    return pd.DataFrame({
        "coal_mw": city_total_mw * state_shares["thermal_share"],
        "gas_mw": 0.0,  # not separable from `thermal` in this source
        "hydro_mw": city_total_mw * (
            state_shares["hydro_share"] + state_shares["bio_small_hydro_other_share"]
        ),
        "nuclear_mw": city_total_mw * state_shares["nuclear_share"],
        "wind_mw": city_total_mw * state_shares["wind_share"],
        "solar_mw": city_total_mw * state_shares["solar_share"],
    })