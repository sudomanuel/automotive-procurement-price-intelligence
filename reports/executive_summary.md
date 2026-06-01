# Executive Summary — Automotive Procurement Price Intelligence

*Business case inspired by real industry challenges in a premium automotive manufacturer. No real company data is used.*

## The problem
A strategic purchasing team must decide, across 60 component suppliers, **who to prioritize, renegotiate, monitor or replace**. Two questions drive that decision: *what should a component cost given today's markets?* and *which suppliers offer the best balance of price, delivery, quality, risk and sustainability?*

## What we did
- **Extracted real market data** from FRED (St. Louis Fed): aluminum, copper and iron-ore (steel proxy) prices, a global energy index, and the EUR/USD rate — 36 monthly observations (2022–2024), rebased to 100 at Jan-2022, with full provenance and an offline fallback.
- **Generated ~4,500 synthetic supplier quotes** (confidential in real life) **calibrated to that real data**: each quote's `unit_price` is an explicit function of the real commodity, energy and FX indices, plus order volume, logistics, contract type and a hidden supplier "archetype".
- **Forecast unit price** with three models and **scored every supplier** on a transparent, configurable 0–100 scorecard.

## What explains price
Component type sets the **price tier** (Battery Module ≈ €10.5k vs Wiring Harness ≈ €203). *Within* a tier, price is driven by **commodity markets** (Aluminum Casting vs raw-material index, r = 0.51), **energy and logistics cost**, **order volume** (economies of scale) and **contract type** (Spot quotes are the most volatile). Gradient Boosting predicts price at **R² = 0.98, MAPE 11%** — clearly beating a linear baseline (MAPE 40%) because the drivers act multiplicatively.

## Which suppliers are strategic vs risky
- **Strategic Partners (10):** balanced excellence (avg score 81). The top quotes come from EU suppliers in the Czech Republic, Spain and Germany.
- **Reliable but Expensive (16):** premium quality and delivery but the **highest spend share (33%)** — the prime renegotiation target.
- **Cost Efficient (17):** cheap with acceptable risk — develop the better ones.
- **High Risk (11):** the five lowest-scoring suppliers are **all China-based**, and the high-risk group concentrates **€648M ≈ 15% of total spend** — a clear dependency-reduction priority.
- **Needs Improvement (6):** mediocre across the board; keep as backup or monitor.

## Recommended decisions
| Action | Suppliers | Why |
|--------|:--------:|-----|
| Prioritize for long-term contract | 10 | Best balanced performers |
| Renegotiate price | 13 | Premium suppliers holding the largest spend share |
| Develop as strategic partner | 12 | Cheap with room to improve reliability |
| Reduce dependency | 14 | Risk concentrated in a few high-spend, high-risk vendors |
| Monitor quality risk | 6 | Early quality warning signs |
| Keep as backup supplier | 5 | Useful surge capacity, not core |

**Bottom line:** lock in the 10 strategic partners, attack the 33% of spend sitting with premium suppliers through renegotiation, and de-risk the ~15% of spend concentrated in China-based high-risk vendors.

*Full method, data lineage and limitations: see [`README.md`](../README.md) and [`data/README_data.md`](../data/README_data.md). Figures in [`reports/figures/`](figures/).*
