"""Bollinger component. Implements ``docs/01_SPEC_COMPONENTS.md`` section 2.

::

    basis = SMA(close, 20);  sigma = stdev(close, 20)   # POPULATION, ddof=0
    %B        = (close - lower) / (upper - lower)
    bandwidth = (upper - lower) / basis
    bwPct     = percentrank(bandwidth, 200)

Regime-dependent polarity (``docs/01`` section 2, ``docs/02`` section 2) -- the
single most important design decision in AZIMUTH:

===========  ==========================  ======================
Regime       Logic                       Score
===========  ==========================  ======================
Trend        band ride = strength        ``clip((%B - 0.5)*2)``
Range        band tag = exhaustion       ``clip((0.5 - %B)*2)``
===========  ==========================  ======================

Two traps:

* ``ta.stdev`` is population (``ddof=0``); ``pandas.rolling().std()`` defaults to
  ``ddof=1`` (``docs/06`` section 3). Regression test: ``tests/test_stdev_ddof.py``.
* docs/11_FINDINGS.md finding 1: the regime boolean that flips this sign has no
  hysteresis, so a single flicker moves the composite by up to ~74 points -- more
  than ``signal.enter``.
"""

from __future__ import annotations

from azimuth.core._types import BoolSeries, FloatSeries
from azimuth.core.primitives import EPS, percentrank, sma, stdev
from azimuth.core.ribbon import clip

__all__ = [
    "bandwidth",
    "bandwidth_pctile",
    "bollinger_bands",
    "bollinger_score",
    "percent_b",
    "squeeze",
]


def bollinger_bands(
    close: FloatSeries, length: int, mult: float
) -> tuple[FloatSeries, FloatSeries, FloatSeries]:
    """Return ``(basis, upper, lower)``. ``stdev`` is population, ddof=0."""
    basis = sma(close, length)
    sigma = stdev(close, length)
    return basis, basis + mult * sigma, basis - mult * sigma


def percent_b(close: FloatSeries, length: int, mult: float) -> FloatSeries:
    """%B, exported to Pine's ``x_pctb``. Denominator guarded at ``EPS``.

    Note %B is NOT clipped: it exceeds 1 above the upper band and goes negative
    below the lower one, which is exactly the "band ride" the trend branch reads
    as strength. Clipping happens once, on the score.
    """
    _, upper, lower = bollinger_bands(close, length, mult)
    return (close - lower) / (upper - lower).clip(lower=EPS)


def bandwidth(close: FloatSeries, length: int, mult: float) -> FloatSeries:
    """``(upper - lower) / basis``, guarded at ``EPS`` per ``AZIMUTH.pine:133``."""
    basis, upper, lower = bollinger_bands(close, length, mult)
    return (upper - lower) / basis.clip(lower=EPS)


def bandwidth_pctile(close: FloatSeries, length: int, mult: float, lookback: int) -> FloatSeries:
    """Percentrank of bandwidth, exported to Pine's ``x_bwpct``.

    See docs/11_FINDINGS.md finding 12: the strict-``<`` vs ``<=`` convention for
    ``ta.percentrank`` is disputed between docs/06 section 3 and TradingView's own
    reference. The fixture settles it.
    """
    return percentrank(bandwidth(close, length, mult), lookback)


def bollinger_score(
    close: FloatSeries, trending: BoolSeries, length: int, mult: float
) -> FloatSeries:
    """Regime-flipped Bollinger score, exported to Pine's ``x_bb``.

    ``docs/01`` section 2 on why the flip exists: "A fixed-polarity Bollinger rule
    is the classic reason confluence systems fail: mean-reversion logic applied
    inside a trend bleeds continuously."
    """
    pct_b = percent_b(close, length, mult)
    trend_score = (pct_b - 0.5) * 2.0
    return clip(trend_score.where(trending, -trend_score))


def squeeze(
    close: FloatSeries, length: int, mult: float, lookback: int, pctile: float
) -> BoolSeries:
    """Squeeze flag. See docs/11_FINDINGS.md finding 4 -- does not reach the score."""
    return (
        (bandwidth_pctile(close, length, mult, lookback) < pctile).fillna(value=False).astype(bool)
    )
