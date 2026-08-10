"""Parquet cache keyed by (symbol, tf, start, end).

``docs/04_SPEC_PYTHON_CLI.md`` section 3. The data hash produced here feeds the run
manifest (section 8), so two runs on the same data are provably comparable.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def cache_key(symbol: str, timeframe: str, start: str, end: str) -> str:
    """Deterministic cache key."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 3")


def read(cache_dir: Path, key: str) -> pd.DataFrame | None:
    """Return the cached frame, or None on a miss."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 3")


def write(cache_dir: Path, key: str, df: pd.DataFrame) -> Path:
    """Persist a frame to the cache; return the written path."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 3")


def data_sha256(df: pd.DataFrame) -> str:
    """Content hash of the canonical frame, for the run manifest."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 8")
