"""
Central configuration for the automotive-procurement-price-intelligence project.

This module is the single source of truth for:
  * filesystem paths (resolved relative to the repo root, OS-independent)
  * the analysis time window
  * external data sources (FRED series ids + URLs)
  * the country reference table (explicit, documented reference data)
  * the synthetic-data simulation coefficients (clearly separated from real data)
  * the supplier scorecard weights (configurable, as required by the brief)

Design principle of the whole project:
    Real public / reference data first, synthetic business data second.

Everything that comes from a real public source (commodity prices, energy index,
EUR/USD) or from an explicit reference table (country attributes) is defined or
loaded here so the data lineage is auditable.  Everything that is *simulated*
(supplier quotes) is driven by those real series, never the other way around.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
EXTERNAL_DIR = DATA_DIR / "external"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# External (real / reference) artefacts
COMMODITY_CSV = EXTERNAL_DIR / "commodity_index.csv"
EXCHANGE_CSV = EXTERNAL_DIR / "exchange_rate_index.csv"
ENERGY_CSV = EXTERNAL_DIR / "energy_cost_index.csv"
COUNTRY_CSV = EXTERNAL_DIR / "country_reference.csv"
ACQUISITION_META = EXTERNAL_DIR / "_acquisition_metadata.json"

# Project (synthetic) artefacts
RAW_QUOTES_CSV = RAW_DIR / "supplier_quotes.csv"
# Supplier dimension table (star-schema "dimension" to the quotes "fact" table).
# Also carries the latent generating archetype as SYNTHETIC ground truth, used to
# validate that the scorecard rediscovers the true supplier types.
SUPPLIER_MASTER_CSV = RAW_DIR / "supplier_master.csv"
PROCESSED_QUOTES_CSV = PROCESSED_DIR / "supplier_quotes_processed.csv"

# Reports
SCORECARD_CSV = REPORTS_DIR / "supplier_scorecard.csv"
MODEL_METRICS_CSV = REPORTS_DIR / "model_comparison.csv"
EXEC_SUMMARY_MD = REPORTS_DIR / "executive_summary.md"

# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
RANDOM_SEED = 42

# --------------------------------------------------------------------------- #
# Analysis window  (36 months, fully covered by the public sources)
# --------------------------------------------------------------------------- #
# A fixed historical window is used (instead of "latest N months") so the whole
# pipeline is reproducible: re-running it tomorrow yields the same dataset.
WINDOW_START = "2022-01-01"
WINDOW_END = "2024-12-01"  # inclusive month start -> 36 monthly observations
N_MONTHS = 36

# Index base period: every external index is normalised to 100 at WINDOW_START
# so that "index - 100" reads directly as a % deviation from the window start.
INDEX_BASE_DATE = WINDOW_START

# --------------------------------------------------------------------------- #
# External data sources  (FRED, no API key required for the CSV endpoint)
# --------------------------------------------------------------------------- #
FRED_CSV_ENDPOINT = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# series_id -> human friendly column name
FRED_SERIES = {
    "PALUMUSDM": "aluminum_usd_ton",       # Global price of Aluminum, US$/metric ton
    "PCOPPUSDM": "copper_usd_ton",         # Global price of Copper, US$/metric ton
    "PIORECRUSDM": "iron_ore_usd_ton",     # Global price of Iron Ore (steel proxy)
    "PNRGINDEXM": "energy_index_raw",      # Global price of Energy index (2016=100)
    "DEXUSEU": "eur_usd",                  # US$ to 1 EUR spot rate (daily)
}

# Weights for the composite raw-material index (sum to 1.0).
# Reflects a rough cost mix of an automotive bill of materials.
RAW_MATERIAL_WEIGHTS = {
    "aluminum_usd_ton": 0.45,
    "copper_usd_ton": 0.30,
    "iron_ore_usd_ton": 0.25,
}

# --------------------------------------------------------------------------- #
# Country reference table  (explicit reference data, written to
# data/external/country_reference.csv by data_acquisition.py)
# --------------------------------------------------------------------------- #
# distance_to_germany_km : approximate one-way freight distance to a central
#   German manufacturing hub (road for the EU, sea-freight equivalent overseas).
# country_risk_score     : 0-100 supply-chain / geopolitical risk PROXY (higher =
#   riskier).  Illustrative reference values, NOT a live feed -- documented as such.
COUNTRY_REFERENCE = [
    # country,          region,           supplier_region,       currency, dist_km, risk
    ("Germany",        "Europe",         "Domestic",            "EUR",      250,   10),
    ("Czech Republic", "Europe",         "EU-East",             "CZK",      350,   18),
    ("Poland",         "Europe",         "EU-East",             "PLN",      700,   22),
    ("Italy",          "Europe",         "EU-West",             "EUR",      750,   28),
    ("Spain",          "Europe",         "EU-West",             "EUR",     1600,   26),
    ("China",          "Asia",           "Asia-Pacific",        "CNY",    19000,   65),
    ("Mexico",         "North America",  "Nearshore-Americas",  "MXN",     9800,   48),
    ("USA",            "North America",  "North-America",       "USD",     7500,   30),
]
COUNTRY_REFERENCE_COLUMNS = [
    "country", "region", "supplier_region", "currency",
    "distance_to_germany_km", "country_risk_score",
]

# --------------------------------------------------------------------------- #
# Component catalogue  (SYNTHETIC simulation assumptions)
# --------------------------------------------------------------------------- #
# Per component:
#   category        : analytical grouping
#   base_price      : reference unit price (EUR) at the index base period
#   material_beta   : sensitivity of price to the raw-material index
#   energy_beta     : sensitivity of price to the energy index
#   capacity_beta   : sensitivity of price to supplier capacity utilisation
#                     (scarcity pricing -- high for Electronics, as required)
#   weight_factor   : relative shipping weight/volume (drives logistics_cost)
COMPONENTS = {
    "Battery Module":       dict(category="EV Components",       base_price=9800, material_beta=0.45, energy_beta=0.30, capacity_beta=0.10, weight_factor=1.6),
    "Electric Motor Part":  dict(category="Powertrain",          base_price=4200, material_beta=0.40, energy_beta=0.22, capacity_beta=0.12, weight_factor=1.3),
    "Aluminum Casting":     dict(category="Powertrain",          base_price=420,  material_beta=0.70, energy_beta=0.28, capacity_beta=0.08, weight_factor=1.8),
    "Brake System":         dict(category="Chassis",             base_price=560,  material_beta=0.30, energy_beta=0.12, capacity_beta=0.06, weight_factor=1.2),
    "Suspension Component": dict(category="Chassis",             base_price=380,  material_beta=0.35, energy_beta=0.12, capacity_beta=0.06, weight_factor=1.4),
    "Tire Set":             dict(category="Chassis",             base_price=620,  material_beta=0.25, energy_beta=0.18, capacity_beta=0.05, weight_factor=1.5),
    "Interior Trim":        dict(category="Interior",            base_price=240,  material_beta=0.12, energy_beta=0.10, capacity_beta=0.05, weight_factor=0.9),
    "Infotainment Unit":    dict(category="Electronics",         base_price=980,  material_beta=0.18, energy_beta=0.14, capacity_beta=0.28, weight_factor=0.6),
    "Wiring Harness":       dict(category="Electronics",         base_price=210,  material_beta=0.28, energy_beta=0.12, capacity_beta=0.26, weight_factor=0.7),
    "Cooling System":       dict(category="Thermal Management",  base_price=540,  material_beta=0.32, energy_beta=0.20, capacity_beta=0.10, weight_factor=1.1),
}

COMPONENT_CATEGORIES = [
    "EV Components", "Chassis", "Interior",
    "Electronics", "Powertrain", "Thermal Management",
]

# --------------------------------------------------------------------------- #
# Contract types  (SYNTHETIC)
# --------------------------------------------------------------------------- #
# price_mult   : average price level vs an annual contract
# volatility   : sigma of the idiosyncratic price noise (Spot most volatile)
# volume_mult  : typical order size (multi-year buys in bulk)
CONTRACT_TYPES = {
    "Spot":                dict(price_mult=1.05, volatility=0.13, volume_mult=0.6,  prob=0.30),
    "Annual Contract":     dict(price_mult=1.00, volatility=0.06, volume_mult=1.0,  prob=0.45),
    "Multi-year Contract": dict(price_mult=0.96, volatility=0.03, volume_mult=1.6,  prob=0.25),
}

# --------------------------------------------------------------------------- #
# Supplier archetypes  (SYNTHETIC)
# --------------------------------------------------------------------------- #
# Each supplier is assigned one archetype that drives its price level, quality,
# delivery reliability, risk and sustainability.  This is what creates the
# "cheap-but-risky vs expensive-but-reliable vs balanced" structure the brief
# asks for -- the patterns the scorecard then has to rediscover from the data.
SUPPLIER_ARCHETYPES = {
    "Strategic Partner":     dict(prob=0.20, price_mult=1.00, otd=0.95, defect=0.012, risk_adj=-8,  sustain=78, lead_adj=0),
    "Cost Efficient":        dict(prob=0.24, price_mult=0.89, otd=0.86, defect=0.034, risk_adj=+6,  sustain=58, lead_adj=+4),
    "Reliable but Expensive":dict(prob=0.18, price_mult=1.13, otd=0.975,defect=0.006, risk_adj=-10, sustain=80, lead_adj=-2),
    "High Risk":             dict(prob=0.14, price_mult=0.94, otd=0.78, defect=0.058, risk_adj=+18, sustain=46, lead_adj=+10),
    "Balanced":              dict(prob=0.12, price_mult=1.00, otd=0.90, defect=0.020, risk_adj=0,   sustain=66, lead_adj=+1),
    # "Underperformer": fairly priced but mediocre everywhere -> the data-driven
    # source of the "Needs Improvement" category (no compensating strength).
    "Underperformer":        dict(prob=0.12, price_mult=1.06, otd=0.86, defect=0.031, risk_adj=+5,  sustain=54, lead_adj=+3),
}

# --------------------------------------------------------------------------- #
# Pricing-model coefficients  (SYNTHETIC global drivers)
# --------------------------------------------------------------------------- #
SCALE_ELASTICITY = 0.06       # economies of scale: price ~ volume^(-elasticity)
REFERENCE_VOLUME = 1000       # pivot volume for the scale effect
FX_BETA_NON_EUR = 0.28        # FX exposure for suppliers invoicing outside EUR
FX_BETA_EUR = 0.04            # residual FX exposure for EUR-zone suppliers
LANDED_COST_BETA = 0.06       # how strongly distance/logistics lift the unit price
FREIGHT_RATE = 0.018          # EUR per km per (weighted) unit, before energy adj

# Regional sustainability priors (reference-informed, applied on top of archetype)
SUSTAINABILITY_REGION_PRIOR = {
    "Europe": 6, "North America": 2, "Asia": -6,
}

# --------------------------------------------------------------------------- #
# Dataset size
# --------------------------------------------------------------------------- #
N_SUPPLIERS = 60
TARGET_ROWS = 5200            # final row count lands in the 3k-8k band

# --------------------------------------------------------------------------- #
# Supplier scorecard  (configurable weights -- must sum to 1.0)
# --------------------------------------------------------------------------- #
SCORECARD_WEIGHTS = {
    "cost_competitiveness": 0.30,
    "delivery_reliability": 0.25,
    "quality_performance": 0.20,
    "risk_exposure": 0.15,
    "sustainability": 0.10,
}

# Final supplier-score thresholds for categorisation (0-100 scale).
SCORE_THRESHOLDS = dict(strategic=72, solid=58, weak=45)

SUPPLIER_CATEGORIES = [
    "Strategic Partner", "Cost Efficient",
    "Reliable but Expensive", "High Risk", "Needs Improvement",
]

RECOMMENDED_ACTIONS = [
    "Prioritize for long-term contract",
    "Renegotiate price",
    "Monitor quality risk",
    "Reduce dependency",
    "Keep as backup supplier",
    "Develop as strategic partner",
]


def ensure_dirs() -> None:
    """Create every output directory if it does not already exist."""
    for d in (EXTERNAL_DIR, RAW_DIR, PROCESSED_DIR, REPORTS_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)
