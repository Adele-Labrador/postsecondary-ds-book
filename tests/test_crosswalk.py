import pandas as pd
import pytest

from src.ingest import crosswalk as cw


def test_load_crosswalk_reads_required_columns(fixtures_dir):
    df = cw.load_crosswalk(fixtures_dir / "crosswalk.csv")
    assert {"unitid_from", "unitid_to", "effective_year"} <= set(df.columns)


def test_load_crosswalk_missing_columns_raises(tmp_path):
    bad_path = tmp_path / "bad_crosswalk.csv"
    bad_path.write_text("unitid_from,unitid_to\n1,2\n")
    with pytest.raises(ValueError):
        cw.load_crosswalk(bad_path)


def test_apply_crosswalk_remaps_pre_merger_history(crosswalk_df):
    panel = pd.DataFrame(
        {
            "unitid": [100005, 100005, 100001],
            "survey_year": [2018, 2019, 2020],
        }
    )

    remapped = cw.apply_crosswalk(panel, crosswalk_df)

    # Rows at/before the 2020 merger effective year should roll up to 100001.
    assert list(remapped["unitid"]) == [100001, 100001, 100001]


def test_apply_crosswalk_leaves_unaffected_ids_untouched(crosswalk_df):
    panel = pd.DataFrame({"unitid": [100099], "survey_year": [2022]})
    remapped = cw.apply_crosswalk(panel, crosswalk_df)
    assert remapped.loc[0, "unitid"] == 100099


def test_flag_closed_institutions(crosswalk_df):
    closed = cw.flag_closed_institutions(crosswalk_df)
    assert list(closed["unitid"]) == [100006]
    assert list(closed["closed_year"]) == [2019]
