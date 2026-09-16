import pandas as pd
import pytest

from src.validation import benchmark_checks as bc


def test_compare_to_published_flags_within_tolerance():
    model_df = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "completion_rate_150pct": [0.651, 0.40],
        }
    )
    published_df = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "completion_rate_150pct": [0.65, 0.30],
        }
    )

    comparison = bc.compare_to_published(
        model_df, published_df, value_col="completion_rate_150pct", tolerance=0.02
    )

    row1 = comparison[comparison["unitid"] == 1].iloc[0]
    row2 = comparison[comparison["unitid"] == 2].iloc[0]
    assert row1["within_tolerance"]
    assert not row2["within_tolerance"]


def test_classification_agreement():
    predicted = pd.Series(["Doctoral", "Baccalaureate", "Doctoral"])
    truth = pd.Series(["Doctoral", "Doctoral", "Doctoral"])
    agreement = bc.classification_agreement(predicted, truth)
    assert agreement == pytest.approx(2 / 3)


def test_classification_agreement_length_mismatch_raises():
    with pytest.raises(ValueError):
        bc.classification_agreement(pd.Series([1, 2]), pd.Series([1]))


def test_summarize_benchmark():
    comparison = pd.DataFrame(
        {
            "abs_diff": [0.01, 0.03],
            "within_tolerance": [True, False],
        }
    )
    summary = bc.summarize_benchmark(comparison)
    assert summary["n_compared"] == 2
    assert summary["mean_abs_diff"] == pytest.approx(0.02)
    assert summary["pct_within_tolerance"] == pytest.approx(0.5)
