"""
src/price_model.py
==================
STAGE 4 of the pipeline -- COMPONENT PRICE FORECASTING.

Predicts ``unit_price`` from component, sourcing, contract, order and real
macro-economic features.  Three models are compared:

    * Linear Regression        (interpretable baseline)
    * Random Forest Regressor  (non-linear, captures interactions)
    * Gradient Boosting Reg.   (non-linear, strong tabular performer)

Metrics: MAE, RMSE, R2, MAPE (on a held-out 20% test split).

Business use: a defensible "expected price" for a component given its drivers,
so buyers can flag quotes that are materially above the model expectation and
quantify how much commodity / energy / FX moves explain price changes.

Artefacts written to reports/ (consumed by visualization.py):
    model_comparison.csv      -- metric table for all three models
    _model_predictions.csv    -- actual vs predicted (best model) on the test set
    _feature_importance.csv   -- importance ranking (best tree model)

Run directly:   python -m src.price_model
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (mean_absolute_error,
                             mean_absolute_percentage_error,
                             mean_squared_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from . import config as C
except ImportError:        # pragma: no cover
    import config as C

TARGET = "unit_price"
CAT_FEATURES = ["component_type", "component_category", "country",
                "region", "contract_type"]
NUM_FEATURES = ["order_volume", "raw_material_index", "energy_cost_index",
                "exchange_rate_index", "lead_time_days",
                "supplier_capacity_utilization", "logistics_cost",
                "sustainability_score"]
FEATURES = CAT_FEATURES + NUM_FEATURES


@dataclass
class ModelArtifacts:
    metrics: pd.DataFrame
    best_name: str
    best_pipeline: Pipeline
    y_test: np.ndarray
    predictions: dict = field(default_factory=dict)   # name -> y_pred (test)
    test_index: pd.Index = None
    feature_importance: pd.DataFrame = None


def _build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
            ("num", StandardScaler(), NUM_FEATURES),
        ]
    )


def _models() -> dict[str, object]:
    return {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=300, max_depth=None, min_samples_leaf=2,
            n_jobs=-1, random_state=C.RANDOM_SEED),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=400, max_depth=3, learning_rate=0.05,
            subsample=0.9, random_state=C.RANDOM_SEED),
    }


def _metrics(y_true, y_pred) -> dict:
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": r2_score(y_true, y_pred),
        "MAPE_%": mean_absolute_percentage_error(y_true, y_pred) * 100,
    }


def train_and_evaluate(df: pd.DataFrame) -> ModelArtifacts:
    X = df[FEATURES].copy()
    y = df[TARGET].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=C.RANDOM_SEED
    )

    rows, preds, fitted = [], {}, {}
    for name, est in _models().items():
        pipe = Pipeline([("prep", _build_preprocessor()), ("model", est)])
        pipe.fit(X_train, y_train)
        yhat_tr = pipe.predict(X_train)
        yhat_te = pipe.predict(X_test)
        m = _metrics(y_test, yhat_te)
        m["model"] = name
        m["R2_train"] = r2_score(y_train, yhat_tr)
        rows.append(m)
        preds[name] = yhat_te
        fitted[name] = pipe

    metrics = (pd.DataFrame(rows)
               [["model", "MAE", "RMSE", "R2", "MAPE_%", "R2_train"]]
               .sort_values("RMSE").reset_index(drop=True)).round(4)

    best_name = metrics.iloc[0]["model"]
    best_pipe = fitted[best_name]

    # ---- feature importance from the best available tree model -------------
    imp_source = best_name if best_name != "Linear Regression" else "Random Forest"
    imp_pipe = fitted[imp_source]
    feat_names = imp_pipe.named_steps["prep"].get_feature_names_out()
    importances = imp_pipe.named_steps["model"].feature_importances_
    fi = (pd.DataFrame({"feature": feat_names, "importance": importances})
          .sort_values("importance", ascending=False).reset_index(drop=True))
    fi["source_model"] = imp_source

    return ModelArtifacts(
        metrics=metrics, best_name=best_name, best_pipeline=best_pipe,
        y_test=y_test, predictions=preds, test_index=X_test.index,
        feature_importance=fi,
    )


def run(df: pd.DataFrame | None = None) -> ModelArtifacts:
    C.ensure_dirs()
    print("STAGE 4 | Price forecasting (Linear / Random Forest / Gradient Boosting)")
    if df is None:
        df = pd.read_csv(C.PROCESSED_QUOTES_CSV)
    art = train_and_evaluate(df)

    art.metrics.to_csv(C.MODEL_METRICS_CSV, index=False)

    best_pred = art.predictions[art.best_name]
    comp = df.loc[art.test_index, "component_type"].values
    pd.DataFrame({
        "component_type": comp,
        "actual_unit_price": art.y_test,
        "predicted_unit_price": best_pred.round(2),
        "model": art.best_name,
    }).to_csv(C.REPORTS_DIR / "_model_predictions.csv", index=False)

    art.feature_importance.to_csv(
        C.REPORTS_DIR / "_feature_importance.csv", index=False)

    print(art.metrics.to_string(index=False))
    print(f"  + best model: {art.best_name}  "
          f"(R2={art.metrics.iloc[0]['R2']:.3f}, "
          f"MAPE={art.metrics.iloc[0]['MAPE_%']:.1f}%)")
    print(f"  + artefacts -> {C.MODEL_METRICS_CSV.name}, _model_predictions.csv, "
          f"_feature_importance.csv")
    return art


if __name__ == "__main__":
    run()
