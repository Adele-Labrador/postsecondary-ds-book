"""Pin Carnegie 2021 basic codes to institutions whose category is unambiguous.

The 2021 edition inserted "Research Institutions" at code 27, so a table copied
from the 2018 edition is silently off by one from 27 through 33. Every code in
that range is checked here against the NCES HD2023 assignments.
"""

import pytest

from src.ingest.build_dashboard_data import CC_BASIC_2021


@pytest.mark.parametrize(
    "code, fragment, family, example",
    [
        (24, "Faith-Related", "Special Focus", "Aquinas Institute of Theology"),
        (25, "Medical Schools", "Special Focus", "Albany Medical College"),
        (26, "Other Health Professions", "Special Focus", "A T Still University"),
        (27, "Research Institutions", "Special Focus", "The Rockefeller University"),
        (28, "Engineering", "Special Focus", "Franklin W Olin College of Engineering"),
        (29, "Business & Management", "Special Focus", "Babson College"),
        (30, "Arts, Music & Design", "Special Focus", "The Juilliard School"),
        (31, "Law Schools", "Special Focus", "Brooklyn Law School"),
        (32, "Other Special Focus", "Special Focus", "Bank Street College of Education"),
        (33, "Tribal Colleges", "Tribal", "Navajo Technical University"),
    ],
)
def test_special_focus_and_tribal_codes(code, fragment, family, example):
    label, fam = CC_BASIC_2021[code]
    assert fragment in label, f"code {code} ({example}) mapped to {label!r}"
    assert fam == family


def test_table_covers_every_published_code():
    assert sorted(CC_BASIC_2021) == list(range(1, 34))
