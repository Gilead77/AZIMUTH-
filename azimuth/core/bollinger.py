"""Bollinger component. Implements ``docs/01_SPEC_COMPONENTS.md`` section 2.

::

    basis = SMA(close, 20);  sigma = stdev(close, 20)   # POPULATION, ddof=0
    %B        = (close - lower) / (upper - lower)
    bandwidth = (upper - lower) / basis
    bwPct     = percentrank(bandwidth, 200)

Regime-dependent polarity (``docs/01`` section 2, ``docs/02`` section 2) -- the
single most important design decision in AZIMUTH:

===========  ==========================  ====================
Regime       Logic                       Score
===========  ==========================  ====================
Trend        band ride = strength        ``clip((%B - 0.5)*2)``
Range        band tag = exhaustion       ``clip((0.5 - %B)*2)``
===========  ==========================  ====================

Two traps:

* ``ta.stdev`` is population (``ddof=0``); ``pandas.rolling().std()`` defaults to
  ``ddof=1`` (``docs/06`` section 3). Regression test: ``tests/test_stdev_ddof.py``.
* docs/11_FINDINGS.md finding 1: the regime boolean that flips this sign has no
  hysteresis, so a single flicker moves the composite by up to ~74 points -- more
  than ``signal.enter``.
"""

from __future__ import annotations

from azimuth.core._types import BoolSeries, FloatSeries


def bollinger_bands(
    close: FloatSeries, length: int, mult: float
) -> tuple[FloatSeries, FloatSeries, FloatSeries]:
    """Return ``(basis, upper, lower)``. ``stdev`` is population, ddof=0."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 2")


def percent_b(close: FloatSeries, length: int, mult: float) -> FloatSeries:
    """%B, exported to Pine's ``x_pctb``. Denominator guarded at 1e-10."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 2")


def bandwidth_pctile(close: FloatSeries, length: int, mult: float, lookback: int) -> FloatSeries:
    """Percentrank of bandwidth, exported to Pine's ``x_bwpct``.

    See docs/11_FINDINGS.md finding 12: the strict-``<`` vs ``<=`` convention for
    ``ta.percentrank`` is disputed between docs/06 section 3 and TradingView's own
    reference. The fixture settles it.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 2")


def bollinger_score(
    close: FloatSeries, trending: BoolSeries, length: int, mult: float
) -> FloatSeries:
    """Regime-flipped Bollinger score, exported to Pine's ``x_bb``."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 2")


def squeeze(
    close: FloatSeries, length: int, mult: float, lookback: int, pctile: float
) -> BoolSeries:
    """Squeeze flag. See docs/11_FINDINGS.md finding 4 -- does not reach the score."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 2")
