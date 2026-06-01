# Data Documentation & Lineage

This project follows one rule: **real public / reference data first, synthetic business data second.** This file documents exactly which data is real, which is simulated, why, and how to reproduce it.

---

## 1. Folder layout

```
data/
├── external/    # REAL public data (FRED) + curated REFERENCE table
│   ├── commodity_index.csv
│   ├── energy_cost_index.csv
│   ├── exchange_rate_index.csv
│   ├── country_reference.csv
│   └── _acquisition_metadata.json   # provenance: source, URLs, rows, timestamp
├── raw/         # SYNTHETIC business data, calibrated to the external data
│   ├── supplier_quotes.csv          # fact table (one row = one quote)
│   └── supplier_master.csv          # supplier dimension table (+ latent archetype)
└── processed/
    └── supplier_quotes_processed.csv  # cleaned + feature-engineered analytical set
```

---

## 2. External data — REAL public sources

All series are downloaded from **FRED (Federal Reserve Economic Data, St. Louis Fed)** via its public CSV endpoint `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>`, which **requires no API key**. Each is rebased to **100 at the base period (Jan-2022)** so deviations read as % change vs the window start.

| File | FRED series | Description | Used for |
|------|-------------|-------------|----------|
| `commodity_index.csv` | `PALUMUSDM`, `PCOPPUSDM`, `PIORECRUSDM` | Aluminum, copper, iron-ore (steel proxy) prices, USD/ton | `raw_material_index` = 0.45·Al + 0.30·Cu + 0.25·Fe |
| `energy_cost_index.csv` | `PNRGINDEXM` | Global price of Energy index (2016=100) | `energy_cost_index` |
| `exchange_rate_index.csv` | `DEXUSEU` | US$ per 1 EUR spot rate (daily → monthly mean) | `exchange_rate_index` |

**Provenance** is written to `data/external/_acquisition_metadata.json` on every run (source = `FRED live` or `fallback`, URLs, row counts, UTC timestamp, analysis window).

### Fallback (offline reproducibility)
If FRED is unreachable, `src/data_acquisition.py` generates a small, deterministic, realistic sample series for each index and labels it `source = fallback` in both the CSV (`source` column) and the metadata JSON. **This is not hidden** — it is recorded explicitly so a reader always knows whether a run used live or fallback data.

---

## 3. Country reference table — curated REFERENCE data

`country_reference.csv` is a **manually curated, documented** reference table (not a live feed):

| Column | Meaning | Notes |
|--------|---------|-------|
| `country`, `region`, `supplier_region` | sourcing geography | — |
| `currency` | invoicing currency | drives FX exposure (non-EUR = exposed) |
| `distance_to_germany_km` | approximate one-way freight distance to a central German hub | road for the EU, sea-freight equivalent overseas |
| `country_risk_score` | 0–100 supply-chain / geopolitical risk **proxy** | illustrative reference values, **not** a live index |

---

## 4. Project data — SYNTHETIC (and why)

Real supplier quotations, defect rates, lead times and risk scores are **commercially confidential** and never published. They are therefore **simulated** in `src/data_generation.py`. The simulation is *calibrated by the real external data*: every quote inherits the genuine macro indices for its month, and `unit_price` is an explicit function of them.

### Which columns are real vs simulated

| Column | Origin |
|--------|--------|
| `raw_material_index`, `energy_cost_index`, `exchange_rate_index` | **REAL** (FRED, merged by month) |
| `country`, `region` | **REFERENCE** (country table) |
| `risk_score_external` | **HYBRID** — country risk (reference) + simulated supplier/lead-time variation |
| `quote_id`, `supplier_id`, `supplier_name`, `component_type`, `component_category`, `order_volume`, `unit_price`, `lead_time_days`, `on_time_delivery_rate`, `defect_rate`, `warranty_claim_rate`, `supplier_capacity_utilization`, `logistics_cost`, `contract_type`, `sustainability_score`, `final_awarded` | **SYNTHETIC** |

### How the external indices affect `unit_price`
`unit_price` is built multiplicatively (see README §5). In words:
- **raw-material index ↑ → price ↑**, strongest for material-intensive parts (Aluminum Casting `material_beta = 0.70`).
- **energy index ↑ → price ↑** (and `logistics_cost ↑`).
- **EUR/USD index ↓ (weaker euro) → price ↑** for non-EUR suppliers invoicing in USD (China, USA, Mexico).
- **order volume ↑ → price ↓** (economies of scale); **distance ↑ → price ↑** (landed cost).
- **Spot** contracts are most volatile, **Multi-year** least.

### Key simulation assumptions
- 60 suppliers, each specialising in 1–4 components, assigned a hidden **archetype** that sets its price level, quality, delivery, risk and sustainability.
- Battery Module & Electric Motor Part are the most expensive components; Electronics prices are sensitive to capacity utilization (scarcity pricing).
- High lead time and high capacity utilization increase risk; high defect rates and low on-time delivery reduce the supplier score.
- The latent archetype is stored in `supplier_master.csv` as **synthetic ground truth** purely to validate the scorecard — it would not exist in a real dataset and is never used as a model feature.

---

## 5. Limitations

- **Synthetic prices are model-generated**, so the price model's R² is optimistic; on real quotes expect lower accuracy. Treat the model as a demonstration of method, not a calibrated real-world predictor.
- The **country risk score is an illustrative proxy**, not sourced from a governance/risk index.
- `raw_material_index` weights (45/30/25) are a reasonable but illustrative bill-of-materials mix, not a measured cost breakdown.
- FX exposure is modelled via a single EUR/USD series rather than per-currency rates.
- Real procurement data would include negotiation history, tooling/NRE costs, multi-tier supply chains and contractual minimums not modelled here.

---

## 6. How to re-run the extraction

```bash
# just the acquisition stage (re-downloads FRED, rewrites data/external/)
python -m src.data_acquisition

# or the full pipeline (acquisition → generation → processing → model → scorecard → figures)
python run_pipeline.py
```

The analysis window and all coefficients are configurable in [`src/config.py`](../src/config.py) (`WINDOW_START`, `WINDOW_END`, `FRED_SERIES`, `RAW_MATERIAL_WEIGHTS`, `RANDOM_SEED`). A fixed seed and fixed window make every run reproducible.
