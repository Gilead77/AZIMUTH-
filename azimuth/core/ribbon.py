"""EMA ribbon component. Implements ``docs/01_SPEC_COMPONENTS.md`` section 1.

Score construction::

    bullPairs = sum over i in 0..6 of [ EMA_i > EMA_{i+1} ]
    ribOrder  = (bullPairs / 7) * 2 - 1                       in [-1, +1]
    ribSlope  = clip((EMA_34 - EMA_34[k]) / (ATR_14 * k))     k = slope_lookback
    ribScore  = clip(0.65 * ribOrder + 0.35 * ribSlope)

``ribOrder`` is deliberately ordinal rather than distance-based: scale-free, and it
survives regime changes in volatility.

The ATR in the slope denominator is ``ta.atr``, i.e. RMA of true range, which is
SMA-seeded (``docs/06_PARITY_TESTS.md`` section 3). If ``x_ribbon`` fails parity,
suspect ATR/RMA seeding before suspecting the EMA.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np
import pandas as pd

from azimuth.core._types import BoolSeries, FloatSeries
from azimuth.core.primitives import EPS, ema, percentrank

__all__ = [
    "ORDER_WEIGHT",
    "SLOPE_WEIGHT",
    "clip",
    "ribbon_compression",
    "ribbon_emas",
    "ribbon_order",
    "ribbon_score",
    "ribbon_slope",
    "ribbon_width",
]

ORDER_WEIGHT = 0.65
SLOPE_WEIGHT = 0.35
"""``docs/01`` section 1.3. Not swept -- they are part of the component's
definition, not hyperparameters, and ``docs/07`` section 1 does not list them."""

SLOPE_EMA_INDEX = 3
"""``pine/AZIMUTH.pine:123`` takes the slope of ``e4``, the FOURTH ribbon EMA.

``docs/01`` section 1.2 calls it "EMA_34" because 34 is the fourth default
Fibonacci length. It is the position that is fixed, not the number -- swapping the
ribbon preset must move the slope with it, or the two preset sets in ``docs/07``
section 1 would not be comparable.
"""


def clip(x: FloatSeries) -> FloatSeries:
    """``clip(x) = max(-1, min(1, x))`` from ``docs/01`` preamble."""
    return x.clip(lower=-1.0, upper=1.0)


def ribbon_emas(close: FloatSeries, lengths: Sequence[int]) -> list[FloatSeries]:
    """The ribbon EMAs, in the order given. Pine ``e1..e8``."""
    return [ema(close, length) for length in lengths]


def ribbon_order(close: FloatSeries, lengths: Sequence[int]) -> FloatSeries:
    """Ordinal stacking score in [-1, +1] (section 1.1).

    Counts adjacent pairs in bullish order and maps 0..7 onto -1..+1. A perfect
    bullish fan gives +1, a perfect bearish fan -1, a tangle about 0.

    Pine's comparison is strict ``>`` (``AZIMUTH.pine:120``), so exactly equal
    adjacent EMAs count as bearish. That only happens on perfectly flat price,
    where the score is meaningless anyway, but it is reproduced rather than
    "improved" to a tolerance-based comparison.
    """
    emas = ribbon_emas(close, lengths)
    n_pairs = len(emas) - 1
    if n_pairs < 1:
        raise ValueError(f"need at least 2 ribbon lengths, got {len(lengths)}")

    bull_pairs = pd.Series(0.0, index=close.index, dtype=float)
    valid = pd.Series(True, index=close.index)
    for fast, slow in pairwise(emas):
        bull_pairs = bull_pairs + (fast > slow).astype(float)
        valid &= fast.notna() & slow.notna()

    order = (bull_pairs / n_pairs) * 2.0 - 1.0
    return order.where(valid)


def ribbon_slope(close: FloatSeries, atr: FloatSeries, length: int, lookback: int) -> FloatSeries:
    """ATR-normalised slope of the ribbon's 4th EMA, clipped (section 1.2).

    ``clip((e - e[k]) / max(atr * k, EPS))``. Normalising by ATR makes the slope
    comparable across instruments and timeframes; the ``EPS`` guard mirrors
    ``math.max(atr * ribSlopeLb, 1e-10)`` at ``pine/AZIMUTH.pine:123``.
    """
    if lookback < 1:
        raise ValueError(f"slope lookback must be >= 1, got {lookback}")

    e = ema(close, length)
    denominator = (atr * lookback).clip(lower=EPS)
    return clip((e - e.shift(lookback)) / denominator)


def ribbon_score(
    close: FloatSeries,
    atr: FloatSeries,
    lengths: Sequence[int],
    slope_lookback: int,
) -> FloatSeries:
    """Composite ribbon score, ``clip(0.65*order + 0.35*slope)`` (section 1.3).

    Exported to Pine's ``x_ribbon``; parity tolerance 1e-6.
    """
    order = ribbon_order(close, lengths)
    slope = ribbon_slope(close, atr, lengths[SLOPE_EMA_INDEX], slope_lookback)
    return clip(ORDER_WEIGHT * order + SLOPE_WEIGHT * slope)


def ribbon_width(close: FloatSeries, lengths: Sequence[int]) -> FloatSeries:
    """``(max(EMAs) - min(EMAs)) / close`` (section 1.4)."""
    emas = ribbon_emas(close, lengths)
    stacked = pd.concat(emas, axis=1)
    # skipna=False so the warm-up stays NaN rather than reporting the width of
    # whichever EMAs happen to have seeded already.
    spread = stacked.max(axis=1, skipna=False) - stacked.min(axis=1, skipna=False)
    return spread / close.replace(0.0, np.nan)


def ribbon_compression(
    close: FloatSeries,
    lengths: Sequence[int],
    lookback: int,
    pctile: float,
) -> BoolSeries:
    """Compression flag: setup, not direction (section 1.4).

    NOTE (docs/11_FINDINGS.md finding 4): this flag never reaches the composite
    score or the regime gate in ``pine/AZIMUTH.pine`` -- it drives only ``bgcolor``,
    the dashboard and one ``alertcondition``. Its two parameters therefore cannot
    move any performance metric, and sweeping them adds trials to N for nothing.
    """
    ranked = percentrank(ribbon_width(close, lengths), lookback)
    return (ranked < pctile).fillna(value=False).astype(bool)
