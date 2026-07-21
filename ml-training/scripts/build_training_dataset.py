"""
Builds one training-ready CSV per city, combining:
  - real daily demand (Kaggle-hosted POSOCO data — validated against the
    March 2020 COVID lockdown demand drop; see project report for the
    cross-validation that excluded the GitHub twinkle0705 source)
  - population-weighted city apportionment from real state totals
  - CEA sector-share disaggregation (residential/commercial/industrial)
  - FY2021-22 generation-mix shares (data.gov.in)

Run from ml-training/scripts/:
    python build_training_dataset.py

Outputs one CSV per city to ml-training/data/processed/<city>.csv
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from data_preparation import (
    CITY_TO_STATE,
    apply_generation_mix,
    apportion_to_city,
    disaggregate_by_category,
    load_daily_demand,
    load_generation_mix,
    report_coverage,
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

DEMAND_CSV = RAW_DIR / "Indias_Electricity_Consumption_Dataset.csv"
GENERATION_CSV = RAW_DIR / "RS_Session_267_AU_944_B_ii_a.csv"


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    demand = load_daily_demand(str(DEMAND_CSV))
    coverage = report_coverage(demand)
    print("Real daily demand coverage report:")
    for k, v in coverage.items():
        print(f"  {k}: {v}")
    print()

    gen_shares = load_generation_mix(str(GENERATION_CSV))

    for city, state in CITY_TO_STATE.items():
        state_demand = demand[state]
        city_total = apportion_to_city(state_demand, city)

        categories = disaggregate_by_category(city_total)
        gen_mix = apply_generation_mix(city_total, gen_shares.loc[state])

        out = pd.concat([city_total.rename("total_demand_mw"), categories, gen_mix], axis=1)
        out.index.name = "date"

        out_path = PROCESSED_DIR / f"{city.lower()}.csv"
        out.to_csv(out_path)
        print(f"{city:12s} -> {out_path}  ({len(out)} rows, "
              f"{out['total_demand_mw'].isna().sum()} missing)")


if __name__ == "__main__":
    main()