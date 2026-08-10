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


def rsi_base_score(rsi: FloatSeries, trending: BoolSeries, span: float) -> FloatSeries:
    """Regime-flipped distance from 50, clipped (section 3.1)."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 3.1")


def divergences(
    rsi: FloatSeries, high: FloatSeries, low: FloatSeries, legs: int
) -> tuple[BoolSeries, BoolSeries]:
    """Return ``(bullish, bearish)`` regular divergence flags (section 3.2).

    Flags are stamped at the CONFIRMATION bar, ``legs`` bars after the pivot.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 3.2")


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
    """``clip(base + bullBonus - bearBonus)``, exported to Pine's ``x_rsi``."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 3")
