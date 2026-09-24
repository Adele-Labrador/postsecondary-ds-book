"""Offline tests for the NCES dashboard builder.

Each case below encodes a discrepancy found while reconciling the NCES build
against the Urban-portal build, so a regression would reintroduce a known,
user-visible data error.
"""

import io
import zipfile

import pandas as pd
import pytest

from src.ingest import build_dashboard_data_nces as nces


@pytest.mark.parametrize(
    "num, den, expected",
    [
        (205, 328, 0.63),  # 0.625 exactly: Python's round() gives 0.62
        (1, 8, 0.13),  # 0.125 exactly
        (5, 8, 0.63),
        (1, 3, 0.33),
        (2, 3, 0.67),
        (0, 40, 0.0),
        (40, 40, 1.0),
    ],
)
def test_round_half_up_matches_published_rates(num, den, expected):
    assert nces.round_half_up(num, den) == expected


def _gr(rows):
    return pd.DataFrame(rows, columns=["UNITID", "GRTYPE", "GRTOTLT"]).set_index("UNITID")


def test_grad_rates_include_two_year_colleges():
    # The portal build dropped these: 2-year institutions report under
    # GRTYPE 27/29/30, not the 4-year codes 1/2/3.
    gr = _gr([(10, 27, 500), (10, 29, 480), (10, 30, 192)])
    assert nces.grad_rates(gr) == {10: {"cohort": 500, "rate": 0.4}}


def test_grad_rates_four_year_uses_adjusted_cohort_denominator():
    # Revised cohort 1,000; 50 exclusions; 700 completers -> 700 / 950.
    gr = _gr([(20, 1, 1000), (20, 2, 950), (20, 3, 700)])
    assert nces.grad_rates(gr) == {20: {"cohort": 1000, "rate": 0.74}}


def test_grad_rates_keeps_larger_cohort_when_both_levels_reported():
    gr = _gr(
        [
            (30, 1, 100),
            (30, 2, 100),
            (30, 3, 60),
            (30, 27, 900),
            (30, 29, 880),
            (30, 30, 264),
        ]
    )
    assert nces.grad_rates(gr)[30] == {"cohort": 900, "rate": 0.3}


def test_grad_rates_skips_empty_adjusted_cohort():
    gr = _gr([(40, 1, 5), (40, 2, 0), (40, 3, 0)])
    assert nces.grad_rates(gr) == {}


def test_num_treats_negative_sentinels_as_missing_but_keeps_zero():
    # $0 is a real value (tuition-free institutions); the portal build's
    # `value or fallback` idiom silently dropped it.
    out = nces.num(pd.Series(["0", "-1", "-2", "", "12.5"]))
    assert out.iloc[0] == 0
    assert out.iloc[1:4].isna().all()
    assert out.iloc[4] == 12.5


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buf.getvalue()


def test_fetch_component_prefers_revised_file_and_strips_bom(tmp_path):
    (tmp_path / "ADM2022.zip").write_bytes(
        _zip_bytes(
            {
                "adm2022.csv": "\ufeffUNITID,ADMSSN\n1,2745\n",
                "adm2022_rv.csv": "\ufeffUNITID,ADMSSN\n1,2845\n",
            }
        )
    )
    frame = nces.fetch_component("ADM2022", raw_dir=tmp_path)
    assert frame.attrs["source_file"] == "adm2022_rv.csv"
    assert frame.loc[1, "ADMSSN"] == 2845


def test_fetch_component_uses_original_when_no_revision(tmp_path):
    (tmp_path / "HD2023.zip").write_bytes(_zip_bytes({"HD2023.csv": "unitid,INSTNM\n7,X\n"}))
    frame = nces.fetch_component("HD2023", raw_dir=tmp_path)
    assert frame.attrs["source_file"] == "HD2023.csv"
    assert list(frame.index) == [7]


def test_fetch_component_accepts_uppercase_rv_suffix(tmp_path):
    # NCES's 2026 re-publication names some revisions ``adm2023_RV.csv``.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("adm2023.csv", "UNITID,APPLCN\n1,10\n")
        zf.writestr("adm2023_RV.csv", "UNITID,APPLCN\n1,12\n")
    (tmp_path / "ADM2023.zip").write_bytes(buf.getvalue())
    frame = nces.fetch_component("ADM2023", raw_dir=tmp_path)
    assert frame.attrs["source_file"] == "adm2023_RV.csv"
    assert frame.loc[1, "APPLCN"] == 12


@pytest.mark.parametrize(
    "year, stem",
    [(2022, "IC2022_AY"), (2023, "IC2023_AY"), (2024, "COST1_2024"), (2025, "COST1_2025")],
)
def test_tuition_moves_to_cost_component_in_2024(year, stem):
    # IC{Y}_AY stops at 2023; 2024-25 tuition is only in the winter Cost file.
    assert nces.tuition_stem(year) == stem


@pytest.mark.parametrize(
    "stem, source, expected",
    [
        ("GR2024", "gr2024.csv", True),  # first release, no revision yet
        ("GR2023", "gr2023_RV.csv", False),
        ("EF2024D", "ef2024d.csv", True),
        ("EFIA2025", "efia2025.csv", True),
        ("COST1_2024", "cost1_2024.csv", True),
        ("SFA2223", "sfa2223_RV.csv", False),
        ("HD2024", "hd2024.csv", False),  # directory: never revised
        ("IC2023_AY", "ic2023_ay.csv", False),
    ],
)
def test_is_provisional(stem, source, expected):
    assert nces.is_provisional(stem, source) is expected


def test_download_falls_back_to_legacy_path(tmp_path, monkeypatch):
    # Only the legacy path has the file: the current path 404s.
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zf:
        zf.writestr("hd2013.csv", "UNITID,X\n1,2\n")
    tried = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        tried.append(request.full_url)
        if request.full_url.startswith(nces.NCES_BASE):
            raise nces.urllib.error.HTTPError(request.full_url, 404, "nf", {}, None)
        return Resp(payload.getvalue())

    monkeypatch.setattr(nces.urllib.request, "urlopen", fake_urlopen)
    frame = nces.fetch_component("HD2013", raw_dir=tmp_path)
    assert frame.loc[1, "X"] == 2
    assert [u.split("/ipeds/")[1].split("/")[0] for u in tried] == [
        "complete-data-files",
        "datacenter",
    ]


def test_download_reports_missing_when_neither_path_has_file(tmp_path, monkeypatch):
    def fake_urlopen(request, timeout):
        raise nces.urllib.error.HTTPError(request.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(nces.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(nces.MissingFile):
        nces.fetch_component("GR2099", raw_dir=tmp_path)


def test_refresh_keeps_cache_when_new_download_is_unusable(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hd2015.csv", "UNITID,X\n1,7\n")
    (tmp_path / "HD2015.zip").write_bytes(buf.getvalue())

    def fake_download(stem, zpath, retries):
        zpath.write_bytes(b"")  # NCES has returned empty bodies for old years

    monkeypatch.setattr(nces, "_download", fake_download)
    frame = nces.fetch_component("HD2015", raw_dir=tmp_path, refresh=True)
    assert frame.loc[1, "X"] == 7
    assert not (tmp_path / "HD2015.zip.part").exists()
