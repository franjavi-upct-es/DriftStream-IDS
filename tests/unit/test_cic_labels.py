# tests/unit/test_cic_labels.py
"""CIC-IDS2017 label mapping: canonical families, Attempted, aliases."""

from __future__ import annotations

import pytest

from driftstream.core.errors import UnknownLabelError
from driftstream.etl.cicids2017 import EXPECTED_DAY, FAMILIES, map_label

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "family", "attempted"),
    [
        ("BENIGN", "BENIGN", False),
        ("DoS Hulk", "DoS Hulk", False),
        ("DoS Slowhttptest - Attempted", "DoS Slowhttptest", True),
        ("Web Attack - XSS - Attempted", "Web Attack - XSS", True),
        ("Infiltration - Portscan", "Infiltration - Portscan", False),
        ("Infiltration - Attempted", "Infiltration", True),
        ("Botnet - Attempted", "Botnet", True),
        # spellings of the original CIC and WTMC 2021 releases
        ("Bot", "Botnet", False),
        ("PortScan", "Portscan", False),
        ("DoS SlowHttpTest", "DoS Slowhttptest", False),
        (
            "Web Attack \N{EN DASH} Brute Force",
            "Web Attack - Brute Force",
            False,
        ),
        ("  DDoS ", "DDoS", False),
    ],
)
def test_map_label(raw: str, family: str, attempted: bool) -> None:
    assert map_label(raw) == (family, attempted)


@pytest.mark.parametrize("raw", ["Ransomware", "", "BENIGN - Attempted"])
def test_unknown_labels_fail_loudly(raw: str) -> None:
    with pytest.raises(UnknownLabelError):
        map_label(raw)


def test_every_attack_family_has_an_expected_day() -> None:
    assert set(FAMILIES) - {"BENIGN"} == set(EXPECTED_DAY)
