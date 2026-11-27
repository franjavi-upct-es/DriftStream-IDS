# src/driftstream/data/subsample.py
"""Deterministic, hash-based subsampling (ARCHITECTURE.md §8.3).

A flow is kept when ``u(key, seed) < fraction`` with ``u`` a uniform hash
in [0, 1). Because the decision depends only on the key and the seed:

* the same flow is kept or dropped in every run with the same seed;
* nested fractions are consistent (a flow kept at 10 % is kept at 25 %);
* prevalence and temporal structure are preserved in expectation, as the
  hash is independent of the label and the timestamp.

The hash is SplitMix64 (Steele et al. 2014), vectorised with NumPy.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = ["keep_mask", "uniform_hash"]

_GOLDEN = np.uint64(0x9E3779B97F4A7C15)
_M1 = np.uint64(0xBF58476D1CE4E5B9)
_M2 = np.uint64(0x94D049BB133111EB)


def uniform_hash(keys: ArrayLike, seed: int) -> NDArray[np.float64]:
    """Map integer keys to uniforms in [0, 1), reproducibly.

    Args:
        keys: Integer keys (for example ``flow_id`` or a row hash).
        seed: Non-negative integer seed.

    Returns:
        One float in [0, 1) per key.
    """
    if seed < 0:
        raise ValueError(f"seed must be >= 0, got {seed}")
    k = np.asarray(keys).astype(np.uint64, copy=False)
    with np.errstate(over="ignore"):
        z = k + np.uint64(seed) * _GOLDEN + _GOLDEN
        z = (z ^ (z >> np.uint64(30))) * _M1
        z = (z ^ (z >> np.uint64(27))) * _M2
        z = z ^ (z >> np.uint64(31))
    # Top 53 bits -> exact double in [0, 1).
    out: NDArray[np.float64] = (z >> np.uint64(11)).astype(np.float64) * (
        2.0**-53
    )
    return out


def keep_mask(keys: ArrayLike, fraction: float, seed: int) -> NDArray[np.bool_]:
    """Return which keys to keep for a sampling ``fraction``.

    Args:
        keys: Integer keys.
        fraction: Share to keep, in [0, 1].
        seed: Non-negative integer seed.

    Returns:
        Boolean mask, ``True`` for kept keys.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be in [0, 1], got {fraction}")
    mask: NDArray[np.bool_] = uniform_hash(keys, seed) < fraction
    return mask
