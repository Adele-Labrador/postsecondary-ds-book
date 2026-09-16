from src.ingest import ipeds_api_client as api


def test_parse_payload_standardizes_columns():
    payload = {
        "results": [
            {
                "unitid": 100001,
                "inst_name": "Alpha State University",
                "sector": 1,
                "control": 1,
                "level": 1,
                "state_abbr": "CO",
            },
            {
                "unitid": 100002,
                "inst_name": "Beta Community College",
                "sector": 4,
                "control": 1,
                "level": 2,
                "state_abbr": "CO",
            },
        ]
    }

    df = api.parse_payload("institutional_characteristics", 2022, payload)

    assert list(df["unitid"]) == [100001, 100002]
    assert "institution_name" in df.columns
    assert (df["survey_year"] == 2022).all()


def test_parse_payload_without_results_wrapper():
    payload = [{"unitid": 100003, "state_abbr": "CO"}]
    df = api.parse_payload("fall_enrollment", 2021, payload)
    assert df.loc[0, "unitid"] == 100003
    assert df.loc[0, "survey_year"] == 2021


def test_fetch_endpoint_unknown_component_raises():
    import pytest

    with pytest.raises(KeyError):
        api.fetch_endpoint("not_a_real_component", 2022)
