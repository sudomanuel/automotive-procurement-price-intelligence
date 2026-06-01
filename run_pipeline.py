"""
run_pipeline.py
===============
One-command, end-to-end run of the whole procurement price-intelligence project:

    1. data_acquisition   -> real macro data (FRED) + reference table  (data/external/)
    2. data_generation    -> synthetic supplier quotes driven by it     (data/raw/)
    3. preprocessing      -> clean analytical dataset                    (data/processed/)
    4. price_model        -> forecast unit_price, compare 3 models       (reports/)
    5. supplier_scoring   -> 0-100 scorecard + categories + actions      (reports/)
    6. visualization      -> the 10 reporting figures                    (reports/figures/)

Usage:
    python run_pipeline.py

Everything is reproducible (fixed seed + fixed analysis window).  If FRED is
unreachable, stage 1 transparently falls back to documented sample series.
"""
from __future__ import annotations

import time

from src import (data_acquisition, data_generation, preprocessing,
                 price_model, supplier_scoring, visualization)


def main() -> None:
    t0 = time.time()
    print("=" * 70)
    print("AUTOMOTIVE PROCUREMENT PRICE INTELLIGENCE - full pipeline")
    print("=" * 70)

    data_acquisition.run()
    print("-" * 70)
    data_generation.run()
    print("-" * 70)
    df = preprocessing.run()
    print("-" * 70)
    price_model.run(df)
    print("-" * 70)
    supplier_scoring.run(df)
    print("-" * 70)
    visualization.run()

    print("=" * 70)
    print(f"PIPELINE COMPLETE in {time.time() - t0:.1f}s")
    print("Key outputs:")
    print("  data/external/   real FRED indices + country reference + provenance")
    print("  data/processed/  supplier_quotes_processed.csv  (analytical dataset)")
    print("  reports/         supplier_scorecard.csv, model_comparison.csv")
    print("  reports/figures/ 10 figures (01_*.png ... 10_*.png)")
    print("=" * 70)


if __name__ == "__main__":
    main()
