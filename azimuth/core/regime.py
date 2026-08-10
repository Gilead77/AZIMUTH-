"""Regime gate. Implements ``docs/01_SPEC_COMPONENTS.md`` section 6.

Two independent estimators, OR-combined::

    ER  = |close - close[n]| / sum(|close - close[1]|)  over n=20   -> ER > 0.30
    [+DI, -DI, ADX] = DMI(14, 14)                                   -> ADX > 20
    trending = (ER > 0.30) OR (ADX > 20)

``regime.mode`` forces trend-only or range-only. docs/01 section 6 is explicit that
the harness runs all three modes as SEPARATE HYPOTHESES and does not pick the best.

docs/11_FINDINGS.md finding 1 -- the most consequential open question in the
design. This boolean inverts the sign of both ``bbScore`` and ``rsiScore``. With
default weights a single flip moves the composite by up to

    2 * (0.8 + 0.8) / 4.3 * 100  ~=  74 points

with no price movement at all, which exceeds ``signal.enter = 45``. docs/02
section 3 applies a hysteresis dead band to the score for exactly this reason but
leaves the gate that inverts the score unprotected.

The M1 diagnostics below measure it. They are descriptive statistics of the signal,
not performance metrics, so they may be computed before the parity gate lifts.
"""

from __future__ import annotations

from azimuth.config.schema import RegimeMode
from azimuth.core._types import BoolSeries, FloatSeries


def efficiency_ratio(close: FloatSeries, length: int) -> FloatSeries:
    """Kaufman efficiency ratio: directional travel / total travel. Pine ``x_er``."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 6")


def trending(
    high: FloatSeries,
    low: FloatSeries,
    close: FloatSeries,
    er_length: int,
    er_threshold: float,
    adx_length: int,
    adx_threshold: float,
    mode: RegimeMode = "adaptive",
) -> BoolSeries:
    """The regime boolean. OR of the ER and ADX conditions, or forced by ``mode``."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 6")


def regime_diagnostics(trending_flags: BoolSeries) -> dict[str, float]:
    """Duty cycle and flip statistics for the regime gate.

    docs/11_FINDINGS.md finding 1, M1 diagnostic. Returns duty cycle (fraction of
    bars trending), flip count, flips per 1000 bars, and mean run length of each
    state.

    Pre-committed reading: if range mode occupies < 20% of bars, OR mean run length
    is < 5 bars, record in the pre-registration that the polarity switch is
    expected to act as noise amplification rather than adaptation.

    This is a descriptive statistic of the signal, NOT a performance metric --
    permitted before the parity gate lifts (CLAUDE.md rule 2).
    """
    raise NotImplementedError("M1 — docs/11_FINDINGS.md finding 1")
