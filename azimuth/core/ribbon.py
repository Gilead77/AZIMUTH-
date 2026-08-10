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

from azimuth.core._types import BoolSeries, FloatSeries


def ribbon_order(close: FloatSeries, lengths: Sequence[int]) -> FloatSeries:
    """Ordinal stacking score in [-1, +1] (section 1.1)."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 1.1")


def ribbon_slope(close: FloatSeries, atr: FloatSeries, length: int, lookback: int) -> FloatSeries:
    """ATR-normalised slope of the 4th ribbon EMA, clipped (section 1.2)."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 1.2")


def ribbon_score(
    close: FloatSeries,
    atr: FloatSeries,
    lengths: Sequence[int],
    slope_lookback: int,
) -> FloatSeries:
    """Composite ribbon score, ``clip(0.65*order + 0.35*slope)`` (section 1.3).

    Exported to Pine's ``x_ribbon``; parity tolerance 1e-6.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 1.3")


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
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 1.4")
