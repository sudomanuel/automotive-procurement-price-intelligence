"""
src/supplier_scoring.py
=======================
STAGE 5 of the pipeline -- SUPPLIER SCORECARD.

Aggregates the quote-level data to one row per supplier and computes a 0-100
``final_supplier_score`` from five weighted, configurable dimensions:

    cost_competitiveness  30%   (price vs the component's market median)
    delivery_reliability  25%   (on-time delivery rate)
    quality_performance   20%   (defect & warranty claim rates)
    risk_exposure         15%   (external supply-chain risk)
    sustainability        10%   (sustainability score)

Each dimension is min-max normalised across the supplier pool (relative
benchmarking, the way category managers actually compare vendors), with the
direction handled per metric (lower price / defects / risk = better).

Cost competitiveness deliberately uses ``price_ratio_vs_median`` (each quote
relative to its own component's market median) -- NOT the raw average price -- so
a battery supplier is not punished for selling intrinsically expensive parts.

Every supplier is then mapped to a category and a concrete recommended action.

Output: reports/supplier_scorecard.csv

Run directly:   python -m src.supplier_scoring
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C


def _min_max(s: pd.Series, higher_better: bool = True) -> pd.Series:
    lo, hi = s.min(), s.max()
    if np.isclose(hi, lo):
        return pd.Series(50.0, index=s.index)
    scaled = (s - lo) / (hi - lo) * 100.0
    return scaled if higher_better else 100.0 - scaled


def aggregate_suppliers(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["supplier_id", "supplier_name", "country"], as_index=False)
    agg = g.agg(
        component_categories_served=("component_category",
                                     lambda s: "; ".join(sorted(s.unique()))),
        avg_unit_price=("unit_price", "mean"),
        avg_price_ratio=("price_ratio_vs_median", "mean"),
        avg_lead_time_days=("lead_time_days", "mean"),
        avg_on_time_delivery_rate=("on_time_delivery_rate", "mean"),
        avg_defect_rate=("defect_rate", "mean"),
        avg_warranty_claim_rate=("warranty_claim_rate", "mean"),
        avg_risk_score_external=("risk_score_external", "mean"),
        avg_sustainability_score=("sustainability_score", "mean"),
        n_quotes=("quote_id", "count"),
        awarded_rate=("final_awarded", "mean"),
        total_spend=("total_order_value", "sum"),
    )
    return agg


def score_suppliers(df: pd.DataFrame,
                    weights: dict | None = None) -> pd.DataFrame:
    weights = weights or C.SCORECARD_WEIGHTS
    if not np.isclose(sum(weights.values()), 1.0):
        raise ValueError(f"Scorecard weights must sum to 1.0, got {sum(weights.values())}")

    s = aggregate_suppliers(df)

    # ---- five 0-100 dimension scores (direction-aware) ---------------------
    quality_raw = s["avg_defect_rate"] + 0.5 * s["avg_warranty_claim_rate"]
    s["cost_competitiveness_score"] = _min_max(s["avg_price_ratio"], higher_better=False)
    s["delivery_reliability_score"] = _min_max(s["avg_on_time_delivery_rate"], higher_better=True)
    s["quality_performance_score"] = _min_max(quality_raw, higher_better=False)
    s["risk_exposure_score"] = _min_max(s["avg_risk_score_external"], higher_better=False)
    s["sustainability_score_norm"] = _min_max(s["avg_sustainability_score"], higher_better=True)

    s["final_supplier_score"] = (
        weights["cost_competitiveness"] * s["cost_competitiveness_score"]
        + weights["delivery_reliability"] * s["delivery_reliability_score"]
        + weights["quality_performance"] * s["quality_performance_score"]
        + weights["risk_exposure"] * s["risk_exposure_score"]
        + weights["sustainability"] * s["sustainability_score_norm"]
    ).round(1)

    s["supplier_category"] = s.apply(_categorize, axis=1)
    s["recommended_action"] = s.apply(_recommend, axis=1)

    # rounding for presentation
    for c in ["avg_unit_price", "total_spend"]:
        s[c] = s[c].round(0)
    for c in ["avg_lead_time_days", "avg_risk_score_external",
              "avg_sustainability_score", "cost_competitiveness_score",
              "delivery_reliability_score", "quality_performance_score",
              "risk_exposure_score", "sustainability_score_norm"]:
        s[c] = s[c].round(1)
    for c in ["avg_on_time_delivery_rate", "avg_defect_rate",
              "avg_warranty_claim_rate", "avg_price_ratio", "awarded_rate"]:
        s[c] = s[c].round(4)

    return s.sort_values("final_supplier_score", ascending=False).reset_index(drop=True)


def _categorize(r: pd.Series) -> str:
    """Map a supplier to one of five categories from its dimension profile.

    Order matters: the most decisive signals (risk, premium quality) are tested
    first.  Thresholds are on the 0-100 relative (min-max) scale.
    """
    cost = r["cost_competitiveness_score"]
    delv = r["delivery_reliability_score"]
    qual = r["quality_performance_score"]
    rsk = r["risk_exposure_score"]
    final = r["final_supplier_score"]
    T = C.SCORE_THRESHOLDS
    premium_ops = delv >= 62 and qual >= 62      # excellent delivery AND quality

    # 1. High Risk: risky profile that is NOT shielded by operational excellence,
    #    or a genuinely poor-quality-and-risky supplier.
    if (rsk < 40 and not premium_ops) or (qual < 38 and rsk < 58):
        return "High Risk"
    # 2. Strategic Partner: top-tier overall AND balanced across every pillar
    if final >= T["strategic"] and min(cost, delv, qual, rsk) >= 50:
        return "Strategic Partner"
    # 3. Reliable but Expensive: premium delivery & quality, weak on price
    if premium_ops and cost < 55:
        return "Reliable but Expensive"
    # 4. Cost Efficient: clearly cheap with acceptable (not premium) reliability
    if cost >= 58 and rsk >= 45:
        return "Cost Efficient"
    # 5. residual mid / low performers
    return "Needs Improvement"


def _recommend(r: pd.Series) -> str:
    cat = r["supplier_category"]
    qual = r["quality_performance_score"]
    rsk = r["risk_exposure_score"]
    if cat == "Strategic Partner":
        return "Prioritize for long-term contract"
    if cat == "Reliable but Expensive":
        # premium supplier -- renegotiate price, but cut dependency if also risky
        return "Reduce dependency" if rsk < 45 else "Renegotiate price"
    if cat == "Cost Efficient":
        return "Develop as strategic partner" if qual >= 50 else "Monitor quality risk"
    if cat == "High Risk":
        return "Reduce dependency"
    # Needs Improvement
    return "Monitor quality risk" if qual < 50 else "Keep as backup supplier"


# Final, ordered column set for the CSV (required columns first, then sub-scores)
OUTPUT_COLUMNS = [
    "supplier_id", "supplier_name", "country", "component_categories_served",
    "avg_unit_price", "avg_lead_time_days", "avg_on_time_delivery_rate",
    "avg_defect_rate", "avg_warranty_claim_rate", "avg_risk_score_external",
    "avg_sustainability_score", "final_supplier_score", "supplier_category",
    "recommended_action",
    # transparency / drivers
    "cost_competitiveness_score", "delivery_reliability_score",
    "quality_performance_score", "risk_exposure_score",
    "sustainability_score_norm", "avg_price_ratio", "n_quotes",
    "awarded_rate", "total_spend",
]


def run(df: pd.DataFrame | None = None,
        weights: dict | None = None) -> pd.DataFrame:
    C.ensure_dirs()
    print("STAGE 5 | Supplier scorecard")
    if df is None:
        df = pd.read_csv(C.PROCESSED_QUOTES_CSV)
    sc = score_suppliers(df, weights)
    sc[OUTPUT_COLUMNS].to_csv(C.SCORECARD_CSV, index=False)
    print(f"  + {C.SCORECARD_CSV.relative_to(C.PROJECT_ROOT)}  "
          f"({len(sc)} suppliers)")
    dist = sc["supplier_category"].value_counts()
    print("  category distribution: "
          + ", ".join(f"{k}={v}" for k, v in dist.items()))
    return sc


if __name__ == "__main__":
    run()
