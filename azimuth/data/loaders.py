"""Data loaders. Implements ``docs/04_SPEC_PYTHON_CLI.md`` section 5.

Every loader returns the canonical frame::

    index: pd.DatetimeIndex, tz-aware UTC, monotonic, no duplicates
    cols : open, high, low, close, volume   (float64)
    attrs: symbol, timeframe, source, fetched_at

Validation on load: no NaNs in OHLC, ``high >= max(open, close)``,
``low <= min(open, close)``, gap report emitted to stderr.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def validate_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Assert the canonical-frame contract; emit a gap report to stderr."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 5")


def load_csv(path: str | Path, symbol: str, timeframe: str) -> pd.DataFrame:
    """Load a local CSV into the canonical frame."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 5")


def load_yfinance(symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Equities, FX and indices via yfinance."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 5")


def load_ccxt(symbol: str, timeframe: str, start: str, exchange: str = "binance") -> pd.DataFrame:
    """Crypto via ccxt."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 5")
