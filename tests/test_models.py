import numpy as np
import pandas as pd
import pytest

from src.models import (
    classify_institution_type,
    cluster_segments,
    forecast_enrollment,
    forecast_graduation_rate,
)


@pytest.fixture
def synthetic_panel():
    """A small but multi-institution, multi-year synthetic panel -- enough
    rows for a train/test split, but fast to run in CI.
    """
    rng = np.random.default_rng(42)
    n_institutions = 40
    years = range(2016, 2023)

    rows = []
    carnegie_labels = rng.choice(
        ["Doctoral", "Baccalaureate", "Associates"],
        size=n_institutions,
        p=[0.3, 0.4, 0.3],
    )
    base_enrollment = rng.integers(1000, 20000, size=n_institutions)
    base_faculty_ratio = rng.uniform(10, 25, size=n_institutions)
    base_completion = rng.uniform(0.3, 0.8, size=n_institutions)

    for i in range(n_institutions):
        for y_idx, year in enumerate(years):
            rows.append(
                {
                    "unitid": 200000 + i,
                    "survey_year": year,
                    "carnegie_basic": carnegie_labels[i],
                    "total_enrollment": base_enrollment[i] * (1 + 0.01 * y_idx) + rng.normal(0, 50),
                    "student_faculty_ratio": base_faculty_ratio[i] + rng.normal(0, 0.5),
                    "completion_rate_150pct": np.clip(
                        base_completion[i] + rng.normal(0, 0.02), 0, 1
                    ),
                    "pell_share": rng.uniform(0.1, 0.6),
                }
            )
    return pd.DataFrame(rows)


def test_train_institution_classifier(synthetic_panel):
    result = classify_institution_type.train_institution_classifier(
        synthetic_panel,
        feature_cols=["total_enrollment", "student_faculty_ratio", "pell_share"],
        target_col="carnegie_basic",
    )
    assert 0.0 <= result.accuracy <= 1.0
    assert isinstance(result.report, str) and len(result.report) > 0


def test_add_lag_features_and_forecast_enrollment(synthetic_panel):
    with_lags = forecast_enrollment.add_lag_features(synthetic_panel)
    assert "total_enrollment_lag1" in with_lags.columns

    result = forecast_enrollment.forecast_enrollment(
        with_lags,
        feature_cols=["total_enrollment_lag1", "total_enrollment_lag2"],
        split_year=2020,
    )
    assert result.mae >= 0
    assert result.rmse >= 0
    assert not result.predictions.empty


def test_forecast_enrollment_empty_split_raises(synthetic_panel):
    with pytest.raises(ValueError):
        forecast_enrollment.forecast_enrollment(
            synthetic_panel, feature_cols=["total_enrollment"], split_year=1900
        )


def test_forecast_graduation_rate(synthetic_panel):
    result = forecast_graduation_rate.forecast_graduation_rate(
        synthetic_panel,
        feature_cols=["total_enrollment", "student_faculty_ratio", "pell_share"],
    )
    assert result.mae >= 0
    assert not result.predictions.empty


def test_flag_equity_risk():
    panel = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "equity_completion_gap": [0.15, 0.02],
        }
    )
    flagged = forecast_graduation_rate.flag_equity_risk(panel)
    assert list(flagged["equity_risk_flag"]) == [True, False]


def test_cluster_institutions(synthetic_panel):
    result = cluster_segments.cluster_institutions(
        synthetic_panel,
        feature_cols=["total_enrollment", "student_faculty_ratio", "completion_rate_150pct"],
        n_clusters=3,
    )
    assert result.assignments["cluster"].nunique() <= 3

    profile = cluster_segments.cluster_profile(
        result,
        synthetic_panel,
        feature_cols=["total_enrollment", "student_faculty_ratio", "completion_rate_150pct"],
    )
    assert len(profile) <= 3
