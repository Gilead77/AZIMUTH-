"""Cross-asset correlation. Implements ``docs/01_SPEC_COMPONENTS.md`` section 5.

Correlation is computed on LOG RETURNS, never prices: price-level correlation
between two trending series is close to meaningless (spurious regression)::

    r_own   = ln(close / close[1])
    r_ref   = ln(ref / ref[1])
    rho_j   = correlation(r_own, r_ref, 60)
    trend_j = sign(ref - EMA(ref, 50))
    contrib_j = |rho_j| >= rho_min ? rho_j * trend_j : 0
    corrScore = clip(sum(contrib_j) / count(active j))

Negative rho flips the vote, which is correct for DXY against most risk assets.

TWO CAVEATS, both in docs/11_FINDINGS.md:

finding 3 -- a reference on a different trading calendar (DXY 24/5, SPX ~6.5h/day)
forward-fills across bars the reference did not trade, injecting structural zero
returns. On a 1H BTC chart against SPX, roughly 73% of bars carry ``r_ref = 0`` and
the 60-bar rho rests on ~16 real observations. Pine and pandas forward-fill
identically, so parity PASSES on a number that carries almost no information.

finding 16 -- ``rho`` measures CONTEMPORANEOUS return correlation, but the
component uses it to weight a claim about the reference's trend predicting our
next-bar return. Correlation is not lead-lag. This is the component most likely to
fail the ablation in docs/02 section 5.
"""

from __future__ import annotations

from collections.abc import Sequence

from azimuth.core._types import FloatSeries


def log_returns(close: FloatSeries) -> FloatSeries:
    """``ln(close / close[1])``. Denominator guarded at 1e-10, matching Pine."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 5")


def reference_contribution(
    own_returns: FloatSeries,
    ref_close: FloatSeries,
    length: int,
    min_abs_rho: float,
    ref_ema: int,
) -> tuple[FloatSeries, FloatSeries, FloatSeries]:
    """Return ``(rho, contribution, active)`` for one reference."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 5")


def correlation_score(
    close: FloatSeries,
    refs: Sequence[FloatSeries],
    length: int,
    min_abs_rho: float,
    ref_ema: int,
) -> FloatSeries:
    """Aggregate contribution over active references. Pine's ``x_corr``."""
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 5")


def crowding(refs_rho: Sequence[FloatSeries]) -> FloatSeries:
    """``mean(|rho_j|)`` -- a RISK measure, not a directional one.

    High crowding means everything is one trade. Feeds position sizing, never the
    directional score (docs/01 section 5).

    docs/11_FINDINGS.md finding 0: the Pine implementation had an operator
    precedence bug here that pinned the denominator at 1. Fixed in commit 1; this
    implementation must match the FIXED Pine, i.e. divide by the count of enabled
    references.
    """
    raise NotImplementedError("M1 — docs/01_SPEC_COMPONENTS.md section 5")


def rho_stability(own: FloatSeries, ref: FloatSeries, length: int) -> tuple[float, float]:
    """Rho over each half of the sample, for ``--check-rho-stability``.

    docs/07 section 5: if the sign flips between halves, DROP that reference.
    Unstable correlations actively degrade the score -- they cast confident votes
    in the wrong direction.
    """
    raise NotImplementedError("M1 — docs/07_PARAMETERS.md section 5")
