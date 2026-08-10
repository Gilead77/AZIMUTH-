"""HTF construction. Implements ``docs/04_SPEC_PYTHON_CLI.md`` section 6.

PARITY-CRITICAL, and the single most dangerous file in the data layer.

Pine's HTF bars close at the end of their period, and a value only becomes
available AFTER that close::

    htf = df.resample(rule, label="right", closed="left").agg(OHLCV_AGG)
    htf_score = compute_htf_score(htf).shift(1)      # confirmed bar only
    aligned = htf_score.reindex(df.index, method="ffill")

The ``.shift(1)`` is the Python equivalent of returning ``s[1]`` from inside
``request.security(..., lookahead = barmerge.lookahead_off)``. ``docs/04``
section 6 states plainly what omitting it costs: "produces lookahead and is the
most likely source of a fake edge".

DEVIATION FROM ``docs/04`` SECTION 6 -- ``closed="left"``, not ``closed="right"``.
See docs/11_FINDINGS.md finding 21. The spec's snippet uses ``closed="right"``,
which is wrong for this data and shifts every HTF bar's contents by one base bar:

* canonical-frame timestamps are bar-OPEN times -- that is what TradingView's
  chart export, yfinance and ccxt all return;
* ``closed="right"`` builds the half-open interval ``(00:00, 04:00]``, so the 4H
  bar labelled 04:00 aggregates the 1H bars 01:00, 02:00, 03:00, 04:00;
* TradingView's 4H bar covers 00:00, 01:00, 02:00, 03:00.

So the resampled open, high, low and close each come from the wrong window --
including one bar that belongs to the NEXT HTF period. ``closed="left"`` builds
``[00:00, 04:00)``, which is the correct set, and ``label="right"`` still stamps
it 04:00, the first instant its value could legally be known.

The failure mode is nasty: it presents as an ``x_htf`` parity mismatch, and the
tempting fix is to adjust the ``.shift(1)``, which would trade a grouping error
for a lookahead error and make the numbers look better.

The shift itself lives in :func:`azimuth.core.htf.align_to_base`. This module
does the resampling and the alignment mechanics; ``tests/test_htf_alignment.py``
asserts on synthetic data that no bar can see its own HTF bar's close, and
includes a negative control proving the test fails when the shift is removed.
"""

from __future__ import annotations

import re
from typing import Any, cast

import pandas as pd

__all__ = ["OHLCV_AGG", "bars_per_htf_bar", "resample_htf", "timeframe_to_rule"]

OHLCV_AGG: dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}

_MINUTES_PATTERN = re.compile(r"^\d+$")
"""Pine expresses intraday timeframes as a bare minute count: "240" is 4 hours."""

_UNIT_PATTERN = re.compile(r"^(\d*)([SDWM])$", re.IGNORECASE)
"""Pine's non-intraday forms: "1D", "D", "1W", "3M", "30S"."""

# pandas offset aliases. "h" and "min" are the modern spellings; the capitalised
# legacy forms emit FutureWarnings on pandas >= 2.2.
_UNIT_TO_OFFSET = {"S": "s", "D": "D", "W": "W", "M": "MS"}


