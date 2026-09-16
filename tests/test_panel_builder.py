import pandas as pd

from src.features import panel_builder


def test_build_panel_merges_optional_tables():
    ic = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "institution_name": ["Alpha", "Beta"],
        }
    )
    student_faculty = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "student_faculty_ratio": [18.0, 16.0],
        }
    )
    aid = pd.DataFrame(
        {
            "unitid": [1],
            "survey_year": [2022],
            "pell_share": [0.3],
        }
    )

    panel = panel_builder.build_panel(ic, student_faculty=student_faculty, aid_intensity=aid)

    assert len(panel) == 2
    assert "student_faculty_ratio" in panel.columns
    assert "pell_share" in panel.columns
    # Institution 2 has no aid row -> pell_share should be missing, not dropped.
    row2 = panel[panel["unitid"] == 2].iloc[0]
    assert pd.isna(row2["pell_share"])


def test_build_panel_with_no_optional_tables_returns_base():
    ic = pd.DataFrame({"unitid": [1], "survey_year": [2022]})
    panel = panel_builder.build_panel(ic)
    pd.testing.assert_frame_equal(panel, ic)


def test_save_and_load_panel_roundtrip(tmp_path):
    ic = pd.DataFrame(
        {
            "unitid": [1, 2],
            "survey_year": [2022, 2022],
            "institution_name": ["Alpha", "Beta"],
        }
    )
    panel = panel_builder.build_panel(ic)
    out_path = panel_builder.save_panel(panel, path=tmp_path / "panel.parquet")

    assert out_path.exists()
    reloaded = panel_builder.load_panel(out_path)
    pd.testing.assert_frame_equal(reloaded, panel)
