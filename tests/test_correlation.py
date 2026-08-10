"""Regression: ``ta.correlation`` is rolling Pearson and matches pandas.

``docs/06_PARITY_TESTS.md`` section 3 records this as the one primitive where the
obvious pandas call is correct. The test exists anyway, because "matches" is a
claim that should be checked rather than assumed -- and because the component
built on it has a separate, non-parity problem worth restating.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import correlation


def test_perfect_positive_correlation():
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    y = pd.Series([2.0, 4.0, 6.0, 8.0, 10.0])
    assert correlation(x, y, 5).iloc[4] == pytest.approx(1.0)


def test_perfect_negative_correlation():
    """Negative rho flips the vote, which docs/01 section 5 notes is exactly right
    for DXY against most risk assets."""
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    y = pd.Series([10.0, 8.0, 6.0, 4.0, 2.0])
    assert correlation(x, y, 5).iloc[4] == pytest.approx(-1.0)


def test_matches_pandas_rolling_corr():
    rng = np.random.default_rng(5)
    x = pd.Series(rng.normal(0, 1, 200))
    y = pd.Series(rng.normal(0, 1, 200))

    ours = correlation(x, y, 60)
    theirs = x.rolling(60).corr(y)
    pd.testing.assert_series_equal(ours, theirs)


def test_na_until_the_window_fills():
    x = pd.Series(np.arange(10, dtype=float))
    y = pd.Series(np.arange(10, dtype=float) ** 2)
    assert correlation(x, y, 5).iloc[:4].isna().all()


def test_structural_zero_returns_collapse_the_effective_sample():
    """Not a parity failure -- a meaning failure. docs/11_FINDINGS.md finding 3.

    A reference on a different trading calendar is forward-filled across bars it
    did not trade, so its return series is mostly structural zeros. Pine and
    pandas agree on the resulting rho to 1e-15; it is still built on a fraction of
    the observations `length` implies. This test documents the magnitude.
    """
    rng = np.random.default_rng(13)
    n = 600
    own = pd.Series(rng.normal(0, 1, n))

    # A reference trading ~6.5h in 24: roughly 73% of bars carry no new information.
    ref = own * 0.8 + rng.normal(0, 0.6, n)
    traded = rng.random(n) < 0.27
    ref_stale = ref.where(traded).ffill().bfill()
    ref_returns = ref_stale.diff().fillna(0.0)

    rho_clean = correlation(own.diff().fillna(0.0), ref.diff().fillna(0.0), 60)
    rho_stale = correlation(own.diff().fillna(0.0), ref_returns, 60)

    # Both are computable and neither is NaN -- that is the trap. The gate on
    # |rho| >= corr.min_abs_rho fires on a number backed by ~16 real observations.
    assert rho_stale.notna().sum() > 0
    assert abs(rho_clean.mean() - rho_stale.mean()) > 0.05, (
        "staleness should visibly move rho; if it does not, this fixture no longer "
        "demonstrates finding 3"
    )
