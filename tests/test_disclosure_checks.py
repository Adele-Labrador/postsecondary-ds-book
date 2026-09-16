import pandas as pd
import pytest

from src.validation import disclosure_checks as dc


@pytest.fixture
def cell_df():
    return pd.DataFrame(
        {
            "unitid": [1, 2, 3],
            "subgroup": ["pell", "pell", "pell"],
            "n_completers": [25, 8, 12],
            "completion_rate": [0.5, 0.6, 0.55],
        }
    )


def test_flag_small_cells(cell_df):
    flagged = dc.flag_small_cells(cell_df, count_col="n_completers", min_n=10)
    assert list(flagged["suppress"]) == [False, True, False]


def test_apply_suppression_masks_values(cell_df):
    masked = dc.apply_suppression(
        cell_df, count_col="n_completers", value_cols=["completion_rate"], min_n=10
    )
    row2 = masked[masked["unitid"] == 2].iloc[0]
    assert pd.isna(row2["completion_rate"])
    row1 = masked[masked["unitid"] == 1].iloc[0]
    assert row1["completion_rate"] == 0.5


def test_suppression_rate(cell_df):
    rate = dc.suppression_rate(cell_df, count_col="n_completers", min_n=10)
    assert rate == pytest.approx(1 / 3)
