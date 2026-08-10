"""Parquet cache keyed by (symbol, tf, start, end).

``docs/04_SPEC_PYTHON_CLI.md`` section 3. The data hash produced here feeds the run
manifest (section 8), which is what makes ``docs/04`` section 8's determinism claim
checkable: "Two runs with the same manifest must produce byte-identical metrics."

The hash covers the frame's contents, not the file. A vendor silently revising
history -- yfinance adjusting for a split, an exchange backfilling a gap -- changes
the hash, which is exactly the signal wanted: it means a "reproduction" of an
earlier run is not reproducing anything.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

__all__ = ["cache_key", "data_sha256", "read", "write"]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def cache_key(symbol: str, timeframe: str, start: str, end: str) -> str:
    """Deterministic, filesystem-safe cache key.

    Symbols contain ``/`` (``BTC/USDT``) and ``:`` (``TVC:DXY``), so the readable
    part is sanitised and a short hash of the original is appended -- keeping the
    filename legible while ensuring two symbols cannot collide after sanitising.
    """
    raw = f"{symbol}|{timeframe}|{start}|{end}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    readable = _UNSAFE.sub("-", f"{symbol}_{timeframe}_{start}_{end}").strip("-")
    return f"{readable}_{digest}"


def _path(cache_dir: Path, key: str) -> Path:
    return Path(cache_dir) / f"{key}.parquet"


def read(cache_dir: Path, key: str) -> pd.DataFrame | None:
    """Return the cached frame, or None on a miss."""
    path = _path(cache_dir, key)
    if not path.is_file():
        return None
    return pd.read_parquet(path)


def write(cache_dir: Path, key: str, df: pd.DataFrame) -> Path:
    """Persist a frame to the cache; return the written path."""
    path = _path(cache_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return path


def data_sha256(df: pd.DataFrame) -> str:
    """Content hash of the canonical frame, for the run manifest.

    Hashes the index and the OHLCV columns in a fixed order, via each column's
    raw bytes. Deliberately excludes ``df.attrs``: ``fetched_at`` changes on every
    download, and two identical datasets fetched an hour apart must hash the same
    or the determinism test in ``docs/04`` section 8 can never pass.
    """
    digest = hashlib.sha256()
    digest.update(df.index.to_numpy(dtype="datetime64[ns]").tobytes())
    for column in ("open", "high", "low", "close", "volume"):
        if column in df.columns:
            digest.update(column.encode("utf-8"))
            digest.update(df[column].to_numpy(dtype="float64").tobytes())
    return digest.hexdigest()
