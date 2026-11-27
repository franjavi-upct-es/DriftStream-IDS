# tests/integration/test_notebooks_eda.py
"""The EDA notebooks run end to end on fixture-processed data (T2.7)."""

from __future__ import annotations

import runpy
import shutil
from pathlib import Path

import pytest

from driftstream.data.splits import WarmupSpec
from driftstream.etl.cicids2017 import run_cic_etl

pytestmark = pytest.mark.integration

NOTEBOOKS = Path(__file__).resolve().parents[2] / "notebooks"


def test_cic_notebook(
    cic_raw_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "cic"
    run_cic_etl(
        cic_raw_dir, data, warmup=WarmupSpec(days=("2017-07-03", "2017-07-04"))
    )
    monkeypatch.setenv("DRIFTSTREAM_CIC_DIR", str(data))
    monkeypatch.setenv("DRIFTSTREAM_EDA_OUT", str(tmp_path / "fig"))
    runpy.run_path(str(NOTEBOOKS / "01_eda_cicids2017.py"), run_name="__main__")
    produced = {p.name for p in (tmp_path / "fig").iterdir()}
    assert produced == {
        "cic_rate_share.png",
        "cic_family_timeline.png",
        "cic_feature_shift.png",
    }


@pytest.mark.skipif(shutil.which("java") is None, reason="PySpark needs Java")
def test_kyoto_notebook(
    kyoto_raw_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("pyspark")
    from driftstream.etl.spark_kyoto_etl import run_kyoto_etl  # noqa: PLC0415

    data = tmp_path / "kyoto"
    run_kyoto_etl(
        kyoto_raw_dir,
        data,
        start="2007-01",
        end="2007-03",
        warmup=WarmupSpec(first_days=30),
        master="local[2]",
    )
    monkeypatch.setenv("DRIFTSTREAM_KYOTO_DIR", str(data))
    monkeypatch.setenv("DRIFTSTREAM_EDA_OUT", str(tmp_path / "fig"))
    runpy.run_path(str(NOTEBOOKS / "02_eda_kyoto2006.py"), run_name="__main__")
    produced = {p.name for p in (tmp_path / "fig").iterdir()}
    assert produced == {
        "kyoto_rate_share.png",
        "kyoto_family_mix.png",
        "kyoto_feature_shift.png",
    }
