# src/driftstream/__init__.py
"""DriftStream-IDS: verification latency and labelling budgets in NIDS.

The package is one library used by two execution modes: a deterministic
discrete-event simulator (``driftstream.simulate``) and a Kafka-Spark
deployment (``driftstream.deploy``). See ``ARCHITECTURE.md`` §5.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
