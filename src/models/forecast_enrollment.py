"""Chapter: forecasting institution-level enrollment trends.

The panel is a temporal dataset, so splits must respect time (train on
earlier years, test on later years) rather than a random shuffle, to avoid
look-ahead leakage -- see the book's chapter notebook contract.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass
class ForecastResult:
    model: LinearRegression
    mae: float
    rmse: float
    predictions: pd.DataFrame


def add_lag_features(
    panel: pd.DataFrame, value_col: str = "total_enrollment", lags: tuple[int, ...] = (1, 2, 3)
) -> pd.DataFrame:
    """Add lagged and rolling-mean enrollment features per institution,
    sorted by year, for use as forecasting inputs.
    """
    out = panel.sort_values(["unitid", "survey_year"]).copy()
    grouped = out.groupby("unitid")[value_col]
    for lag in lags:
        out[f"{value_col}_lag{lag}"] = grouped.shift(lag)
    out[f"{value_col}_rolling_mean3"] = grouped.shift(1).rolling(3).mean().reset_index(drop=True)
    return out


def train_test_split_by_year(
    panel: pd.DataFrame, split_year: int, year_col: str = "survey_year"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Temporal split: rows at/before ``split_year`` train the model, rows
    after it are held out for evaluation.
    """
    train = panel[panel[year_col] <= split_year]
    test = panel[panel[year_col] > split_year]
    return train, test


def forecast_enrollment(
    panel: pd.DataFrame,
    feature_cols: list[str],
    split_year: int,
    target_col: str = "total_enrollment",
) -> ForecastResult:
    train, test = train_test_split_by_year(panel, split_year)
    train = train.dropna(subset=feature_cols + [target_col])
    test = test.dropna(subset=feature_cols + [target_col])
    if train.empty or test.empty:
        raise ValueError(
            "Train or test split is empty after dropping missing values; "
            "check split_year and lag-feature availability."
        )

    model = LinearRegression()
    model.fit(train[feature_cols], train[target_col])

    preds = model.predict(test[feature_cols])
    mae = mean_absolute_error(test[target_col], preds)
    rmse = float(np.sqrt(mean_squared_error(test[target_col], preds)))

    result_df = test[["unitid", "survey_year", target_col]].copy()
    result_df["predicted"] = preds

    return ForecastResult(model=model, mae=mae, rmse=rmse, predictions=result_df)
