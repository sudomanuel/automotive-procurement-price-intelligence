"""
notebooks/build_notebooks.py
============================
Generates the five analysis notebooks (notebooks-as-code, so they stay in sync
with src/ and are trivially regenerable):

    01_data_acquisition_macro_drivers.ipynb
    02_generate_supplier_quotes.ipynb
    03_procurement_eda.ipynb
    04_price_forecasting_model.ipynb
    05_supplier_scorecard.ipynb

The notebooks LOAD the artefacts produced by `python run_pipeline.py` and add
narrative + analysis on top, so executing them is fast and never rewrites data.

Usage:   python notebooks/build_notebooks.py
"""
from __future__ import annotations

import pathlib

import nbformat as nbf

HERE = pathlib.Path(__file__).resolve().parent

# Boot cell prepended to every notebook so `from src import ...` works regardless
# of the working directory the notebook is launched from.
BOOT = """\
%matplotlib inline
import sys, pathlib
ROOT = pathlib.Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

import pandas as pd, numpy as np
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 40, "display.width", 160)
from src import config as C
print("project root:", ROOT)"""


def nb(*cells) -> nbf.NotebookNode:
    n = nbf.v4.new_notebook()
    n.cells = list(cells)
    n.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return n


def md(src: str):
    return nbf.v4.new_markdown_cell(src)


def code(src: str):
    return nbf.v4.new_code_cell(src)


# --------------------------------------------------------------------------- #
# 01 — Data acquisition
# --------------------------------------------------------------------------- #
nb01 = nb(
    md("# 01 · Data Acquisition — Real Macro Drivers\n"
       "**Principle: real public / reference data first, synthetic business data second.**\n\n"
       "This notebook inspects the *real* external data the project is built on: commodity, "
       "energy and FX series pulled from **FRED** (St. Louis Fed), plus a curated country "
       "reference table. Produced by `python -m src.data_acquisition`."),
    code(BOOT),
    md("## Provenance\nEvery run records where each dataset came from (live FRED vs documented fallback)."),
    code("import json\n"
         "meta = json.loads(C.ACQUISITION_META.read_text())\n"
         "print('window:', meta['window_start'], '->', meta['window_end'])\n"
         "for d in meta['datasets']:\n"
         "    print(f\"  {d['dataset']:<26} source={d['source']:<24} rows={d['rows']}\")"),
    md("## The three real index series"),
    code("com = pd.read_csv(C.COMMODITY_CSV, parse_dates=['date'])\n"
         "ene = pd.read_csv(C.ENERGY_CSV, parse_dates=['date'])\n"
         "fx  = pd.read_csv(C.EXCHANGE_CSV, parse_dates=['date'])\n"
         "com.head()"),
    code("fig, ax = plt.subplots(figsize=(11,5.5))\n"
         "ax.plot(com.date, com.raw_material_index, lw=3, color='#b3122b', label='Raw-material index')\n"
         "ax.plot(ene.date, ene.energy_cost_index, lw=2, ls='--', color='#1f77b4', label='Energy cost index')\n"
         "ax.plot(fx.date,  fx.exchange_rate_index, lw=2, ls=':', color='#2ca02c', label='EUR/USD index')\n"
         "ax.axhline(100, color='k', lw=.8, alpha=.4)\n"
         "ax.set_title('Real macro drivers (FRED), rebased to 100 at Jan-2022'); ax.legend(); plt.show()"),
    md("**Read-out.** The data carries genuine economic history: the **2022 energy crisis** "
       "(energy index peaking ~156, +56%), cooling commodity markets afterwards, and a "
       "**weakening euro**. These real movements drive the synthetic prices in notebook 02."),
    code("country = pd.read_csv(C.COUNTRY_CSV)\ncountry"),
)

# --------------------------------------------------------------------------- #
# 02 — Generate supplier quotes
# --------------------------------------------------------------------------- #
nb02 = nb(
    md("# 02 · Synthetic Supplier Quotes (calibrated to real data)\n"
       "Supplier quotations are confidential, so they are **simulated** — but every quote "
       "inherits the real macro indices for its month and `unit_price` is an explicit "
       "function of them. Produced by `python -m src.data_generation`."),
    code(BOOT),
    code("q = pd.read_csv(C.RAW_QUOTES_CSV)\n"
         "master = pd.read_csv(C.SUPPLIER_MASTER_CSV)\n"
         "print(q.shape, '| suppliers:', q.supplier_id.nunique(), '| months:', q.groupby(['year','month']).ngroups)\n"
         "q.head()"),
    md("## Star schema\nA **fact table** of quotes + a **supplier dimension** table (which also "
       "holds the latent generating archetype, used later only for validation)."),
    code("master.head()"),
    md("## Do the encoded relationships hold?\nThese are the assumptions the brief requires; "
       "we verify them directly in the generated data."),
    code("# (a) material-intensive part tracks the real commodity index\n"
         "ac = q[q.component_type=='Aluminum Casting']\n"
         "print('Aluminum Casting  r(raw_material_index, unit_price) =', round(ac.raw_material_index.corr(ac.unit_price),2))\n\n"
         "# (b) Spot is the most volatile contract type (within component)\n"
         "cv = (q.groupby(['component_type','contract_type']).unit_price.apply(lambda s: s.std()/s.mean())\n"
         "        .groupby('contract_type').mean().round(3))\n"
         "print('\\nwithin-component price CV by contract type:'); print(cv)\n\n"
         "# (c) economies of scale\n"
         "print('\\nr(log order_volume, price/median) =', round(np.log(q.order_volume).corr(q.unit_price/q.groupby('component_type').unit_price.transform('median')),2))"),
    code("order = q.groupby('component_type').unit_price.median().sort_values(ascending=False).index\n"
         "fig, ax = plt.subplots(figsize=(11,6))\n"
         "sns.boxplot(data=q, y='component_type', x='unit_price', order=order, color='#4c72b0', fliersize=1)\n"
         "ax.set_xscale('log'); ax.set_title('Unit price by component type (log)'); plt.show()"),
    md("Battery Module & Electric Motor Part dominate the price scale; commodities/energy/FX "
       "drive the variation *within* each component tier."),
)