def timeframe_to_rule(timeframe: str) -> str:
    """Map a Pine timeframe string to a pandas offset alias.

    Pine's ``timeframe.period`` grammar (``docs/07`` section 3 uses these forms):

    ==============  ==========  ===================================
    Pine            Meaning     pandas
    ==============  ==========  ===================================
    ``"15"``        15 minutes  ``15min``
    ``"240"``       4 hours     ``240min``
    ``"1D"`` / ``"D"``  1 day   ``1D``
    ``"1W"``        1 week      ``1W``
    ``"1M"``        1 month     ``1MS`` (month START, see below)
    ==============  ==========  ===================================

    Months map to ``MS`` rather than ``M``: pandas' ``M`` anchors to month END,
    which with ``label="right"`` would place a bar's label on the last day of the
    month it summarises rather than the first instant after it. That is an
    off-by-one-bar alignment error -- the exact class of bug the HTF contract
    exists to prevent -- and it is invisible on a chart.

    Raises:
        ValueError: on anything the grammar does not cover, rather than guessing.
    """
    tf = timeframe.strip()
    if not tf:
        raise ValueError("timeframe must not be empty")

    if _MINUTES_PATTERN.match(tf):
        minutes = int(tf)
        if minutes <= 0:
            raise ValueError(f"timeframe {timeframe!r}: minute count must be positive")
        return f"{minutes}min"

    match = _UNIT_PATTERN.match(tf)
    if match is None:
        raise ValueError(
            f"unrecognised timeframe {timeframe!r}. Expected a bare minute count "
            '("15", "240") or a count with a unit ("1D", "1W", "3M", "30S").'
        )

    count_text, unit = match.groups()
    count = int(count_text) if count_text else 1
    if count <= 0:
        raise ValueError(f"timeframe {timeframe!r}: count must be positive")

    return f"{count}{_UNIT_TO_OFFSET[unit.upper()]}"


def bars_per_htf_bar(base_timeframe: str, htf_timeframe: str) -> float:
    """How many base bars fit in one HTF bar. Used for sanity reporting.

    ``docs/07`` section 3 recommends HTF1 at roughly 4x the chart timeframe and
    HTF2 at roughly 24x. A ratio below 1 means the "higher" timeframe is actually
    faster than the chart, which produces an HTF series that updates within the
    bar and defeats the entire confirmation contract.

    Months are approximated at 30 days -- adequate for a ratio warning, and never
    used for alignment.
    """
    minutes = {"s": 1 / 60, "min": 1.0, "h": 60.0, "D": 1440.0, "W": 10080.0, "MS": 43200.0}

    def to_minutes(rule: str) -> float:
        for suffix, factor in minutes.items():
            if rule.endswith(suffix):
                return float(rule[: -len(suffix)] or 1) * factor
        raise ValueError(f"cannot size offset {rule!r}")

    return to_minutes(timeframe_to_rule(htf_timeframe)) / to_minutes(
        timeframe_to_rule(base_timeframe)
    )


def resample_htf(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Right-closed, right-labelled HTF bars matching Pine's bar construction.

    Args:
        df: Canonical OHLCV frame (``docs/04`` section 5) on a DatetimeIndex.
        rule: A pandas offset alias, from :func:`timeframe_to_rule`.

    Returns:
        OHLCV aggregated to ``rule``. Empty periods -- weekends on an FX feed, say
        -- are DROPPED rather than emitted as NaN rows, matching Pine, which has
        no bar where the instrument did not trade. A NaN row would otherwise
        forward-fill into the base timeframe as a real HTF reading.

    Note:
        ``closed="left"`` groups the base bars whose OPEN falls inside the period
        (finding 21 -- the spec's ``closed="right"`` takes the wrong window), and
        ``label="right"`` stamps the result with the instant the bar CLOSES, which
        is the first timestamp at which its value could legally be known.

        The two settings work together with the ``.shift(1)`` in
        :func:`azimuth.core.htf.align_to_base`. Changing any one of the three in
        isolation silently changes the lag, and a lag error here is indistinguishable
        from a working signal until parity is run.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(f"expected a DatetimeIndex, got {type(df.index).__name__}")
    if not df.index.is_monotonic_increasing:
        raise ValueError("index must be monotonic increasing before resampling")

    missing = [column for column in OHLCV_AGG if column not in df.columns]
    if missing:
        raise ValueError(f"frame is missing OHLCV columns {missing}")

    # cast: pandas-stubs types .agg()'s mapping more narrowly than the runtime accepts
    resampled = df.resample(rule, label="right", closed="left").agg(cast(Any, OHLCV_AGG))

    # A period with no base bars yields NaN for every column. Drop those rows:
    # Pine has no such bar, and keeping them would ffill a fabricated reading down
    # onto the base timeframe.
    return resampled.dropna(subset=["close"])
