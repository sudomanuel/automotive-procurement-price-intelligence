"""
src/data_acquisition.py
=======================
STAGE 1 of the pipeline -- DATA ACQUISITION (real / reference data first).

Pulls genuine public macro-economic series from FRED (Federal Reserve Economic
Data, St. Louis Fed) and writes them, together with an explicit country
reference table, into ``data/external/``:

    commodity_index.csv     <- aluminum / copper / iron-ore (steel proxy) prices
    energy_cost_index.csv   <- global energy price index
    exchange_rate_index.csv <- EUR/USD spot rate
    country_reference.csv    <- documented reference table (distance, risk, ...)

The FRED CSV endpoint needs no API key.  If the network is unavailable (e.g.
running offline / behind a proxy) every series falls back to a small,
deterministic, clearly-labelled sample series so the whole pipeline stays
reproducible.  Provenance (live vs fallback, URLs, row counts, timestamp) is
recorded in ``data/external/_acquisition_metadata.json`` for full lineage.

Run directly:   python -m src.data_acquisition
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import StringIO

import numpy as np
import pandas as pd
import requests

try:                       # support both "python -m src.x" and "python src/x.py"
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C


# --------------------------------------------------------------------------- #
# Low level helpers
# --------------------------------------------------------------------------- #
def _fetch_fred_series(series_id: str, timeout: int = 30) -> pd.DataFrame:
    """Download a single FRED series as a tidy [date, value] frame."""
    resp = requests.get(
        C.FRED_CSV_ENDPOINT, params={"id": series_id}, timeout=timeout
    )
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text))
    df.columns = ["date", "value"]                      # 1st col date, 2nd value
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().reset_index(drop=True)


def _window_months() -> pd.DatetimeIndex:
    return pd.date_range(C.WINDOW_START, periods=C.N_MONTHS, freq="MS")


def _to_monthly(df: pd.DataFrame) -> pd.Series:
    """Collapse a (possibly daily) series to a monthly mean indexed by month-start."""
    return df.set_index("date")["value"].resample("MS").mean()


def _slice_window(s: pd.Series) -> pd.Series:
    months = _window_months()
    return s.reindex(months).interpolate(limit_direction="both")


def _rebase_100(s: pd.Series) -> pd.Series:
    """Normalise so the base period (WINDOW_START) equals 100."""
    base = s.loc[pd.Timestamp(C.INDEX_BASE_DATE)]
    return s / base * 100.0


def _fallback_series(anchor: float, drift: float, seas_amp: float,
                     noise: float, rng: np.random.Generator) -> pd.Series:
    """Deterministic, realistic-looking monthly fallback series (clearly labelled)."""
    t = np.arange(C.N_MONTHS)
    level = anchor * (1 + drift * t / C.N_MONTHS + seas_amp * np.sin(2 * np.pi * t / 12))
    level = level * (1 + rng.normal(0, noise, C.N_MONTHS))
    return pd.Series(level, index=_window_months())


def _attach_calendar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.insert(1, "year", df["date"].dt.year)
    df.insert(2, "month", df["date"].dt.month)
    return df


# --------------------------------------------------------------------------- #
# Commodity / raw material index
# --------------------------------------------------------------------------- #
def acquire_commodities() -> tuple[pd.DataFrame, dict]:
    metals = {
        "aluminum_usd_ton": "PALUMUSDM",
        "copper_usd_ton": "PCOPPUSDM",
        "iron_ore_usd_ton": "PIORECRUSDM",
    }
    source = "FRED live"
    series = {}
    try:
        for col, sid in metals.items():
            series[col] = _slice_window(_to_monthly(_fetch_fred_series(sid)))
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [commodities] live fetch failed ({exc!s:.80}) -> fallback")
        source = "fallback"
        rng = np.random.default_rng(C.RANDOM_SEED)
        series = {
            "aluminum_usd_ton": _fallback_series(2400, 0.10, 0.05, 0.04, rng),
            "copper_usd_ton":   _fallback_series(8500, 0.18, 0.04, 0.04, rng),
            "iron_ore_usd_ton": _fallback_series(120, -0.10, 0.06, 0.05, rng),
        }

    out = pd.DataFrame(series)
    # composite raw-material index: weighted average of rebased metals (100 = base)
    rebased = pd.DataFrame({c: _rebase_100(out[c]) for c in out.columns})
    out["raw_material_index"] = sum(
        rebased[c] * w for c, w in C.RAW_MATERIAL_WEIGHTS.items()
    ).round(2)
    for c in metals:
        out[c] = out[c].round(2)
    out = out.reset_index(names="date")
    out["source"] = source
    out = _attach_calendar(out)
    out.to_csv(C.COMMODITY_CSV, index=False)

    prov = dict(
        dataset="commodity_index.csv", source=source,
        fred_series=metals if source == "FRED live" else None,
        url=f"{C.FRED_CSV_ENDPOINT}?id=PALUMUSDM (+PCOPPUSDM,PIORECRUSDM)",
        rows=len(out),
        columns=list(out.columns),
        note="raw_material_index = 0.45*aluminum + 0.30*copper + 0.25*iron_ore "
             "(each rebased to 100 at the window start).",
    )
    return out, prov


# --------------------------------------------------------------------------- #
# Energy cost index
# --------------------------------------------------------------------------- #
def acquire_energy() -> tuple[pd.DataFrame, dict]:
    source = "FRED live"
    try:
        raw = _slice_window(_to_monthly(_fetch_fred_series("PNRGINDEXM")))
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [energy] live fetch failed ({exc!s:.80}) -> fallback")
        source = "fallback"
        rng = np.random.default_rng(C.RANDOM_SEED + 1)
        raw = _fallback_series(180, 0.05, 0.10, 0.06, rng)

    out = pd.DataFrame({"energy_index_raw": raw.round(2)})
    out["energy_cost_index"] = _rebase_100(raw).round(2)
    out = out.reset_index(names="date")
    out["source"] = source
    out = _attach_calendar(out)
    out.to_csv(C.ENERGY_CSV, index=False)

    prov = dict(
        dataset="energy_cost_index.csv", source=source,
        fred_series={"energy_index_raw": "PNRGINDEXM"} if source == "FRED live" else None,
        url=f"{C.FRED_CSV_ENDPOINT}?id=PNRGINDEXM",
        rows=len(out), columns=list(out.columns),
        note="Global price of Energy index (2016=100), rebased to 100 at window start.",
    )
    return out, prov


# --------------------------------------------------------------------------- #
# Exchange-rate index  (EUR/USD)
# --------------------------------------------------------------------------- #
def acquire_exchange() -> tuple[pd.DataFrame, dict]:
    source = "FRED live"
    try:
        eur_usd = _slice_window(_to_monthly(_fetch_fred_series("DEXUSEU")))
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [exchange] live fetch failed ({exc!s:.80}) -> fallback")
        source = "fallback"
        rng = np.random.default_rng(C.RANDOM_SEED + 2)
        eur_usd = _fallback_series(1.08, -0.04, 0.03, 0.02, rng)

    out = pd.DataFrame({"eur_usd": eur_usd.round(4)})
    out["exchange_rate_index"] = _rebase_100(eur_usd).round(2)
    out = out.reset_index(names="date")
    out["source"] = source
    out = _attach_calendar(out)
    out.to_csv(C.EXCHANGE_CSV, index=False)

    prov = dict(
        dataset="exchange_rate_index.csv", source=source,
        fred_series={"eur_usd": "DEXUSEU"} if source == "FRED live" else None,
        url=f"{C.FRED_CSV_ENDPOINT}?id=DEXUSEU",
        rows=len(out), columns=list(out.columns),
        note="US$ per 1 EUR, monthly mean, rebased to 100 at window start. "
             "A FALLING index = weaker EUR = more expensive non-EUR imports.",
    )
    return out, prov


# --------------------------------------------------------------------------- #
# Country reference table  (explicit documented reference data)
# --------------------------------------------------------------------------- #
def build_country_reference() -> tuple[pd.DataFrame, dict]:
    out = pd.DataFrame(C.COUNTRY_REFERENCE, columns=C.COUNTRY_REFERENCE_COLUMNS)
    out.to_csv(C.COUNTRY_CSV, index=False)
    prov = dict(
        dataset="country_reference.csv", source="reference table (curated)",
        url=None, rows=len(out), columns=list(out.columns),
        note="Manually curated reference table. distance_to_germany_km is an "
             "approximate one-way freight distance to a central German hub; "
             "country_risk_score (0-100) is an illustrative supply-chain risk "
             "PROXY, not a live feed.",
    )
    return out, prov


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run() -> dict:
    C.ensure_dirs()
    print("STAGE 1 | Data acquisition (real / reference data)")
    provenances = []
    for fn in (acquire_commodities, acquire_energy, acquire_exchange,
               build_country_reference):
        df, prov = fn()
        provenances.append(prov)
        print(f"  + {prov['dataset']:<24} source={prov['source']:<22} rows={prov['rows']}")

    meta = dict(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        window_start=C.WINDOW_START, window_end=C.WINDOW_END,
        index_base_date=C.INDEX_BASE_DATE,
        fred_endpoint=C.FRED_CSV_ENDPOINT,
        datasets=provenances,
    )
    with open(C.ACQUISITION_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"  + provenance written to {C.ACQUISITION_META.name}")
    return meta


if __name__ == "__main__":
    run()
