"""Composite score. Implements ``docs/02_SPEC_SCORING.md`` section 1.

::

    score = 100 * sum(w_i * s_i) / sum(w_i)        in [-100, +100]

Weights are HYPERPARAMETERS and must be swept, not tuned by eye. An equal-weight
configuration (1,1,1,1,1) is a mandatory baseline in every walk-forward: if the
tuned weights do not beat equal weights out of sample, use equal weights. docs/02
section 1 notes they usually do not.

Ribbon, HTF and correlation are NOT regime-flipped -- they are directional context
in both regimes. Only Bollinger and RSI flip (docs/02 section 2).
"""

from __future__ import annotations

from azimuth.config.schema import WeightsConfig
from azimuth.core._types import FloatSeries


def composite(
    ribbon: FloatSeries,
    bollinger: FloatSeries,
    rsi: FloatSeries,
    htf: FloatSeries,
    corr: FloatSeries,
    weights: WeightsConfig,
) -> FloatSeries:
    """Weighted composite in [-100, +100]. Denominator guarded at 1e-10."""
    raise NotImplementedError("M1 — docs/02_SPEC_SCORING.md section 1")


def component_correlation_matrix(
    ribbon: FloatSeries,
    bollinger: FloatSeries,
    rsi: FloatSeries,
    htf: FloatSeries,
    corr: FloatSeries,
) -> dict[tuple[str, str], float]:
    """Pairwise correlations between the five component scores.

    docs/11_FINDINGS.md finding 16, M1 diagnostic. Ribbon, Bollinger and RSI are
    all momentum/location measures on the same close series over comparable
    horizons, so the ablation outcome in docs/02 section 5 may be predictable
    before any backtest runs.

    If rho(ribbon, bollinger) and rho(ribbon, rsi) exceed ~0.6, state the expected
    ablation result IN the pre-registration as a prediction. A pre-registered
    prediction that comes true is far stronger evidence than the same observation
    made post hoc, and it costs nothing to make now.

    Descriptive statistic, not a performance metric -- permitted before parity.
    """
    raise NotImplementedError("M1 — docs/11_FINDINGS.md finding 16")
