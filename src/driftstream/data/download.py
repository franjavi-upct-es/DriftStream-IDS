# src/driftstream/data/download.py
"""Download and verify the raw datasets (ROADMAP T2.1, T2.3).

Sources (checked 2026-11-25):

* **CIC-IDS2017, improved** — the latest DistriNet/KU Leuven release
  (Liu et al., IEEE CNS 2022, building on Engelen et al. 2021):
  ``CICIDS2017_improved.zip`` (≈ 328 MB), one CSV per day.
* **Kyoto 2006+** — ``new_data201704`` release (Bro 2.4 sessions,
  sanitised IPs). The original host (``takakura.com/Kyoto_data``) refused
  connections on 2026-11-27, so the data comes from the Kaggle mirror
  ``harshwardhanbhangale/kyoto-2006`` (CC BY 4.0), pinned to version 1:
  one ``archive.zip`` (≈ 14.5 GB; 109 GB unpacked) holding the daily
  ``<YYYY>/Kyoto2016/<YYYY>/<MM>/<YYYYMMDD>.txt`` files of 2006-11 → 2015-12
  (2010 absent). The archive needs no Kaggle account; only the day files
  of the configured window are extracted. The mirror is a third party, so
  its archive is pinned by checksum like any other source.

Integrity follows *trust on first use*: the first verified download of a
file records its SHA-256 in ``data/CHECKSUMS.raw`` (committed to git);
every later download must match it. ``strict=True`` refuses files without
a recorded checksum. Archives are extracted with a path-traversal guard
("zip slip"), because a downloaded archive is untrusted input.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import urllib.request
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from driftstream.core.errors import ChecksumMismatchError, UnsafeArchiveError

__all__ = [
    "CIC_URL",
    "KYOTO_KAGGLE_DATASET",
    "KYOTO_KAGGLE_VERSION",
    "KYOTO_URL",
    "Checksums",
    "RawFile",
    "cic_files",
    "fetch",
    "kyoto_files",
    "months",
    "safe_extract",
    "sha256_file",
    "sync",
]

log = logging.getLogger(__name__)

CIC_URL = (
    "https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/"
    "CICIDS2017_improved.zip"
)
KYOTO_KAGGLE_DATASET = "harshwardhanbhangale/kyoto-2006"
KYOTO_KAGGLE_VERSION = 1
KYOTO_URL = (
    f"https://www.kaggle.com/api/v1/datasets/download/{KYOTO_KAGGLE_DATASET}"
    f"?datasetVersionNumber={KYOTO_KAGGLE_VERSION}"
)
_CHUNK = 1 << 20
_DECEMBER = 12
_HTTP_PARTIAL = 206
_S_IFLNK = 0o120000  # symbolic link in the zip external attributes
_S_IFMT = 0o170000


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(_CHUNK):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RawFile:
    """One file to download.

    Attributes:
        url: Source URL.
        target: Destination, relative to the ``data/`` root.
        extract_to: Directory (relative to ``data/``) to unzip into, or
            ``None`` to keep the file as is.
        members: Regular expression (``re.search`` on the member name)
            selecting the archive members to extract, or ``None`` for all.
    """

    url: str
    target: Path
    extract_to: Path | None = None
    members: str | None = None


def cic_files() -> list[RawFile]:
    """Return the CIC-IDS2017 improved archive."""
    base = Path("raw/cicids2017_corrected")
    return [RawFile(CIC_URL, base / "CICIDS2017_improved.zip", base)]


def months(start: str, end: str) -> Iterator[tuple[int, int]]:
    """Yield ``(year, month)`` from ``start`` to ``end`` inclusive.

    Args:
        start: ``YYYY-MM`` (a ``YYYY-MM-DD`` date is accepted).
        end: ``YYYY-MM`` (a ``YYYY-MM-DD`` date is accepted).
    """
    y, m = (int(p) for p in start[:7].split("-"))
    ey, em = (int(p) for p in end[:7].split("-"))
    if (y, m) > (ey, em):
        raise ValueError(f"start {start} is after end {end}")
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + 1, 1) if m == _DECEMBER else (y, m + 1)


def kyoto_files(start: str = "2007-01", end: str = "2009-12") -> list[RawFile]:
    """Return the Kyoto Kaggle archive, restricted to a window's day files.

    The archive is the same for every window; only the extracted members
    change, so widening the window does not download anything again.

    Args:
        start: First month, ``YYYY-MM``.
        end: Last month, ``YYYY-MM``.
    """
    base = Path("raw/kyoto2006")
    keys = "|".join(f"{y}{m:02d}" for y, m in months(start, end))
    return [
        RawFile(
            KYOTO_URL,
            base / "_zips" / f"kyoto-2006-kaggle-v{KYOTO_KAGGLE_VERSION}.zip",
            base,
            members=rf"(?:^|/)(?:{keys})\d{{2}}\.txt$",
        )
    ]


class Checksums:
    """``sha256sum``-style checksum file: ``<hex>  <relative path>``.

    Lines starting with ``#`` are comments and are preserved on save.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.header: list[str] = []
        self.entries: dict[str, str] = {}
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    if not self.entries:
                        self.header.append(line)
                    continue
                digest, rel = line.split(maxsplit=1)
                self.entries[rel.strip()] = digest.lower()
        if not self.header:  # new file: path comment (repository rule)
            self.header = [
                f"# data/{self.path.name}",
                "# SHA-256 of raw downloads, sha256sum format: recorded on",
                "# first download (trust on first use), verified afterwards.",
            ]

    def check(
        self, rel: str, digest: str, *, strict: bool
    ) -> Literal["verified", "recorded"]:
        """Verify ``digest`` for ``rel``, or record it on first use.

        Args:
            rel: Path relative to the ``data/`` root (POSIX form).
            digest: Observed SHA-256.
            strict: Refuse files without a recorded checksum.

        Returns:
            ``"verified"`` or ``"recorded"``.

        Raises:
            ChecksumMismatchError: On mismatch, or on an unknown file in
                strict mode.
        """
        expected = self.entries.get(rel)
        if expected is None:
            if strict:
                raise ChecksumMismatchError(f"{rel}: no recorded checksum")
            self.entries[rel] = digest
            return "recorded"
        if expected != digest:
            raise ChecksumMismatchError(
                f"{rel}: expected {expected}, got {digest}"
            )
        return "verified"

    def save(self) -> None:
        """Write the file (header comments first, entries sorted)."""
        body = [f"{d}  {r}" for r, d in sorted(self.entries.items())]
        text = "\n".join([*self.header, *body]) + "\n"
        self.path.write_text(text, encoding="utf-8")


