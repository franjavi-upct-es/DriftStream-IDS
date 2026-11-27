# src/driftstream/core/errors.py
"""Project-wide exception hierarchy.

Every error raised on purpose by DriftStream-IDS derives from
:class:`DriftStreamError`, so callers (the CLI, the runner) can tell a
documented failure from a bug.
"""

from __future__ import annotations

__all__ = [
    "ChecksumMismatchError",
    "DataValidationError",
    "DriftStreamError",
    "SchemaError",
    "UnknownLabelError",
    "UnsafeArchiveError",
]


class DriftStreamError(Exception):
    """Base class of all documented DriftStream-IDS errors."""


class SchemaError(DriftStreamError):
    """A table does not have the expected columns or types."""


class DataValidationError(DriftStreamError):
    """Processed data violates a post-ETL invariant.

    Attributes:
        failures: Human-readable description of every failed check.
    """

    def __init__(self, failures: list[str]) -> None:
        self.failures = list(failures)
        joined = "; ".join(self.failures) or "unknown failure"
        super().__init__(f"{len(self.failures)} check(s) failed: {joined}")


class UnknownLabelError(DriftStreamError):
    """A raw label is not covered by the dataset's label mapping.

    Failing loudly is deliberate: a silently mapped new label would change
    the ground truth without anyone noticing.
    """


class ChecksumMismatchError(DriftStreamError):
    """A file's SHA-256 differs from the recorded checksum."""


class UnsafeArchiveError(DriftStreamError):
    """An archive member would be written outside the target directory."""
