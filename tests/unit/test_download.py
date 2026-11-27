# tests/unit/test_download.py
"""Downloads, checksums (trust on first use) and safe extraction."""

from __future__ import annotations

import re
import stat
import zipfile
from pathlib import Path

import pytest

from driftstream.core.errors import ChecksumMismatchError, UnsafeArchiveError
from driftstream.data.download import (
    CIC_URL,
    KYOTO_KAGGLE_VERSION,
    KYOTO_URL,
    Checksums,
    RawFile,
    cic_files,
    fetch,
    kyoto_files,
    months,
    safe_extract,
    sha256_file,
    sync,
)
from driftstream.etl.spark_kyoto_etl import discover_day_files

pytestmark = pytest.mark.unit


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_months_and_kyoto_urls() -> None:
    assert list(months("2007-11", "2008-02")) == [
        (2007, 11),
        (2007, 12),
        (2008, 1),
        (2008, 2),
    ]
    with pytest.raises(ValueError, match="after"):
        list(months("2009-01", "2008-01"))


def test_kyoto_source_is_the_pinned_kaggle_archive() -> None:
    (rf,) = kyoto_files("2007-01", "2009-12")
    assert rf.url == KYOTO_URL
    assert rf.url.startswith("https://www.kaggle.com/api/v1/datasets/download/")
    assert rf.url.endswith(f"?datasetVersionNumber={KYOTO_KAGGLE_VERSION}")
    assert rf.target == Path(
        f"raw/kyoto2006/_zips/kyoto-2006-kaggle-v{KYOTO_KAGGLE_VERSION}.zip"
    )
    assert rf.extract_to == Path("raw/kyoto2006")
    # A wider window keeps the archive (no new download).
    (wide,) = kyoto_files("2006-11", "2015-12")
    assert wide.target == rf.target


@pytest.mark.parametrize(
    ("name", "selected"),
    [
        ("2007/Kyoto2016/2007/01/20070101.txt", True),
        ("2009/Kyoto2016/2009/12/20091231.txt", True),
        ("2006/Kyoto2016/2006/12/20061231.txt", False),
        ("2011/Kyoto2016/2011/01/20110101.txt", False),
        ("2007/Kyoto2016/2007/01/20070101.txt.bak", False),
        ("2007/Kyoto2016/2007/01/x20070101.txt", False),
        ("20070315.txt", True),
    ],
)
def test_kyoto_members_select_the_window(name: str, selected: bool) -> None:
    (rf,) = kyoto_files("2007-01", "2009-12")
    assert rf.members is not None
    assert bool(re.search(rf.members, name)) is selected


def test_cic_source_is_the_cns2022_release() -> None:
    (rf,) = cic_files()
    assert rf.url == CIC_URL
    assert "CNS2022" in rf.url and rf.url.endswith("CICIDS2017_improved.zip")


def test_fetch_from_file_url_is_atomic(tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 3_000_000)
    dest = tmp_path / "out" / "file.bin"
    assert fetch(src.as_uri(), dest) == 3_000_000
    assert dest.read_bytes() == src.read_bytes()
    assert not dest.with_name("file.bin.part").exists()


def test_fetch_restarts_when_range_is_ignored(tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"abcdef")
    dest = tmp_path / "file.bin"
    dest.with_name("file.bin.part").write_bytes(b"zz")  # stale partial
    fetch(src.as_uri(), dest)
    assert dest.read_bytes() == b"abcdef"


def test_checksums_record_verify_and_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "CHECKSUMS.raw"
    path.write_text("# header\n")
    sums = Checksums(path)
    assert sums.check("raw/a.zip", "aa", strict=False) == "recorded"
    sums.save()
    reloaded = Checksums(path)
    assert reloaded.header == ["# header"]
    assert reloaded.check("raw/a.zip", "aa", strict=True) == "verified"
    with pytest.raises(ChecksumMismatchError, match="expected"):
        reloaded.check("raw/a.zip", "bb", strict=False)
    with pytest.raises(ChecksumMismatchError, match="no recorded"):
        reloaded.check("raw/new.zip", "cc", strict=True)


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    bad = _zip(tmp_path / "bad.zip", {"../escape.txt": b"x"})
    with pytest.raises(UnsafeArchiveError, match="escapes"):
        safe_extract(bad, tmp_path / "dest")
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_rejects_symlinks(tmp_path: Path) -> None:
    path = tmp_path / "link.zip"
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(UnsafeArchiveError, match="symlink"):
        safe_extract(path, tmp_path / "dest")


