"""RSI component with divergence bonus. Implements ``docs/01_SPEC_COMPONENTS.md`` section 3.

Base score is regime-dependent, centred on 50 rather than 30/70. The rationale in
docs/01 section 3.1 is worth restating: in an uptrend RSI oscillates roughly 40-80
and never reaches 30, so an "oversold buy" rule simply never fires where it would
have worked.

Divergence (section 3.2) is pivot-based with ``div_legs`` bars each side:

* bullish -- price lower low, RSI higher low  -> ``+div_bonus``
* bearish -- price higher high, RSI lower high -> ``-div_bonus``

Pivots confirm ``div_legs`` bars late. That is lag, NOT repainting: the value never
changes once printed. The lag must be reproduced exactly, not removed
(``docs/01`` section 3.2, ``docs/03`` section 2, ``docs/06`` section 3).

docs/11_FINDINGS.md finding 16: in the trend branch this is a momentum measure on
the same close series as the ribbon slope, and docs/02 section 1 already concedes
the two are partially collinear. Expect this component to be a strong ablation
candidate.
"""

from __future__ import annotations

from azimuth.core._types import BoolSeries, FloatSeries
from azimuth.core.primitives import pivot_high, pivot_low, rsi, valuewhen
from azimuth.core.ribbon import clip

__all__ = ["divergences", "rsi_base_score", "rsi_score"]

RSI_CENTRE = 50.0
"""``docs/01`` section 3.1: the centre is the 50-line, not 30/70."""


def rsi_base_score(rsi_values: FloatSeries, trending: BoolSeries, span: float) -> FloatSeries:
    """Regime-flipped distance from 50, clipped (section 3.1).

    Trend: ``clip((rsi - 50) / span)``. Range: ``clip((50 - rsi) / span)``.
    """
    if span <= 0.0:
        raise ValueError(f"rsi.span must be positive, got {span}")

    trend_score = (rsi_values - RSI_CENTRE) / span
    return clip(trend_score.where(trending, -trend_score))


def divergences(
    rsi_values: FloatSeries, high: FloatSeries, low: FloatSeries, legs: int
) -> tuple[BoolSeries, BoolSeries]:
    """Return ``(bullish, bearish)`` regular divergence flags (section 3.2).

    Transcribed from ``pine/AZIMUTH.pine:140-145``::

        plF     = not na(ta.pivotlow(rsi, divLb, divLb))
        bullDiv = plF and valuewhen(plF, rsi[divLb], 0) > valuewhen(plF, rsi[divLb], 1)
                      and valuewhen(plF, low[divLb], 0) < valuewhen(plF, low[divLb], 1)

    Flags are stamped at the CONFIRMATION bar, ``legs`` bars after the pivot. The
    ``[divLb]`` offsets read back from the confirmation bar to the pivot bar, which
    is why ``rsi`` and ``low`` are shifted by ``legs`` here: at the confirmation
    bar, ``shift(legs)`` holds the pivot bar's value.

    Bullish divergence is price making a LOWER low while RSI makes a HIGHER low --
    the two comparisons therefore point in opposite directions, and swapping them
    is the easiest way to get a plausible-looking but inverted signal.
    """
    rsi_at_pivot = rsi_values.shift(legs)
    low_at_pivot = low.shift(legs)
    high_at_pivot = high.shift(legs)

    pivot_low_confirmed = pivot_low(rsi_values, legs, legs).notna()
    pivot_high_confirmed = pivot_high(rsi_values, legs, legs).notna()

    # occurrence 0 is this pivot, 1 is the previous one (docs/03 section 7 item 6).
    bullish = (
        pivot_low_confirmed
        & (
            valuewhen(pivot_low_confirmed, rsi_at_pivot, 0)
            > valuewhen(pivot_low_confirmed, rsi_at_pivot, 1)
        )
        & (
            valuewhen(pivot_low_confirmed, low_at_pivot, 0)
            < valuewhen(pivot_low_confirmed, low_at_pivot, 1)
        )
    )
    bearish = (
        pivot_high_confirmed
        & (
            valuewhen(pivot_high_confirmed, rsi_at_pivot, 0)
            < valuewhen(pivot_high_confirmed, rsi_at_pivot, 1)
        )
        & (
            valuewhen(pivot_high_confirmed, high_at_pivot, 0)
            > valuewhen(pivot_high_confirmed, high_at_pivot, 1)
        )
    )

    return (
        bullish.fillna(value=False).astype(bool),
        bearish.fillna(value=False).astype(bool),
    )


def rsi_score(
    close: FloatSeries,
    high: FloatSeries,
    low: FloatSeries,
    trending: BoolSeries,
    length: int,
    span: float,
    legs: int,
    bonus: float,
) -> FloatSeries:
    """``clip(base + bullBonus - bearBonus)``, exported to Pine's ``x_rsi``.

    ``docs/07`` section 1 puts ``0.0`` in the sweep range for ``rsi.div_bonus``
    deliberately: it tests whether divergence adds anything at all.
    """
    rsi_values = rsi(close, length)
    base = rsi_base_score(rsi_values, trending, span)
    bullish, bearish = divergences(rsi_values, high, low, legs)

    adjusted = base + bullish.astype(float) * bonus - bearish.astype(float) * bonus
    return clip(adjusted)