def fetch(url: str, dest: Path, *, timeout: float = 60.0) -> int:
    """Download ``url`` to ``dest``, resuming a partial ``.part`` file.

    The file appears at ``dest`` only once complete (atomic rename). If
    the server ignores the ``Range`` header the download restarts.

    Args:
        url: Source URL (``https://`` or ``file://``).
        dest: Destination path.
        timeout: Socket timeout, seconds.

    Returns:
        Bytes written in this call.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    offset = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url)
    if offset:
        req.add_header("Range", f"bytes={offset}-")
    written = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resumed = offset > 0 and getattr(resp, "status", 200) == _HTTP_PARTIAL
        mode = "ab" if resumed else "wb"
        if offset and not resumed:
            log.info("%s: server ignored Range, restarting", url)
        with part.open(mode) as fh:
            while block := resp.read(_CHUNK):
                fh.write(block)
                written += len(block)
    part.replace(dest)
    return written


def safe_extract(
    archive: Path,
    dest: Path,
    *,
    members: str | None = None,
    skip_existing: bool = False,
) -> list[Path]:
    """Extract a zip archive, refusing members that escape ``dest``.

    Every member is checked, selected or not: an archive with one unsafe
    member is rejected as a whole.

    Args:
        archive: Zip file (untrusted).
        dest: Target directory.
        members: Regular expression (``re.search`` on the member name)
            selecting the members to extract, or ``None`` for all.
        skip_existing: Leave a file alone when it already exists with the
            member's size (an interrupted extraction leaves a shorter
            file, which is rewritten).

    Returns:
        Paths written in this call.

    Raises:
        UnsafeArchiveError: If a member is absolute, contains ``..`` that
            leaves ``dest``, or is a symbolic link.
    """
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    wanted = re.compile(members) if members is not None else None
    out: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest):
                raise UnsafeArchiveError(f"{info.filename!r} escapes {dest}")
            if (info.external_attr >> 16) & _S_IFMT == _S_IFLNK:
                raise UnsafeArchiveError(f"{info.filename!r} is a symlink")
        for info in zf.infolist():
            if wanted is not None and not wanted.search(info.filename):
                continue
            target = (dest / info.filename).resolve()
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if (
                skip_existing
                and target.is_file()
                and target.stat().st_size == info.file_size
            ):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, _CHUNK)
            out.append(target)
    return out


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome for one raw file.

    Attributes:
        file: The raw file.
        status: ``"verified"`` or ``"recorded"``.
        downloaded: Whether a download happened in this call.
        extracted: Number of files written by the extraction (files
            already in place are not rewritten and not counted).
    """

    file: RawFile
    status: str
    downloaded: bool
    extracted: int


def sync(
    files: list[RawFile],
    data_root: Path,
    checksums: Checksums,
    *,
    strict: bool = False,
    extract: bool = True,
) -> list[SyncResult]:
    """Download missing files, verify all of them and extract archives.

    Existing complete files are not downloaded again; their checksum is
    still verified. The checksum file is saved after every file, so an
    interrupted run keeps what it has verified.

    Args:
        files: Files to synchronise.
        data_root: The ``data/`` directory.
        checksums: Checksum registry (``data/CHECKSUMS.raw``).
        strict: Refuse files without a recorded checksum.
        extract: Unzip archives that declare ``extract_to``.

    Returns:
        One result per file, in input order.
    """
    results: list[SyncResult] = []
    for rf in files:
        path = Path(data_root) / rf.target
        downloaded = not path.exists()
        if downloaded:
            log.info("downloading %s", rf.url)
            fetch(rf.url, path)
        status = checksums.check(
            rf.target.as_posix(), sha256_file(path), strict=strict
        )
        checksums.save()
        n = 0
        if extract and rf.extract_to is not None:
            n = len(
                safe_extract(
                    path,
                    Path(data_root) / rf.extract_to,
                    members=rf.members,
                    skip_existing=True,
                )
            )
        results.append(SyncResult(rf, status, downloaded, n))
    return results
