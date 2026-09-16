"""Chapter: forecasting the 150%-time completion rate, and flagging
equity-gap risk, from the Graduation Rates / Outcome Measures components.

This mirrors ``forecast_enrollment`` structurally, and is the chapter
intended to attempt a partial replication of a published study (see the
book's Section 6, "peer-reviewed replication") -- always validate model
output against the institution's own IPEDS Data Feedback Report figure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split


@dataclass
class GraduationForecastResult:
    model: GradientBoostingRegressor
    mae: float
    rmse: float
    predictions: pd.DataFrame


def forecast_graduation_rate(
    panel: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "completion_rate_150pct",
    test_size: float = 0.25,
    random_state: int = 42,
) -> GraduationForecastResult:
    data = panel.dropna(subset=feature_cols + [target_col])
    if data.empty:
        raise ValueError("No rows remain after dropping missing target/features.")

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        data[feature_cols],
        data[target_col],
        data.index,
        test_size=test_size,
        random_state=random_state,
    )

    model = GradientBoostingRegressor(random_state=random_state)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))

    result_df = data.loc[idx_test, ["unitid", "survey_year", target_col]].copy()
    result_df["predicted"] = preds

    return GraduationForecastResult(model=model, mae=mae, rmse=rmse, predictions=result_df)


def flag_equity_risk(
    panel: pd.DataFrame, gap_col: str = "equity_completion_gap", threshold: float = 0.10
) -> pd.DataFrame:
    """Flag institution-years where the non-Pell/Pell completion gap
    exceeds ``threshold`` (default 10 percentage points) as equity-risk.
    """
    out = panel.copy()
    out["equity_risk_flag"] = out[gap_col] > threshold
    return out[["unitid", "survey_year", gap_col, "equity_risk_flag"]]
