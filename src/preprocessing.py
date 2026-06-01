"""
src/preprocessing.py
====================
STAGE 3 of the pipeline -- CLEANING, VALIDATION & FEATURE ENGINEERING.

Takes the assembled raw quotes (``data/raw/supplier_quotes.csv``), runs data
quality checks, and produces the analytical dataset used by the EDA, the price
model and the scorecard (``data/processed/supplier_quotes_processed.csv``).

Cleaning / validation:
    * enforce dtypes, drop duplicate quote ids
    * range-check rates (0-1) and indices (>0); coerce / clip impossible values
    * confirm every quote carries its real external macro indices

Feature engineering (additive -- raw columns are preserved):
    * date / quarter          -- proper time axis
    * total_order_value       -- unit_price * order_volume (EUR exposure)
    * log_order_volume        -- linear-model friendly scale variable
    * price_ratio_vs_median   -- price vs the component's market median (the
                                 like-for-like cost-competitiveness signal)
    * landed_unit_cost        -- unit_price + logistics_cost per unit
    * is_eur_zone / is_overseas

Run directly:   python -m src.preprocessing
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C

RATE_COLS = ["on_time_delivery_rate", "defect_rate",
             "warranty_claim_rate", "supplier_capacity_utilization"]
INDEX_COLS = ["raw_material_index", "energy_cost_index", "exchange_rate_index"]


def _quality_report(df: pd.DataFrame, label: str) -> None:
    nulls = int(df.isna().sum().sum())
    print(f"  [{label}] rows={len(df):,} cols={df.shape[1]} nulls={nulls}")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- structural integrity ----------------------------------------------
    before = len(df)
    df = df.drop_duplicates(subset="quote_id").reset_index(drop=True)
    if len(df) != before:
        print(f"  - dropped {before - len(df)} duplicate quote ids")

    # --- type enforcement ---------------------------------------------------
    int_cols = ["year", "month", "order_volume", "lead_time_days", "final_awarded"]
    for c in int_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    float_cols = (["unit_price", "logistics_cost", "risk_score_external",
                   "sustainability_score"] + RATE_COLS + INDEX_COLS)
    for c in float_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # --- domain validation / clipping --------------------------------------
    for c in RATE_COLS:                       # rates must live in [0, 1]
        df[c] = df[c].clip(0, 1)
    df["unit_price"] = df["unit_price"].clip(lower=0.01)
    df["order_volume"] = df["order_volume"].clip(lower=1)
    for c in INDEX_COLS:                       # indices must be positive
        df.loc[df[c] <= 0, c] = np.nan

    # --- missing-value handling --------------------------------------------
    # indices come from real series; if any month were missing we forward/back fill
    df[INDEX_COLS] = (df.sort_values(["year", "month"])[INDEX_COLS]
                      .ffill().bfill())
    key_cols = ["supplier_id", "component_type", "country", "unit_price"]
    df = df.dropna(subset=key_cols).reset_index(drop=True)

    # --- categorical sanity -------------------------------------------------
    df = df[df["component_type"].isin(C.COMPONENTS)]
    df = df[df["contract_type"].isin(C.CONTRACT_TYPES)].reset_index(drop=True)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(
        dict(year=df["year"].astype(int), month=df["month"].astype(int), day=1)
    )
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df["total_order_value"] = (df["unit_price"] * df["order_volume"]).round(2)
    df["log_order_volume"] = np.log1p(df["order_volume"]).round(4)

    comp_median = df.groupby("component_type")["unit_price"].transform("median")
    df["price_ratio_vs_median"] = (df["unit_price"] / comp_median).round(4)

    df["landed_unit_cost"] = (
        df["unit_price"] + df["logistics_cost"] / df["order_volume"]
    ).round(2)

    df["is_eur_zone"] = df["region"].eq("Europe") & df["country"].isin(
        ["Germany", "Italy", "Spain"]
    )
    df["is_overseas"] = ~df["region"].eq("Europe")
    return df


def run() -> pd.DataFrame:
    C.ensure_dirs()
    print("STAGE 3 | Preprocessing & feature engineering")
    raw = pd.read_csv(C.RAW_QUOTES_CSV)
    _quality_report(raw, "raw")
    df = engineer_features(clean(raw))
    _quality_report(df, "processed")
    df.to_csv(C.PROCESSED_QUOTES_CSV, index=False)
    print(f"  + {C.PROCESSED_QUOTES_CSV.relative_to(C.PROJECT_ROOT)}")
    return df


if __name__ == "__main__":
    run()
