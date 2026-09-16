import pytest

from src.ingest import ipeds_complete_files as icf


def test_load_component_institutional_characteristics(ic_raw_path):
    df = icf.load_component("institutional_characteristics", 2022, path=ic_raw_path)

    assert set(
        ["unitid", "survey_year", "institution_name", "control", "level", "sector", "state"]
    ) <= set(df.columns)
    assert (df["survey_year"] == 2022).all()
    assert df["unitid"].dtype.kind in "iu"
    assert len(df) == 4


def test_load_component_fall_enrollment(ef_raw_path):
    df = icf.load_component("fall_enrollment", 2022, path=ef_raw_path)

    assert "total_enrollment" in df.columns
    assert "ft_students" in df.columns
    assert "pt_students" in df.columns
    row = df[df["unitid"] == 100001].iloc[0]
    assert row["total_enrollment"] == 18000


def test_load_component_human_resources(hr_raw_path):
    df = icf.load_component("human_resources", 2022, path=hr_raw_path)
    assert "fte_instructional_faculty" in df.columns
    assert "total_staff" in df.columns


def test_load_component_student_financial_aid(sfa_raw_path):
    df = icf.load_component("student_financial_aid", 2022, path=sfa_raw_path)
    assert "total_undergrad" in df.columns
    assert "pell_recipients" in df.columns


def test_load_component_unknown_raises():
    with pytest.raises(KeyError):
        icf.load_component("not_a_real_component", 2022, path="doesnt-matter.csv")


def test_raw_file_path_uses_prefix():
    path = icf.raw_file_path("fall_enrollment", 2022, raw_dir="data/raw")
    assert path.name == "EF2022.csv"
    assert path.parent.name == "fall_enrollment"
