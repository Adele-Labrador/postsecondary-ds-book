"""Engineered ratio/rate features built from standardized IPEDS component
tables (as produced by ``src.ingest.ipeds_complete_files.load_component``).

Every function here is a pure transform: DataFrame(s) in, DataFrame out, no
I/O -- which is what makes them unit-testable with small synthetic fixtures
instead of a full IPEDS download.
"""

from __future__ import annotations

import pandas as pd


def student_faculty_ratio(ef: pd.DataFrame, hr: pd.DataFrame) -> pd.DataFrame:
    """Student-to-faculty ratio, following IPEDS convention:

        FTE students = full-time students + (1/3 * part-time students)
        ratio = FTE students / FTE instructional faculty

    ``ef`` must provide ``ft_students`` and ``pt_students``; ``hr`` must
    provide ``fte_instructional_faculty``. Both must include ``unitid`` and
    ``survey_year``.
    """
    required_ef = {"unitid", "survey_year", "ft_students", "pt_students"}
    required_hr = {"unitid", "survey_year", "fte_instructional_faculty"}
    _require_columns(ef, required_ef, "ef")
    _require_columns(hr, required_hr, "hr")

    merged = ef.merge(hr, on=["unitid", "survey_year"], how="inner")
    merged["fte_students"] = merged["ft_students"] + merged["pt_students"] / 3
    merged["student_faculty_ratio"] = merged["fte_students"] / merged["fte_instructional_faculty"]
    return merged[["unitid", "survey_year", "fte_students", "student_faculty_ratio"]]


def aid_intensity_index(sfa: pd.DataFrame) -> pd.DataFrame:
    """Pell share and average grant aid per recipient, from the Student
    Financial Aid (SFA) component.
    """
    required = {
        "unitid",
        "survey_year",
        "pell_recipients",
        "total_undergrad",
        "total_grant_aid",
        "aid_recipients",
    }
    _require_columns(sfa, required, "sfa")

    out = sfa.copy()
    out["pell_share"] = out["pell_recipients"] / out["total_undergrad"]
    out["avg_aid_per_recipient"] = out["total_grant_aid"] / out["aid_recipients"]
    return out[["unitid", "survey_year", "pell_share", "avg_aid_per_recipient"]]


def admissions_selectivity(adm: pd.DataFrame) -> pd.DataFrame:
    """Admit rate and yield rate from the Admissions (ADM) component."""
    required = {"unitid", "survey_year", "applicants", "admits", "enrolled"}
    _require_columns(adm, required, "adm")

    out = adm.copy()
    out["admit_rate"] = out["admits"] / out["applicants"]
    out["yield_rate"] = out["enrolled"] / out["admits"]
    return out[["unitid", "survey_year", "admit_rate", "yield_rate"]]


def financial_health_ratios(fin: pd.DataFrame, ef: pd.DataFrame) -> pd.DataFrame:
    """Revenue diversification and expense-per-FTE-student from the Finance
    (F) component, normalized by enrollment.
    """
    required_fin = {
        "unitid",
        "survey_year",
        "total_revenue",
        "tuition_revenue",
        "govt_appropriations",
        "total_expenses",
    }
    required_ef = {"unitid", "survey_year", "total_enrollment"}
    _require_columns(fin, required_fin, "fin")
    _require_columns(ef, required_ef, "ef")

    merged = fin.merge(ef, on=["unitid", "survey_year"], how="inner")
    merged["tuition_dependence"] = merged["tuition_revenue"] / merged["total_revenue"]
    merged["appropriation_share"] = merged["govt_appropriations"] / merged["total_revenue"]
    merged["expense_per_student"] = merged["total_expenses"] / merged["total_enrollment"]
    return merged[
        [
            "unitid",
            "survey_year",
            "tuition_dependence",
            "appropriation_share",
            "expense_per_student",
        ]
    ]


def completion_rate(gr: pd.DataFrame) -> pd.DataFrame:
    """150%-time completion rate from the Graduation Rates (GR) component."""
    required = {"unitid", "survey_year", "cohort_size", "completers_150pct"}
    _require_columns(gr, required, "gr")

    out = gr.copy()
    out["completion_rate_150pct"] = out["completers_150pct"] / out["cohort_size"]
    return out[["unitid", "survey_year", "completion_rate_150pct"]]


def equity_completion_gap(om: pd.DataFrame) -> pd.DataFrame:
    """Pell vs. non-Pell completion gap from the Outcome Measures (OM)
    component. A positive gap means non-Pell students complete at a higher
    rate than Pell recipients.
    """
    required = {"unitid", "survey_year", "pell_completers_share", "non_pell_completers_share"}
    _require_columns(om, required, "om")

    out = om.copy()
    out["equity_completion_gap"] = out["non_pell_completers_share"] - out["pell_completers_share"]
    return out[["unitid", "survey_year", "equity_completion_gap"]]


def _require_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"'{name}' is missing required columns: {sorted(missing)}")