# --------------------------------------------------------------------------- #
# 03 — EDA
# --------------------------------------------------------------------------- #
nb03 = nb(
    md("# 03 · Procurement EDA\n"
       "Exploratory analysis of the cleaned dataset covering the mandated questions: price by "
       "component & country, macro co-movement, economies of scale, supplier delivery/quality/risk."),
    code(BOOT),
    code("df = pd.read_csv(C.PROCESSED_QUOTES_CSV, parse_dates=['date'])\nprint(df.shape); df.head()"),
    md("## Price by component type and by country"),
    code("display(df.groupby('component_type').unit_price.median().sort_values(ascending=False).round(0).to_frame('median_price'))\n"
         "display(df.groupby('country').unit_price.median().sort_values(ascending=False).round(0).to_frame('median_price'))"),
    md("## Macro co-movement: monthly average price vs commodity index"),
    code("m = df.groupby('date').agg(avg_price=('unit_price','mean'), rawmat=('raw_material_index','mean'),\n"
         "                           energy=('energy_cost_index','mean')).reset_index()\n"
         "fig, ax = plt.subplots(figsize=(11,5))\n"
         "ax.plot(m.date, m.avg_price/m.avg_price.iloc[0]*100, lw=3, color='#b3122b', label='Avg unit price (idx)')\n"
         "ax.plot(m.date, m.rawmat, lw=2, ls='--', label='Raw-material index')\n"
         "ax.plot(m.date, m.energy, lw=2, ls=':', label='Energy index')\n"
         "ax.set_title('Monthly average price vs real macro indices (rebased)'); ax.legend(); plt.show()"),
    md("## Economies of scale & macro sensitivity"),
    code("fig, axes = plt.subplots(1,2, figsize=(14,5))\n"
         "sns.regplot(data=df, x='order_volume', y='price_ratio_vs_median', logx=True, ax=axes[0],\n"
         "            scatter_kws=dict(alpha=.15,s=12,color='gray'), line_kws=dict(color='#b3122b'))\n"
         "axes[0].set_xscale('log'); axes[0].axhline(1,color='k',lw=.7,alpha=.4); axes[0].set_title('Order volume vs price level')\n"
         "ac = df[df.component_type=='Aluminum Casting']\n"
         "sns.regplot(data=ac, x='raw_material_index', y='unit_price', ax=axes[1],\n"
         "            scatter_kws=dict(alpha=.25,s=18,color='gray'), line_kws=dict(color='#b3122b'))\n"
         "axes[1].set_title('Raw material vs price (Aluminum Casting)'); plt.tight_layout(); plt.show()"),
    md("## Supplier reliability, quality and risk"),
    code("sup = df.groupby(['supplier_id','country']).agg(\n"
         "    otd=('on_time_delivery_rate','mean'), defect=('defect_rate','mean'),\n"
         "    lead=('lead_time_days','mean'), risk=('risk_score_external','mean')).reset_index()\n"
         "print('Risk by region:'); display(df.groupby('region').risk_score_external.mean().round(1).to_frame())\n"
         "fig, ax = plt.subplots(figsize=(9,6))\n"
         "sns.scatterplot(data=sup, x='otd', y='defect', hue='country', s=70, ax=ax)\n"
         "ax.set_title('Suppliers: on-time delivery vs defect rate'); ax.invert_yaxis(); plt.show()"),
    md("**Read-out.** Average price tracks the real commodity & energy cycle; larger orders "
       "price below the component median; overseas regions (Asia, the Americas) carry higher risk."),
)

