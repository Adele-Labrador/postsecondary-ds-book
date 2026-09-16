import pandas as pd
import pytest

from src.features import ratios


@pytest.fixture
def ef_df():
    return pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "ft_students": [15000, 2500],
            "pt_students": [3000, 3500],
            "total_enrollment": [18000, 6000],
        }
    )


@pytest.fixture
def hr_df():
    return pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "fte_instructional_faculty": [900, 180],
        }
    )


def test_student_faculty_ratio(ef_df, hr_df):
    result = ratios.student_faculty_ratio(ef_df, hr_df)

    row1 = result[result["unitid"] == 1].iloc[0]
    expected_fte = 15000 + 3000 / 3
    assert row1["fte_students"] == pytest.approx(expected_fte)
    assert row1["student_faculty_ratio"] == pytest.approx(expected_fte / 900)


def test_student_faculty_ratio_missing_columns_raises(hr_df):
    bad_ef = pd.DataFrame({"unitid": [1], "survey_year": [2022]})
    with pytest.raises(ValueError):
        ratios.student_faculty_ratio(bad_ef, hr_df)


def test_aid_intensity_index():
    sfa = pd.DataFrame(
        {
            "unitid": [1],
            "survey_year": [2022],
            "pell_recipients": [4800],
            "total_undergrad": [16000],
            "total_grant_aid": [64_000_000],
            "aid_recipients": [12000],
        }
    )
    result = ratios.aid_intensity_index(sfa)
    row = result.iloc[0]
    assert row["pell_share"] == pytest.approx(0.3)
    assert row["avg_aid_per_recipient"] == pytest.approx(64_000_000 / 12000)


def test_admissions_selectivity():
    adm = pd.DataFrame(
        {
            "unitid": [1],
            "survey_year": [2022],
            "applicants": [20000],
            "admits": [8000],
            "enrolled": [2000],
        }
    )
    result = ratios.admissions_selectivity(adm)
    row = result.iloc[0]
    assert row["admit_rate"] == pytest.approx(0.4)
    assert row["yield_rate"] == pytest.approx(0.25)


def test_financial_health_ratios(ef_df):
    fin = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "total_revenue": [500_000_000, 60_000_000],
            "tuition_revenue": [200_000_000, 40_000_000],
            "govt_appropriations": [150_000_000, 5_000_000],
            "total_expenses": [480_000_000, 58_000_000],
        }
    )
    result = ratios.financial_health_ratios(fin, ef_df)
    row1 = result[result["unitid"] == 1].iloc[0]
    assert row1["tuition_dependence"] == pytest.approx(0.4)
    assert row1["appropriation_share"] == pytest.approx(0.3)
    assert row1["expense_per_student"] == pytest.approx(480_000_000 / 18000)


def test_completion_rate():
    gr = pd.DataFrame(
        {
            "unitid": [1],
            "survey_year": [2022],
            "cohort_size": [4000],
            "completers_150pct": [2600],
        }
    )
    result = ratios.completion_rate(gr)
    assert result.iloc[0]["completion_rate_150pct"] == pytest.approx(0.65)


def test_equity_completion_gap():
    om = pd.DataFrame(
        {
            "unitid": [1],
            "survey_year": [2022],
            "pell_completers_share": [0.55],
            "non_pell_completers_share": [0.70],
        }
    )
    result = ratios.equity_completion_gap(om)
    assert result.iloc[0]["equity_completion_gap"] == pytest.approx(0.15)