def test_sync_downloads_once_and_extracts(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "200701.zip", {"20070101.txt": b"row\n"})
    data_root = tmp_path / "data"
    rf = RawFile(
        archive.as_uri(),
        Path("raw/kyoto2006/_zips/200701.zip"),
        Path("raw/kyoto2006/2007/01"),
    )
    sums = Checksums(data_root / "CHECKSUMS.raw")
    data_root.mkdir()
    (first,) = sync([rf], data_root, sums)
    assert (first.status, first.downloaded, first.extracted) == (
        "recorded",
        True,
        1,
    )
    assert (data_root / "raw/kyoto2006/2007/01/20070101.txt").is_file()
    (second,) = sync([rf], data_root, Checksums(data_root / "CHECKSUMS.raw"))
    assert (second.status, second.downloaded) == ("verified", False)
    recorded = (data_root / "CHECKSUMS.raw").read_text()
    assert sha256_file(archive) in recorded


def test_safe_extract_filters_members_but_checks_all(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "a.zip", {"keep/1.txt": b"1", "drop/2.txt": b"2"})
    written = safe_extract(archive, tmp_path / "d", members=r"^keep/")
    assert written == [(tmp_path / "d/keep/1.txt").resolve()]
    assert not (tmp_path / "d/drop").exists()
    bad = _zip(tmp_path / "b.zip", {"keep/1.txt": b"1", "../x.txt": b"x"})
    with pytest.raises(UnsafeArchiveError, match="escapes"):
        safe_extract(bad, tmp_path / "e", members=r"^keep/")
    assert not (tmp_path / "e/keep/1.txt").exists()


def test_safe_extract_skips_complete_files_only(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "a.zip", {"a.txt": b"abc", "b.txt": b"defg"})
    dest = tmp_path / "d"
    assert len(safe_extract(archive, dest)) == 2
    (dest / "b.txt").write_bytes(b"de")  # interrupted extraction
    again = safe_extract(archive, dest, skip_existing=True)
    assert again == [(dest / "b.txt").resolve()]
    assert (dest / "b.txt").read_bytes() == b"defg"


def test_sync_extracts_the_kyoto_window_where_the_etl_finds_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from driftstream.data import download  # noqa: PLC0415

    archive = _zip(
        tmp_path / "archive.zip",
        {
            "2006/Kyoto2016/2006/12/20061231.txt": b"old\n",
            "2007/Kyoto2016/2007/01/20070101.txt": b"a\n",
            "2007/Kyoto2016/2007/02/20070201.txt": b"b\n",
            "2007/Kyoto2016/2007/03/20070301.txt": b"c\n",
        },
    )
    monkeypatch.setattr(download, "KYOTO_URL", archive.as_uri())
    data_root = tmp_path / "data"
    data_root.mkdir()
    files = kyoto_files("2007-01", "2007-02")
    sums = Checksums(data_root / "CHECKSUMS.raw")
    (res,) = sync(files, data_root, sums)
    assert (res.downloaded, res.extracted) == (True, 2)
    raw = data_root / "raw/kyoto2006"
    found = discover_day_files(raw, "2007-01", "2007-02")
    assert [p.name for p in found] == ["20070101.txt", "20070201.txt"]
    assert not list(raw.rglob("20061231.txt"))
    (again,) = sync(files, data_root, Checksums(data_root / "CHECKSUMS.raw"))
    assert (again.status, again.downloaded, again.extracted) == (
        "verified",
        False,
        0,
    )


def test_new_checksum_file_starts_with_its_path(tmp_path: Path) -> None:
    sums = Checksums(tmp_path / "CHECKSUMS.raw")
    sums.check("raw/a.zip", "aa", strict=False)
    sums.save()
    lines = (tmp_path / "CHECKSUMS.raw").read_text().splitlines()
    assert lines[0] == "# data/CHECKSUMS.raw"
    assert lines[-1] == "aa  raw/a.zip"
    assert Checksums(tmp_path / "CHECKSUMS.raw").entries == {"raw/a.zip": "aa"}
