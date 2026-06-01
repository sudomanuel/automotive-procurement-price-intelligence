"""
src/visualization.py
====================
STAGE 6 of the pipeline -- REPORTING FIGURES.

Reads the external indices, the processed quotes, the scorecard and the model
artefacts, and writes the ten mandated figures to ``reports/figures/``:

    01_commodity_index_trend.png          06_top_10_supplier_scores.png
    02_price_by_component_type.png        07_supplier_risk_vs_score.png
    03_raw_material_vs_unit_price.png     08_actual_vs_predicted_price.png
    04_order_volume_vs_price.png          09_feature_importance_price_model.png
    05_cost_vs_reliability.png            10_supplier_category_heatmap.png

Run directly:   python -m src.visualization
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")                       # headless / no display required
import matplotlib.pyplot as plt             # noqa: E402
import numpy as np                          # noqa: E402
import pandas as pd                         # noqa: E402
import seaborn as sns                       # noqa: E402

try:
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C

sns.set_theme(style="whitegrid", context="talk")
plt.rcParams["figure.autolayout"] = False
plt.rcParams["axes.titleweight"] = "bold"

CATEGORY_COLORS = {
    "Strategic Partner": "#2ca02c",
    "Reliable but Expensive": "#1f77b4",
    "Cost Efficient": "#ff7f0e",
    "High Risk": "#d62728",
    "Needs Improvement": "#7f7f7f",
}
ACCENT = "#b3122b"          # premium-automotive red accent


def _save(fig, name: str) -> None:
    path = C.FIGURES_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  + {path.relative_to(C.PROJECT_ROOT)}")


# --------------------------------------------------------------------------- #
def fig_01_commodity_trend() -> None:
    com = pd.read_csv(C.COMMODITY_CSV, parse_dates=["date"])
    ene = pd.read_csv(C.ENERGY_CSV, parse_dates=["date"])
    fx = pd.read_csv(C.EXCHANGE_CSV, parse_dates=["date"])

    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col, lab, c in [("aluminum_usd_ton", "Aluminum", "#8c8c8c"),
                        ("copper_usd_ton", "Copper", "#b87333"),
                        ("iron_ore_usd_ton", "Iron ore (steel proxy)", "#4d4d4d")]:
        ax.plot(com["date"], com[col] / com[col].iloc[0] * 100,
                lw=1.6, alpha=0.7, label=lab)
    ax.plot(com["date"], com["raw_material_index"], lw=3.2, color=ACCENT,
            label="Composite raw-material index")
    ax.plot(ene["date"], ene["energy_cost_index"], lw=2.4, ls="--",
            color="#1f77b4", label="Energy cost index")
    ax.plot(fx["date"], fx["exchange_rate_index"], lw=2.0, ls=":",
            color="#2ca02c", label="EUR/USD index")
    ax.axhline(100, color="black", lw=0.8, alpha=0.4)
    ax.set_title("Real macro drivers, rebased to 100 at Jan-2022\n(source: FRED — "
                 "commodities, energy & EUR/USD)")
    ax.set_ylabel("Index (Jan-2022 = 100)")
    ax.set_xlabel("")
    ax.legend(fontsize=11, ncol=2, loc="upper right", framealpha=0.9)
    _save(fig, "01_commodity_index_trend.png")


def fig_02_price_by_component(df: pd.DataFrame) -> None:
    order = (df.groupby("component_type")["unit_price"].median()
             .sort_values(ascending=False).index)
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.boxplot(data=df, y="component_type", x="unit_price", order=order,
                ax=ax, color="#4c72b0", fliersize=1.5, linewidth=1.2)
    ax.set_xscale("log")
    ax.set_title("Unit price distribution by component type (log scale)")
    ax.set_xlabel("Unit price (EUR, log scale)")
    ax.set_ylabel("")
    _save(fig, "02_price_by_component_type.png")


def fig_03_raw_material_vs_price(df: pd.DataFrame) -> None:
    sub = df[df["component_type"] == "Aluminum Casting"]
    r = sub["raw_material_index"].corr(sub["unit_price"])
    fig, ax = plt.subplots(figsize=(11, 6.8))
    sns.regplot(data=sub, x="raw_material_index", y="unit_price", ax=ax,
                scatter_kws=dict(alpha=0.25, s=22, color="#8c8c8c"),
                line_kws=dict(color=ACCENT, lw=3))
    ax.set_title("Raw-material index vs unit price — Aluminum Casting\n"
                 f"(material-intensive component, Pearson r = {r:.2f})")
    ax.set_xlabel("Raw-material index (real FRED commodities, Jan-2022 = 100)")
    ax.set_ylabel("Unit price (EUR)")
    _save(fig, "03_raw_material_vs_unit_price.png")


def fig_04_volume_vs_price(df: pd.DataFrame) -> None:
    r = np.log(df["order_volume"]).corr(df["price_ratio_vs_median"])
    fig, ax = plt.subplots(figsize=(11, 6.8))
    sns.regplot(data=df, x="order_volume", y="price_ratio_vs_median", ax=ax,
                logx=True, scatter_kws=dict(alpha=0.15, s=16, color="#8c8c8c"),
                line_kws=dict(color=ACCENT, lw=3))
    ax.set_xscale("log")
    ax.axhline(1.0, color="black", lw=0.8, alpha=0.4)
    ax.set_title("Economies of scale: order volume vs price level\n"
                 f"(price relative to each component's median, r = {r:.2f})")
    ax.set_xlabel("Order volume (units, log scale)")
    ax.set_ylabel("Unit price ÷ component median")
    _save(fig, "04_order_volume_vs_price.png")


def fig_05_cost_vs_reliability(sc: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7.5))
    for cat, c in CATEGORY_COLORS.items():
        s = sc[sc["supplier_category"] == cat]
        ax.scatter(s["cost_competitiveness_score"], s["delivery_reliability_score"],
                   s=70, alpha=0.85, color=c, label=cat, edgecolor="white", linewidth=0.6)
    ax.axvline(sc["cost_competitiveness_score"].median(), color="black", lw=0.8, alpha=0.35)
    ax.axhline(sc["delivery_reliability_score"].median(), color="black", lw=0.8, alpha=0.35)
    ax.set_title("Cheap vs reliable: the core procurement trade-off")
    ax.set_xlabel("Cost competitiveness score  (higher = cheaper)")
    ax.set_ylabel("Delivery reliability score  (higher = better)")
    ax.legend(fontsize=10, title="Category", loc="lower left", framealpha=0.9)
    _save(fig, "05_cost_vs_reliability.png")


def fig_06_top10_scores(sc: pd.DataFrame) -> None:
    top = sc.nlargest(10, "final_supplier_score").iloc[::-1]
    colors = [CATEGORY_COLORS[c] for c in top["supplier_category"]]
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(top["supplier_name"], top["final_supplier_score"], color=colors)
    for y, (v, cat) in enumerate(zip(top["final_supplier_score"], top["supplier_category"])):
        ax.text(v - 1.5, y, f"{v:.0f}", va="center", ha="right",
                color="white", fontweight="bold", fontsize=11)
    ax.set_title("Top 10 suppliers by overall scorecard")
    ax.set_xlabel("Final supplier score (0-100)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CATEGORY_COLORS.values()]
    ax.legend(handles, CATEGORY_COLORS.keys(), fontsize=9, loc="lower right", title="Category")
    _save(fig, "06_top_10_supplier_scores.png")


def fig_07_risk_vs_score(sc: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7.5))
    for cat, c in CATEGORY_COLORS.items():
        s = sc[sc["supplier_category"] == cat]
        ax.scatter(s["avg_risk_score_external"], s["final_supplier_score"],
                   s=s["total_spend"] / s["total_spend"].max() * 600 + 30 if len(s) else 30,
                   alpha=0.7, color=c, label=cat, edgecolor="white", linewidth=0.6)
    ax.set_title("Supplier risk vs overall score\n(bubble size = total spend — big risky bubbles = act first)")
    ax.set_xlabel("Average external risk score  (higher = riskier)")
    ax.set_ylabel("Final supplier score (0-100)")
    ax.legend(fontsize=10, title="Category", loc="upper right", framealpha=0.9)
    _save(fig, "07_supplier_risk_vs_score.png")


def fig_08_actual_vs_predicted() -> None:
    pred = pd.read_csv(C.REPORTS_DIR / "_model_predictions.csv")
    metrics = pd.read_csv(C.MODEL_METRICS_CSV)
    best = metrics.iloc[0]
    fig, ax = plt.subplots(figsize=(9.5, 9))
    ax.scatter(pred["actual_unit_price"], pred["predicted_unit_price"],
               alpha=0.25, s=20, color="#1f77b4", edgecolor="none")
    lims = [pred[["actual_unit_price", "predicted_unit_price"]].min().min(),
            pred[["actual_unit_price", "predicted_unit_price"]].max().max()]
    ax.plot(lims, lims, color=ACCENT, lw=2, ls="--", label="perfect prediction")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_title(f"Actual vs predicted unit price — {best['model']}\n"
                 f"R² = {best['R2']:.3f}   MAE = €{best['MAE']:.0f}   "
                 f"MAPE = {best['MAPE_%']:.1f}%")
    ax.set_xlabel("Actual unit price (EUR, log)")
    ax.set_ylabel("Predicted unit price (EUR, log)")
    ax.legend(fontsize=11, loc="upper left")
    _save(fig, "08_actual_vs_predicted_price.png")


def fig_09_feature_importance() -> None:
    fi = pd.read_csv(C.REPORTS_DIR / "_feature_importance.csv").head(12).iloc[::-1]
    labels = (fi["feature"].str.replace("cat__", "", regex=False)
              .str.replace("num__", "", regex=False)
              .str.replace("_", " "))
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(labels, fi["importance"], color="#4c72b0")
    ax.set_title(f"Price-model feature importance — {fi['source_model'].iloc[0]}")
    ax.set_xlabel("Importance (impurity reduction)")
    _save(fig, "09_feature_importance_price_model.png")


def fig_10_category_heatmap(sc: pd.DataFrame) -> None:
    dims = {
        "cost_competitiveness_score": "Cost",
        "delivery_reliability_score": "Delivery",
        "quality_performance_score": "Quality",
        "risk_exposure_score": "Risk",
        "sustainability_score_norm": "Sustainability",
    }
    order = [c for c in CATEGORY_COLORS if c in sc["supplier_category"].unique()]
    mat = (sc.groupby("supplier_category")[list(dims)].mean()
           .reindex(order).rename(columns=dims))
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    sns.heatmap(mat, annot=True, fmt=".0f", cmap="RdYlGn", vmin=0, vmax=100,
                linewidths=0.6, cbar_kws={"label": "score (0-100)"}, ax=ax)
    ax.set_title("Average scorecard profile by supplier category")
    ax.set_ylabel(""); ax.set_xlabel("")
    plt.setp(ax.get_yticklabels(), rotation=0)
    _save(fig, "10_supplier_category_heatmap.png")


def run() -> None:
    C.ensure_dirs()
    print("STAGE 6 | Building report figures")
    df = pd.read_csv(C.PROCESSED_QUOTES_CSV)
    sc = pd.read_csv(C.SCORECARD_CSV)

    fig_01_commodity_trend()
    fig_02_price_by_component(df)
    fig_03_raw_material_vs_price(df)
    fig_04_volume_vs_price(df)
    fig_05_cost_vs_reliability(sc)
    fig_06_top10_scores(sc)
    fig_07_risk_vs_score(sc)
    fig_08_actual_vs_predicted()
    fig_09_feature_importance()
    fig_10_category_heatmap(sc)


if __name__ == "__main__":
    run()
