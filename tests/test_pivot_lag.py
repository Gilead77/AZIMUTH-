"""Regression: pivots confirm ``legs`` bars late, and that lag is reproduced.

``docs/06_PARITY_TESTS.md`` section 3 requires the confirmation lag to be asserted
explicitly. ``docs/01`` section 3.2 and ``docs/03`` section 2 are emphatic about
why: the lag is NOT repainting -- the value never changes once printed -- and
"improving" it away by centring the window is lookahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import pivot_high, pivot_low

#                   0    1    2    3     4    5    6    7    8
PEAK = pd.Series([1.0, 2.0, 3.0, 9.0, 3.0, 2.0, 1.0, 2.0, 3.0])
TROUGH = pd.Series([9.0, 8.0, 7.0, 1.0, 7.0, 8.0, 9.0, 8.0, 7.0])


def test_pivot_high_is_stamped_at_the_confirmation_bar():
    result = pivot_high(PEAK, 3, 3)
    assert result.iloc[6] == pytest.approx(9.0), "pivot at bar 3 confirms at bar 3+3"
    assert result.drop(index=6).isna().all(), "no other bar may carry a value"


def test_pivot_low_is_stamped_at_the_confirmation_bar():
    result = pivot_low(TROUGH, 3, 3)
    assert result.iloc[6] == pytest.approx(1.0)
    assert result.drop(index=6).isna().all()


@pytest.mark.parametrize("legs", [2, 3, 5, 8])
def test_confirmation_lag_equals_right_legs_exactly(legs: int):
    """docs/07 section 1 sweeps rsi.div_legs over 3-8. The lag must track it."""
    n = 2 * legs + 5
    src = pd.Series(np.arange(n, dtype=float))
    peak_at = legs + 1
    src.iloc[peak_at] = 1000.0

    result = pivot_high(src, legs, legs)
    assert result.iloc[peak_at + legs] == pytest.approx(1000.0)
    assert result.iloc[: peak_at + legs].isna().all(), (
        f"a value appeared before bar {peak_at + legs}, i.e. before the pivot could "
        "be confirmed -- that is lookahead"
    )


def test_reading_back_recovers_the_pivot_bar():
    """pine/AZIMUTH.pine:142-145 reads `rsi[divLb]` and `low[divLb]` at the
    confirmation bar to get back to the pivot. This is that contract."""
    legs = 3
    result = pivot_high(PEAK, legs, legs)
    confirmed_at = int(np.flatnonzero(result.notna())[0])
    assert PEAK.iloc[confirmed_at - legs] == pytest.approx(result.iloc[confirmed_at])


def test_centred_rolling_max_is_the_bug_this_guards_against():
    """The tempting 'fix': a centred window that stamps the pivot at its own bar.
    It reads `right` bars into the future."""
    legs = 3
    centred = PEAK.rolling(2 * legs + 1, center=True).max()

    # The centred form knows about the peak at bar 3 while standing on bar 3.
    assert centred.iloc[3] == pytest.approx(9.0)
    # The causal form does not.
    assert pd.isna(pivot_high(PEAK, legs, legs).iloc[3])


def test_no_pivot_when_the_flank_is_not_beaten():
    """A monotonic series has no interior pivots at all."""
    src = pd.Series(np.arange(20, dtype=float))
    assert pivot_high(src, 3, 3).isna().all()
    assert pivot_low(src, 3, 3).isna().all()
