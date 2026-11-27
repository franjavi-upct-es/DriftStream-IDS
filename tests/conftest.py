# tests/conftest.py
"""Shared pytest fixtures for the DriftStream-IDS test suite.

The raw-data fixtures (ROADMAP T2.6) are generated here, deterministically,
instead of being committed as files. They reproduce the real formats:

* CIC-IDS2017 improved (CNS 2022): one CSV per weekday, ``id`` column,
  identifiers, UTC timestamps with microseconds (unsorted), ``Infinity``
  and empty values, exact duplicates within one second, ``"<attack> -
  Attempted"`` labels and the ``Attempted Category`` column;
* Kyoto 2006+ (new_data201704): tab-separated ``YYYYMMDD.txt`` day files
  with the 24 documented columns, a missing day, an invalid label and an
  unparsable start time.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# CIC-IDS2017 improved fixture
# --------------------------------------------------------------------------
CIC_COLUMNS = [
    "id",
    "Flow ID",
    "Src IP",
    "Src Port",
    "Dst IP",
    "Dst Port",
    "Protocol",
    "Timestamp",
    "Flow Duration",
    "Total Fwd Packet",
    "Total Bwd packets",
    "Total Length of Fwd Packet",
    "Total Length of Bwd Packet",
    "Flow Bytes/s",
    "Flow Packets/s",
    "Down/Up Ratio",
    "FWD Init Win Bytes",
    "Label",
    "Attempted Category",
]
#: weekday → (UTC date, {label: count}).
CIC_DAYS: dict[str, tuple[str, dict[str, int]]] = {
    "monday": ("2017-07-03", {"BENIGN": 300}),
    "tuesday": (
        "2017-07-04",
        {
            "BENIGN": 250,
            "FTP-Patator": 30,
            "SSH-Patator": 20,
            "FTP-Patator - Attempted": 3,
        },
    ),
    "wednesday": (
        "2017-07-05",
        {
            "BENIGN": 200,
            "DoS Hulk": 80,
            "DoS GoldenEye": 20,
            "DoS Slowloris": 15,
            "DoS Slowhttptest - Attempted": 5,
            "Heartbleed": 2,
        },
    ),
    "thursday": (
        "2017-07-06",
        {
            "BENIGN": 200,
            "Infiltration - Portscan": 60,
            "Web Attack - Brute Force": 5,
            "Web Attack - XSS - Attempted": 4,
        },
    ),
    "friday": (
        "2017-07-07",
        {
            "BENIGN": 200,
            "Portscan": 70,
            "DDoS": 60,
            "Botnet": 5,
            "Botnet - Attempted": 6,
        },
    ),
}
#: Duplicate rows added per day (same features, label and second).
CIC_DUPLICATES_PER_DAY = 2


def _cic_row(
    rng: np.random.Generator, day: str, label: str, idx: int
) -> list[object]:
    attack = label != "BENIGN"
    attempted = label.endswith(" - Attempted")
    hour = int(rng.integers(12, 20))  # 12:00-19:59 UTC (working hours)
    ts = (
        f"{day} {hour:02d}:{int(rng.integers(0, 60)):02d}:"
        f"{int(rng.integers(0, 60)):02d}.{int(rng.integers(0, 10**6)):06d}"
    )
    scale = 5.0 if attack else 1.0
    dur = float(rng.exponential(1e5 * scale))
    fwd = int(rng.integers(1, 20))
    bwd = int(rng.integers(0, 20))
    flow_bytes: object = round(float(rng.exponential(1e3 * scale)), 3)
    if idx % 97 == 5:
        flow_bytes = "Infinity"  # CICFlowMeter artefact
    if idx % 89 == 7:
        flow_bytes = ""  # missing value
    return [
        idx,
        f"10.0.0.{idx % 250}-192.168.10.{idx % 50}-{40000 + idx}-80-6",
        f"10.0.0.{idx % 250}",
        40000 + idx,
        f"192.168.10.{idx % 50}",
        int(rng.choice([80, 443, 21, 22])),
        int(rng.choice([6, 17])),
        ts,
        round(dur, 1),
        fwd,
        bwd,
        fwd * int(rng.integers(0, 1500)),
        bwd * int(rng.integers(0, 1500)),
        flow_bytes,
        round(float(rng.exponential(10 * scale)), 3),
        round(bwd / max(fwd, 1), 3),
        int(rng.integers(0, 65535)),
        label,
        int(rng.integers(0, 4)) if attempted else -1,
    ]


def write_cic_fixture(root: Path, seed: int = 0) -> Path:
    """Write the five weekday CSVs (nested like the extracted archive)."""
    rng = np.random.default_rng(seed)
    out = root / "CICIDS2017_improved"
    out.mkdir(parents=True, exist_ok=True)
    idx = 0
    for weekday, (day, labels) in CIC_DAYS.items():
        rows = []
        for label, count in labels.items():
            for _ in range(count):
                rows.append(_cic_row(rng, day, label, idx))
                idx += 1
        rows += [list(r) for r in rows[:CIC_DUPLICATES_PER_DAY]]
        order = rng.permutation(len(rows))  # raw files are not time-sorted
        with (out / f"{weekday}.csv").open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(CIC_COLUMNS)
            writer.writerows(rows[i] for i in order)
    return root


# --------------------------------------------------------------------------
# Kyoto 2006+ fixture
# --------------------------------------------------------------------------
KYOTO_DAYS = [
    f"2007{m:02d}{d:02d}"
    for m in (1, 2, 3)
    for d in (1, 2, 3, 4, 5)
    if (m, d) != (2, 3)  # one missing day
]
KYOTO_ROWS_PER_DAY = 40


def _kyoto_row(rng: np.random.Generator, label: str) -> list[str]:
    attack = label != "1"
    h, mi, s = (int(rng.integers(0, b)) for b in (24, 60, 60))
    return [
        f"{rng.exponential(3.0 if attack else 1.0):.6f}",
        str(rng.choice(["http", "smtp", "dns", "other"])),
        str(int(rng.integers(0, 5000))),
        str(int(rng.integers(0, 5000))),
        str(int(rng.integers(0, 100))),
        f"{rng.uniform():.2f}",
        f"{rng.uniform() * (0.8 if attack else 0.1):.2f}",
        f"{rng.uniform() * 0.1:.2f}",
        str(int(rng.integers(0, 100))),
        str(int(rng.integers(0, 100))),
        f"{rng.uniform():.2f}",
        f"{rng.uniform() * 0.1:.2f}",
        f"{rng.uniform() * 0.1:.2f}",
        str(rng.choice(["SF", "S0", "REJ", "RSTO"])),
        "0" if not attack else f"{int(rng.integers(1, 9))}(1)",
        "0",
        "0",
        label,
        f"fd00::{int(rng.integers(1, 999)):x}",
        str(int(rng.integers(1024, 65535))),
        f"fd00::1:{int(rng.integers(1, 999)):x}",
        str(int(rng.choice([25, 53, 80, 445]))),
        f"{h:02d}:{mi:02d}:{s:02d}",
        str(rng.choice(["tcp", "udp", "icmp"])),
    ]


def write_kyoto_fixture(root: Path, seed: int = 0) -> Path:
    """Write tab-separated day files under ``YYYY/MM/``."""
    rng = np.random.default_rng(seed)
    for day in KYOTO_DAYS:
        folder = root / day[:4] / day[4:6]
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for i in range(KYOTO_ROWS_PER_DAY):
            label = "1" if i % 4 else ("-1" if i % 8 else "-2")
            rows.append(_kyoto_row(rng, label))
        if day == "20070102":
            rows[0][17] = "9"  # invalid label
            rows[1][22] = "xx:yy:zz"  # unparsable start time
        (folder / f"{day}.txt").write_text(
            "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8"
        )
    return root


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path of the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def config_dir(repo_root: Path) -> Path:
    """Absolute path of the Hydra config tree."""
    return repo_root / "configs"


@pytest.fixture(scope="session")
def cic_raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Directory with the CIC-IDS2017 improved fixture CSVs."""
    return write_cic_fixture(tmp_path_factory.mktemp("cic_raw"))


@pytest.fixture(scope="session")
def kyoto_raw_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Directory with the Kyoto 2006+ fixture day files."""
    return write_kyoto_fixture(tmp_path_factory.mktemp("kyoto_raw"))
