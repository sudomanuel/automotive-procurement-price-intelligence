"""
src/data_generation.py
======================
STAGE 2 of the pipeline -- SYNTHETIC SUPPLIER QUOTES.

Real supplier quotations are confidential, so this stage SIMULATES them -- but
the simulation is *calibrated by the real external data* acquired in stage 1.
Every quote inherits the genuine raw-material, energy and EUR/USD index for its
month, and the unit price is an explicit function of those real series:

    unit_price = base_price[component]
               * material_factor(raw_material_index)      <- real FRED commodities
               * energy_factor(energy_cost_index)          <- real FRED energy index
               * capacity_factor(capacity_utilization)     <- scarcity pricing
               * fx_factor(exchange_rate_index)            <- real FRED EUR/USD
               * scale_factor(order_volume)                <- economies of scale
               * landed_factor(distance_to_germany)        <- logistics premium
               * contract_factor(contract_type)            <- contract pricing
               * archetype_factor(supplier)                <- supplier competitiveness
               * (1 + volatility noise)                    <- Spot > Annual > Multi-year

Supplier behaviour (quality, delivery, risk, sustainability) is driven by hidden
"archetypes" (Strategic / Cost Efficient / Reliable-but-Expensive / High-Risk /
Balanced) so that the downstream scorecard has a real structure to rediscover.

Run directly:   python -m src.data_generation
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C


# --------------------------------------------------------------------------- #
# Local simulation detail constants
# --------------------------------------------------------------------------- #
ACTIVITY_PROB = 0.86       # P(a served supplier-component is quoted in a month)

# How many component types a supplier specialises in (weights for 1..4).
N_COMPONENTS_WEIGHTS = [0.15, 0.40, 0.30, 0.15]

# Sourcing mix for a central-European premium OEM (EU heavy, some LCC sourcing).
COUNTRY_WEIGHTS = {
    "Germany": 0.22, "Czech Republic": 0.12, "Poland": 0.11, "Italy": 0.12,
    "Spain": 0.09, "China": 0.16, "Mexico": 0.08, "USA": 0.10,
}

# Typical order size per component (expensive parts ship in smaller lots).
BASE_VOLUME = {
    "Battery Module": 250, "Electric Motor Part": 350, "Aluminum Casting": 1800,
    "Brake System": 1200, "Suspension Component": 1500, "Tire Set": 900,
    "Interior Trim": 2500, "Infotainment Unit": 600, "Wiring Harness": 3000,
    "Cooling System": 1000,
}

# Contract-type mix conditioned on archetype (reliable suppliers -> longer terms).
CONTRACT_DIST_BY_ARCH = {
    "Strategic Partner":      [0.15, 0.45, 0.40],
    "Reliable but Expensive": [0.15, 0.50, 0.35],
    "Balanced":               [0.28, 0.47, 0.25],
    "Cost Efficient":         [0.40, 0.42, 0.18],
    "High Risk":              [0.50, 0.38, 0.12],
    "Underperformer":         [0.38, 0.44, 0.18],
}
DEFAULT_CONTRACT_DIST = [0.30, 0.45, 0.25]   # fallback for any new archetype
CONTRACT_ORDER = ["Spot", "Annual Contract", "Multi-year Contract"]

# Supplier-name building blocks (synthetic, vendor-neutral).
NAME_STEMS = [
    "Rhein", "Vortex", "Apex", "Helios", "Bavaria", "Lumina", "NordTec", "Kraft",
    "Volta", "Stellar", "Pioneer", "Mercura", "Castor", "Tindal", "Orion",
    "Zenith", "Falcon", "Meridian", "Caldera", "Hanseatic", "Vulcan", "Atlas",
    "Cobalt", "Drava", "Estala", "Fenix", "Granta", "Halden", "Ibex", "Juno",
    "Kepler", "Larix", "Magna", "Novaron", "Onyx", "Pallas", "Quanta", "Razon",
    "Solaris", "Tramont", "Umbra", "Verde", "Westmark", "Xenon", "Ydra", "Zelos",
]
NAME_DOMAINS = ["Components", "Systems", "Automotive", "Industries", "Tech",
                "Mobility", "Castings", "Electronics", "Drivetrain", "Precision"]
LEGAL_SUFFIX = {
    "Germany": "GmbH", "Italy": "S.p.A.", "Spain": "S.A.",
    "Poland": "Sp. z o.o.", "Czech Republic": "s.r.o.", "China": "Co., Ltd.",
    "USA": "Inc.", "Mexico": "S.A. de C.V.",
}


# --------------------------------------------------------------------------- #
# Supplier master
# --------------------------------------------------------------------------- #
def _build_suppliers(rng: np.random.Generator) -> pd.DataFrame:
    countries = list(COUNTRY_WEIGHTS)
    cweights = np.array(list(COUNTRY_WEIGHTS.values()))
    cweights = cweights / cweights.sum()

    arch_names = list(C.SUPPLIER_ARCHETYPES)
    aweights = np.array([C.SUPPLIER_ARCHETYPES[a]["prob"] for a in arch_names])
    aweights = aweights / aweights.sum()

    comp_names = list(C.COMPONENTS)
    stems = rng.permutation(NAME_STEMS).tolist()
    used_names: set[str] = set()
    rows = []
    for i in range(C.N_SUPPLIERS):
        country = rng.choice(countries, p=cweights)
        archetype = rng.choice(arch_names, p=aweights)
        n_comp = rng.choice([1, 2, 3, 4], p=N_COMPONENTS_WEIGHTS)
        served = sorted(rng.choice(comp_names, size=n_comp, replace=False).tolist())

        stem = stems[i % len(stems)]
        domain = rng.choice(NAME_DOMAINS)
        name = f"{stem} {domain} {LEGAL_SUFFIX[country]}"
        while name in used_names:                       # guarantee uniqueness
            name = f"{stem} {rng.choice(NAME_DOMAINS)} {LEGAL_SUFFIX[country]}"
        used_names.add(name)

        rows.append(dict(
            supplier_id=f"SUP-{i + 1:03d}",
            supplier_name=name,
            country=country,
            archetype=archetype,
            served_components=served,
            base_capacity=float(rng.uniform(0.68, 0.90)),
            price_offset=float(rng.normal(0, 0.04)),     # idiosyncratic price level
            quality_offset=float(rng.normal(0, 1.0)),    # +ve = better quality/OTD
        ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Macro frame
# --------------------------------------------------------------------------- #
def _load_macro() -> pd.DataFrame:
    com = pd.read_csv(C.COMMODITY_CSV)[["year", "month", "raw_material_index"]]
    ene = pd.read_csv(C.ENERGY_CSV)[["year", "month", "energy_cost_index"]]
    fx = pd.read_csv(C.EXCHANGE_CSV)[["year", "month", "exchange_rate_index"]]
    macro = com.merge(ene, on=["year", "month"]).merge(fx, on=["year", "month"])
    return macro


# --------------------------------------------------------------------------- #
# Main generation
# --------------------------------------------------------------------------- #
def generate(seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(C.RANDOM_SEED if seed is None else seed)

    country_ref = pd.read_csv(C.COUNTRY_CSV)
    suppliers = _build_suppliers(rng)
    macro = _load_macro()

    # ---- persist the supplier dimension table (with latent archetype) ------
    master = suppliers.merge(
        country_ref[["country", "region", "supplier_region"]],
        on="country", how="left",
    )
    master["n_components_served"] = master["served_components"].apply(len)
    master["components_served"] = master["served_components"].apply("; ".join)
    master[[
        "supplier_id", "supplier_name", "country", "region", "supplier_region",
        "archetype", "n_components_served", "components_served",
    ]].to_csv(C.SUPPLIER_MASTER_CSV, index=False)

    # ---- supplier x served-component x month grid --------------------------
    sc = suppliers.explode("served_components").rename(
        columns={"served_components": "component_type"}
    )
    grid = sc.merge(macro, how="cross")
    keep = rng.random(len(grid)) < ACTIVITY_PROB
    grid = grid.loc[keep].reset_index(drop=True)
    n = len(grid)

    # ---- attach reference / catalogue attributes ---------------------------
    comp_attr = pd.DataFrame(C.COMPONENTS).T.reset_index(names="component_type")
    for col in ("base_price", "material_beta", "energy_beta",
                "capacity_beta", "weight_factor"):
        comp_attr[col] = comp_attr[col].astype(float)
    grid = grid.merge(comp_attr, on="component_type", how="left")
    grid = grid.merge(country_ref, on="country", how="left")

    arch_attr = pd.DataFrame(C.SUPPLIER_ARCHETYPES).T.reset_index(names="archetype")
    grid = grid.merge(arch_attr, on="archetype", how="left",
                      suffixes=("", "_arch"))

    # ---- contract type (archetype-conditioned) -----------------------------
    contract = np.empty(n, dtype=object)
    u = rng.random(n)
    for arch in pd.unique(grid["archetype"]):
        dist = CONTRACT_DIST_BY_ARCH.get(arch, DEFAULT_CONTRACT_DIST)
        m = grid["archetype"].values == arch
        idx = np.searchsorted(np.cumsum(dist), u[m])
        contract[m] = np.array(CONTRACT_ORDER)[np.clip(idx, 0, 2)]
    grid["contract_type"] = contract
    cmap = C.CONTRACT_TYPES
    grid["c_price_mult"] = grid["contract_type"].map(lambda x: cmap[x]["price_mult"])
    grid["c_vol_mult"] = grid["contract_type"].map(lambda x: cmap[x]["volume_mult"])
    grid["c_volatility"] = grid["contract_type"].map(lambda x: cmap[x]["volatility"])

    # ---- order volume (economies-of-scale driver) --------------------------
    base_vol = grid["component_type"].map(BASE_VOLUME).astype(float).values
    grid["order_volume"] = np.maximum(
        10,
        (base_vol * grid["c_vol_mult"].values
         * rng.lognormal(0.0, 0.45, n)).round()
    ).astype(int)

    # ---- capacity utilisation (seasonal + supplier base) -------------------
    seasonal = 0.04 * np.sin(2 * np.pi * grid["month"].values / 12.0)
    cap = grid["base_capacity"].values + seasonal + rng.normal(0, 0.04, n)
    grid["supplier_capacity_utilization"] = np.clip(cap, 0.55, 0.99).round(3)

    # ---- normalised real macro drivers -------------------------------------
    rm = grid["raw_material_index"].values / 100.0
    en = grid["energy_cost_index"].values / 100.0
    fx_idx = grid["exchange_rate_index"].values
    fx_pressure = 100.0 / fx_idx               # >1 when EUR weak -> imports costlier

    # ---- pricing factors ---------------------------------------------------
    material_factor = 1 + grid["material_beta"].values * (rm - 1)
    energy_factor = 1 + grid["energy_beta"].values * (en - 1)
    capacity_factor = 1 + grid["capacity_beta"].values * (
        (grid["supplier_capacity_utilization"].values - 0.80) / 0.20
    )
    is_eur = (grid["currency"].values == "EUR")
    fx_beta = np.where(is_eur, C.FX_BETA_EUR, C.FX_BETA_NON_EUR)
    fx_factor = 1 + fx_beta * (fx_pressure - 1)
    scale_factor = (grid["order_volume"].values / C.REFERENCE_VOLUME) ** (-C.SCALE_ELASTICITY)
    landed_factor = 1 + C.LANDED_COST_BETA * (grid["distance_to_germany_km"].values / 5000.0)
    contract_factor = grid["c_price_mult"].values
    arch_factor = grid["price_mult"].values * (1 + grid["price_offset"].values)
    noise = rng.normal(0, grid["c_volatility"].values)

    unit_price = (grid["base_price"].values
                  * material_factor * energy_factor * capacity_factor
                  * fx_factor * scale_factor * landed_factor
                  * contract_factor * arch_factor * (1 + noise))
    floor = grid["base_price"].values * 0.30
    grid["unit_price"] = np.maximum(unit_price, floor).round(2)

    # ---- logistics cost (per order) ----------------------------------------
    grid["logistics_cost"] = (
        grid["distance_to_germany_km"].values * C.FREIGHT_RATE
        * grid["weight_factor"].values * en
        * np.sqrt(grid["order_volume"].values)
    ).round(2)

    # ---- lead time ---------------------------------------------------------
    base_lead = 6 + grid["distance_to_germany_km"].values / 350.0
    cap_stress = np.maximum(0, grid["supplier_capacity_utilization"].values - 0.88) * 60
    lead = (base_lead + grid["lead_adj"].values + cap_stress + rng.normal(0, 3, n))
    grid["lead_time_days"] = np.clip(lead, 3, 120).round().astype(int)

    # ---- delivery reliability ----------------------------------------------
    otd = (grid["otd"].values
           + 0.010 * grid["quality_offset"].values
           - 0.25 * np.maximum(0, grid["supplier_capacity_utilization"].values - 0.90)
           - 0.0009 * np.maximum(0, grid["lead_time_days"].values - 30)
           + rng.normal(0, 0.02, n))
    grid["on_time_delivery_rate"] = np.clip(otd, 0.55, 0.999).round(4)

    # ---- quality -----------------------------------------------------------
    defect = (grid["defect"].values
              * (1 + 0.8 * np.maximum(0, grid["supplier_capacity_utilization"].values - 0.88))
              * (1 - 0.08 * grid["quality_offset"].values)
              * (1 + rng.normal(0, 0.15, n)))
    grid["defect_rate"] = np.clip(defect, 0.0005, 0.15).round(4)
    grid["warranty_claim_rate"] = np.clip(
        grid["defect_rate"].values * rng.uniform(0.4, 0.7, n)
        + rng.normal(0, 0.002, n), 0.0002, 0.12
    ).round(4)

    # ---- external risk (lead-time & capacity lift risk) --------------------
    risk = (grid["country_risk_score"].values + grid["risk_adj"].values
            + 0.15 * np.maximum(0, grid["lead_time_days"].values - 30)
            + 12 * np.maximum(0, grid["supplier_capacity_utilization"].values - 0.92) / 0.08
            + rng.normal(0, 4, n))
    grid["risk_score_external"] = np.clip(risk, 1, 99).round(1)

    # ---- sustainability ----------------------------------------------------
    region_prior = grid["region"].map(C.SUSTAINABILITY_REGION_PRIOR).fillna(0).values
    sustain = (grid["sustain"].values + region_prior
               + 3 * grid["quality_offset"].values + rng.normal(0, 4, n))
    grid["sustainability_score"] = np.clip(sustain, 10, 99).round(1)

    # ---- award decision (needs component medians -> done on the frame) ------
    med = grid.groupby("component_type")["unit_price"].transform("median")
    price_ratio = grid["unit_price"] / med
    z = (1.8 * (1 - price_ratio)
         + 3.0 * (grid["on_time_delivery_rate"] - 0.90)
         - 25.0 * (grid["defect_rate"] - 0.02)
         - 0.4)
    prob = 1 / (1 + np.exp(-z))
    grid["final_awarded"] = (rng.random(n) < prob).astype(int)

    # ---- finalise ----------------------------------------------------------
    grid = grid.sort_values(["year", "month", "supplier_id", "component_type"]).reset_index(drop=True)
    grid.insert(0, "quote_id", [f"QT-{i + 1:06d}" for i in range(len(grid))])

    cols = [
        "quote_id", "supplier_id", "supplier_name", "component_type",
        "category", "country", "region", "year", "month",
        "order_volume", "unit_price", "raw_material_index", "energy_cost_index",
        "exchange_rate_index", "lead_time_days", "on_time_delivery_rate",
        "defect_rate", "warranty_claim_rate", "supplier_capacity_utilization",
        "logistics_cost", "risk_score_external", "contract_type",
        "sustainability_score", "final_awarded",
    ]
    out = grid[cols].rename(columns={"category": "component_category"})
    return out


def run(seed: int | None = None) -> pd.DataFrame:
    C.ensure_dirs()
    print("STAGE 2 | Generating synthetic supplier quotes (driven by real macro data)")
    df = generate(seed)
    df.to_csv(C.RAW_QUOTES_CSV, index=False)
    print(f"  + {C.SUPPLIER_MASTER_CSV.relative_to(C.PROJECT_ROOT)}  "
          f"(supplier dimension table, {df.supplier_id.nunique()} suppliers)")
    print(f"  + {C.RAW_QUOTES_CSV.relative_to(C.PROJECT_ROOT)}  "
          f"rows={len(df):,}  suppliers={df.supplier_id.nunique()}  "
          f"components={df.component_type.nunique()}  "
          f"months={df.groupby(['year','month']).ngroups}")
    print(f"  + awarded share={df.final_awarded.mean():.1%}  "
          f"median unit_price={df.unit_price.median():,.0f} EUR")
    return df


if __name__ == "__main__":
    run()