# --------------------------------------------------------------------------- #
# 04 — Price forecasting
# --------------------------------------------------------------------------- #
nb04 = nb(
    md("# 04 · Price Forecasting\n"
       "Predict `unit_price` from component, sourcing, contract, order and **real macro** features. "
       "Compare a linear baseline against Random Forest and Gradient Boosting."),
    code(BOOT),
    code("from src import price_model as pm\n"
         "df = pd.read_csv(C.PROCESSED_QUOTES_CSV)\n"
         "art = pm.train_and_evaluate(df)\n"
         "art.metrics"),
    md("Non-linear models beat the linear baseline, especially on **MAPE**, because the price "
       "drivers act multiplicatively."),
    code("yt = art.y_test; yp = art.predictions[art.best_name]\n"
         "fig, axes = plt.subplots(1,2, figsize=(14,6))\n"
         "axes[0].scatter(yt, yp, alpha=.25, s=18, color='#1f77b4')\n"
         "lim=[min(yt.min(),yp.min()), max(yt.max(),yp.max())]\n"
         "axes[0].plot(lim,lim,'--',color='#b3122b'); axes[0].set_xscale('log'); axes[0].set_yscale('log')\n"
         "axes[0].set_title(f'Actual vs predicted — {art.best_name}'); axes[0].set_xlabel('actual'); axes[0].set_ylabel('predicted')\n"
         "res = yp - yt\n"
         "axes[1].hist(res, bins=50, color='#4c72b0'); axes[1].axvline(0,color='#b3122b')\n"
         "axes[1].set_title('Residuals (pred - actual)'); plt.tight_layout(); plt.show()"),
    md("## Feature importance"),
    code("fi = art.feature_importance.head(12).iloc[::-1]\n"
         "labels = fi.feature.str.replace('cat__','',regex=False).str.replace('num__','',regex=False).str.replace('_',' ')\n"
         "fig, ax = plt.subplots(figsize=(10,6)); ax.barh(labels, fi.importance, color='#4c72b0')\n"
         "ax.set_title(f'Feature importance — {art.best_name}'); plt.show()"),
    md("**Read-out.** Component identity sets the price tier; logistics cost, energy index, "
       "lead time, order volume and the commodity index drive variation within a tier. The model "
       "gives buyers an *expected price* to flag quotes that sit materially above it."),
)

# --------------------------------------------------------------------------- #
# 05 — Supplier scorecard
# --------------------------------------------------------------------------- #
nb05 = nb(
    md("# 05 · Supplier Scorecard\n"
       "Turn the quote-level data into one row per supplier scored 0–100 on five **configurable** "
       "weighted dimensions, then assign a category and a recommended action."),
    code(BOOT),
    code("from src import supplier_scoring as ss\n"
         "df = pd.read_csv(C.PROCESSED_QUOTES_CSV)\n"
         "print('weights:', C.SCORECARD_WEIGHTS)\n"
         "sc = ss.score_suppliers(df)\n"
         "sc[['supplier_name','country','final_supplier_score','supplier_category','recommended_action']].head(10)"),
    md("## Category & action distribution"),
    code("display(sc.supplier_category.value_counts().to_frame('suppliers'))\n"
         "display(sc.recommended_action.value_counts().to_frame('suppliers'))"),
    md("## Scorecard profile by category"),
    code("dims = {'cost_competitiveness_score':'Cost','delivery_reliability_score':'Delivery',\n"
         "        'quality_performance_score':'Quality','risk_exposure_score':'Risk','sustainability_score_norm':'Sustainability'}\n"
         "order=[c for c in ['Strategic Partner','Reliable but Expensive','Cost Efficient','High Risk','Needs Improvement'] if c in sc.supplier_category.unique()]\n"
         "mat = sc.groupby('supplier_category')[list(dims)].mean().reindex(order).rename(columns=dims)\n"
         "fig, ax = plt.subplots(figsize=(10,5.5))\n"
         "sns.heatmap(mat, annot=True, fmt='.0f', cmap='RdYlGn', vmin=0, vmax=100, linewidths=.5, ax=ax)\n"
         "ax.set_title('Average scorecard profile by category'); ax.set_ylabel(''); plt.show()"),
    md("## Validation — does the scorecard rediscover the latent archetypes?\n"
       "The generating archetype is hidden ground truth (it would not exist in real data)."),
    code("master = pd.read_csv(C.SUPPLIER_MASTER_CSV)[['supplier_id','archetype']]\n"
         "j = sc.merge(master, on='supplier_id')\n"
         "pd.crosstab(j.archetype, j.supplier_category)"),
    md("## Top and bottom suppliers"),
    code("cols=['supplier_name','country','final_supplier_score','supplier_category','recommended_action']\n"
         "print('TOP 5'); display(sc.nlargest(5,'final_supplier_score')[cols])\n"
         "print('BOTTOM 5'); display(sc.nsmallest(5,'final_supplier_score')[cols])"),
    md("**Business decision.** Prioritize the strategic partners, renegotiate with the premium "
       "suppliers that hold the largest spend share, and reduce dependency on the high-risk, "
       "high-spend vendors concentrated in a single region."),
)

NOTEBOOKS = {
    "01_data_acquisition_macro_drivers.ipynb": nb01,
    "02_generate_supplier_quotes.ipynb": nb02,
    "03_procurement_eda.ipynb": nb03,
    "04_price_forecasting_model.ipynb": nb04,
    "05_supplier_scorecard.ipynb": nb05,
}


def main() -> None:
    for name, notebook in NOTEBOOKS.items():
        path = HERE / name
        nbf.write(notebook, path)
        print(f"  + {path.name}")


if __name__ == "__main__":
    main()
