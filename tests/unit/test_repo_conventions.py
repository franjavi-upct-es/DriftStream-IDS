# tests/unit/test_repo_conventions.py
"""Repository-wide conventions that are cheap to enforce automatically.

Project rule: every file starts with a comment that holds its path
relative to the repository root. This test keeps the rule true as the
repository grows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories that hold generated, downloaded or tool-owned content.
SKIP_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
    ".import_linter_cache",
    "__pycache__",
    "htmlcov",
    "outputs",
    "multirun",
    "mlruns",
    "dist",
    "build",
}
SKIP_TOP_LEVEL = {"data/raw", "data/interim", "data/processed", "results"}
# Generated lock file and formats without a comment syntax.
SKIP_FILES = {"uv.lock", ".coverage"}
SKIP_SUFFIXES = {".json", ".parquet", ".png", ".pdf", ".docx", ".csv"}


def _tracked_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        rel = path.relative_to(REPO_ROOT)
        if not path.is_file() or any(p in SKIP_DIRS for p in rel.parts):
            continue
        if any(rel.as_posix().startswith(s) for s in SKIP_TOP_LEVEL):
            continue
        if rel.name in SKIP_FILES or rel.suffix in SKIP_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


@pytest.mark.parametrize(
    "path",
    _tracked_files(),
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_first_line_names_relative_path(path: Path) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    first = lines[0].strip()
    # Documented exception (docs/decision_log.md, 2026-11-25): Hydra reads
    # a `# @package` directive only on the first line, so such configs
    # carry the path comment on line 2.
    if first.startswith("# @package "):
        first = lines[1].strip()
    accepted = {f"# {rel}", f"<!-- {rel} -->"}
    assert first in accepted, f"{rel}: first line is {first!r}"
