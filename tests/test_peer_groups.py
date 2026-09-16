import pandas as pd
import pytest

from src.features import peer_groups


def test_attach_carnegie_classification(carnegie_df):
    institutions = pd.DataFrame(
        {
            "unitid": [100001, 100002, 999999],
            "survey_year": [2022, 2022, 2022],
        }
    )
    merged = peer_groups.attach_carnegie_classification(institutions, carnegie_df)

    assert "carnegie_basic" in merged.columns
    row = merged[merged["unitid"] == 100001].iloc[0]
    assert row["carnegie_basic"] == "Doctoral Universities: High Research Activity"
    # Unknown institution should get a null classification rather than error.
    unknown_row = merged[merged["unitid"] == 999999].iloc[0]
    assert pd.isna(unknown_row["carnegie_basic"])


def test_attach_carnegie_classification_missing_columns_raises():
    institutions = pd.DataFrame({"unitid": [1]})
    bad_carnegie = pd.DataFrame({"unitid": [1]})
    with pytest.raises(ValueError):
        peer_groups.attach_carnegie_classification(institutions, bad_carnegie)


@pytest.fixture
def panel_with_groups():
    return pd.DataFrame(
        {
            "unitid": [1, 2, 3, 4],
            "survey_year": [2022, 2022, 2022, 2022],
            "carnegie_basic": ["Doctoral", "Doctoral", "Doctoral", "Baccalaureate"],
            "control": [1, 1, 1, 1],
            "level": [1, 1, 1, 1],
            "total_enrollment": [18000, 17000, 30000, 2000],
        }
    )


def test_build_peer_group_filters_on_group_and_size(panel_with_groups):
    peers = peer_groups.build_peer_group(panel_with_groups, target_unitid=1, year=2022)
    # unitid 2 is within +/-25% of 18000 and shares group cols; unitid 3 (30000)
    # is out of size tolerance; unitid 4 is a different carnegie_basic.
    assert set(peers["unitid"]) == {2}


def test_build_peer_group_unknown_institution_raises(panel_with_groups):
    with pytest.raises(ValueError):
        peer_groups.build_peer_group(panel_with_groups, target_unitid=999, year=2022)
