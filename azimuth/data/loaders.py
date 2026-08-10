"""Data loaders. Implements ``docs/04_SPEC_PYTHON_CLI.md`` section 5.

Every loader returns the canonical frame::

    index: pd.DatetimeIndex, tz-aware UTC, monotonic, no duplicates
    cols : open, high, low, close, volume   (float64)
    attrs: symbol, timeframe, source, fetched_at

Validation on load is not optional and not a warning. A frame that violates the
OHLC invariants will still produce numbers all the way through to a Sharpe ratio;
it will simply produce the wrong ones, and nothing downstream can detect it.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "OHLCV_COLUMNS",
    "gap_report",
    "load_ccxt",
    "load_csv",
    "load_yfinance",
    "validate_frame",
]

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def _stamp(df: pd.DataFrame, symbol: str, timeframe: str, source: str) -> pd.DataFrame:
    """Attach the ``docs/04`` section 5 provenance attrs."""
    df.attrs.update(
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        fetched_at=datetime.now(UTC).isoformat(),
    )
    return df


def gap_report(df: pd.DataFrame, timeframe: str) -> list[str]:
    """Describe gaps in the index relative to the expected bar spacing.

    Emitted to stderr on load (``docs/04`` section 5), not raised. Gaps are normal
    -- exchange outages, weekends, holidays -- but they matter twice over:

    * ``docs/05`` section 2's embargo is measured in BARS, so a gap means the
      embargo covers less wall-clock time than intended;
    * a gap inside a 233-bar lookback silently widens that window's real duration.

    Returns:
        Human-readable lines. Empty when the index is evenly spaced.
    """
    from azimuth.data.resample import timeframe_to_rule

    if len(df) < 3:
        return []

    expected = pd.Timedelta(timeframe_to_rule(timeframe))
    deltas = df.index.to_series().diff().dropna()
    gaps = deltas[deltas > expected * 1.5]
    if gaps.empty:
        return []

    lines = [
        f"{len(gaps)} gap(s) larger than 1.5x the {timeframe} bar interval "
        f"({expected}); largest {gaps.max()}"
    ]
    for timestamp, delta in gaps.nlargest(5).items():
        lines.append(f"  {timestamp}  gap of {delta}")
    if len(gaps) > 5:
        lines.append(f"  ... and {len(gaps) - 5} more")
    return lines


def validate_frame(df: pd.DataFrame, timeframe: str | None = None) -> pd.DataFrame:
    """Assert the canonical-frame contract; emit a gap report to stderr.

    Checks, all fatal (``docs/04`` section 5):

    1. the five OHLCV columns exist and are float64;
    2. the index is a tz-aware UTC DatetimeIndex, monotonic, without duplicates;
    3. no NaNs in OHLC (volume may legitimately be missing on some index feeds);
    4. ``high >= max(open, close)`` and ``low <= min(open, close)``.

    Check 4 is the one worth being strict about. A single bar where high < close
    is usually a vendor artefact, but it silently inverts true range on that bar
    and therefore perturbs ATR, the ribbon slope normalisation and every ATR-
    anchored stop for the next `length` bars.

    Raises:
        ValueError: on any violation, naming the offending timestamps.
    """
    missing = [column for column in OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"canonical frame is missing columns {missing}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(f"index must be a DatetimeIndex, got {type(df.index).__name__}")
    if df.index.tz is None:
        raise ValueError("index must be tz-aware UTC (docs/04 section 5)")
    if str(df.index.tz) not in {"UTC", "utc"}:
        raise ValueError(f"index must be UTC, got {df.index.tz}")
    if not df.index.is_monotonic_increasing:
        raise ValueError("index must be monotonic increasing")
    if df.index.has_duplicates:
        dupes = df.index[df.index.duplicated()][:5].tolist()
        raise ValueError(f"index has duplicate timestamps, e.g. {dupes}")

    ohlc = ["open", "high", "low", "close"]
    nan_rows = df[ohlc].isna().any(axis=1)
    if nan_rows.any():
        where = df.index[nan_rows][:5].tolist()
        raise ValueError(f"{int(nan_rows.sum())} row(s) have NaN in OHLC, e.g. {where}")

    high_bad = df["high"] < df[["open", "close"]].max(axis=1)
    low_bad = df["low"] > df[["open", "close"]].min(axis=1)
    if high_bad.any() or low_bad.any():
        where = df.index[high_bad | low_bad][:5].tolist()
        raise ValueError(
            f"{int((high_bad | low_bad).sum())} row(s) violate the OHLC invariants "
            f"(high >= max(open, close), low <= min(open, close)), e.g. {where}. "
            "These perturb true range and therefore ATR, the ribbon slope and every "
            "ATR-anchored stop."
        )

    if timeframe:
        for line in gap_report(df, timeframe):
            print(f"[gap] {line}", file=sys.stderr)

    return df


def _canonicalise(raw: pd.DataFrame, symbol: str, timeframe: str, source: str) -> pd.DataFrame:
    """Lower-case the columns, coerce dtypes, sort, de-duplicate, validate."""
    df = raw.copy()
    df.columns = [str(column).lower().strip() for column in df.columns]

    keep = [column for column in OHLCV_COLUMNS if column in df.columns]
    if "volume" not in df.columns:
        df["volume"] = np.nan
        keep = [*keep, "volume"]
    df = df[keep].astype("float64")

    index = pd.DatetimeIndex(pd.to_datetime(df.index))
    df.index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")

    df = df[~df.index.duplicated(keep="first")].sort_index()
    return _stamp(validate_frame(df, timeframe), symbol, timeframe, source)


def load_csv(path: str | Path, symbol: str, timeframe: str) -> pd.DataFrame:
    """Load a local CSV into the canonical frame.

    Expects a parseable timestamp in the first column (or a column named ``time``
    / ``date`` / ``datetime``) and OHLCV columns in any case.
    """
    raw = pd.read_csv(path)
    time_column = next(
        (c for c in raw.columns if str(c).lower().strip() in {"time", "date", "datetime", "ts"}),
        raw.columns[0],
    )
    raw[time_column] = pd.to_datetime(raw[time_column], utc=True, format="mixed")
    return _canonicalise(raw.set_index(time_column), symbol, timeframe, f"csv:{path}")


def load_yfinance(symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
    """Equities, FX and indices via yfinance.

    Note the instrument-suitability guidance in ``docs/07`` section 4: single
    equities around earnings are a poor fit because gap risk breaks ATR stops, and
    anything with under ~1,000 bars of history cannot support the 233-EMA at all.
    """
    import yfinance

    interval = _YF_INTERVALS.get(timeframe)
    if interval is None:
        raise ValueError(
            f"timeframe {timeframe!r} has no yfinance interval mapping; "
            f"known: {sorted(_YF_INTERVALS)}"
        )

    raw: Any = yfinance.download(
        symbol, start=start, end=end, interval=interval, auto_adjust=False, progress=False
    )
    if raw is None or raw.empty:
        raise ValueError(f"yfinance returned no data for {symbol} {timeframe} from {start}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    return _canonicalise(raw, symbol, timeframe, "yfinance")


_YF_INTERVALS = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1D": "1d",
    "D": "1d",
    "1W": "1wk",
    "W": "1wk",
    "1M": "1mo",
}


def load_ccxt(symbol: str, timeframe: str, start: str, exchange: str = "binance") -> pd.DataFrame:
    """Crypto via ccxt, paginating until the range is covered."""
    import ccxt

    tf = _CCXT_TIMEFRAMES.get(timeframe)
    if tf is None:
        raise ValueError(
            f"timeframe {timeframe!r} has no ccxt mapping; known: {sorted(_CCXT_TIMEFRAMES)}"
        )

    client = getattr(ccxt, exchange)({"enableRateLimit": True})
    since = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)

    rows: list[list[float]] = []
    while True:
        batch = client.fetch_ohlcv(symbol, timeframe=tf, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        since = int(batch[-1][0]) + 1

    if not rows:
        raise ValueError(f"ccxt/{exchange} returned no data for {symbol} {timeframe}")

    raw = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    raw["time"] = pd.to_datetime(raw["time"], unit="ms", utc=True)
    return _canonicalise(raw.set_index("time"), symbol, timeframe, f"ccxt:{exchange}")


_CCXT_TIMEFRAMES = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1D": "1d",
    "D": "1d",
    "1W": "1w",
    "W": "1w",
}
