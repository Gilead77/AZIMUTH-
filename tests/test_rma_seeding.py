"""Regression: ``ta.rma`` is Wilder's smoother, alpha = 1/length, SMA-seeded.

``docs/06_PARITY_TESTS.md`` section 3. RMA sits underneath RSI, ATR and DMI, so a
seeding error here propagates into three of the five components at once.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import rma

SRC = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
LENGTH = 3  # alpha = 1/3

# seed = SMA(1,2,3) = 2.0 at index 2
# i=3  = (1/3)*4 + (2/3)*2       = 2.666666...
# i=4  = (1/3)*5 + (2/3)*2.66667 = 3.444444...
# i=5  = (1/3)*6 + (2/3)*3.44444 = 4.296296...
EXPECTED = [2.0, 8 / 3, 31 / 9, 116 / 27]


def test_rma_matches_hand_computed_pine_values():
    result = rma(SRC, LENGTH)
    assert result.iloc[:2].isna().all()
    np.testing.assert_allclose(result.iloc[2:], EXPECTED, rtol=0, atol=1e-12)


def test_alpha_is_one_over_length_not_two_over_length_plus_one():
    """Wilder's smoother is not an EMA of the same period. Confusing them is the
    classic ADX bug flagged in docs/06 section 3."""
    from azimuth.core.primitives import ema

    assert rma(SRC, LENGTH).iloc[5] != pytest.approx(ema(SRC, LENGTH).iloc[5])

    # An RMA of length n equals an EMA of span 2n-1, which is the identity people
    # reach for -- but only once both have been seeded the same way.
    assert rma(SRC, LENGTH).iloc[2] == pytest.approx(ema(SRC, LENGTH).iloc[2])


def test_naive_ewm_gives_a_different_answer():
    naive = SRC.ewm(alpha=1 / LENGTH, adjust=False).mean()
    assert naive.iloc[:2].notna().all(), "ewm fills the seeding window"
    assert naive.iloc[2] != pytest.approx(rma(SRC, LENGTH).iloc[2])


def test_leading_nan_is_skipped_when_seeding():
    """RSI feeds RMA a series whose first bar is na (no previous close). Pine
    seeds from bars 1..length, not 0..length-1, and so must we."""
    src = pd.Series([np.nan, 1.0, 2.0, 3.0, 4.0])
    result = rma(src, 3)

    assert result.iloc[:3].isna().all(), "seed cannot land before 3 real observations"
    assert result.iloc[3] == pytest.approx(2.0), "seed = mean(1,2,3), skipping the na"


def test_interior_nan_is_refused_rather_than_silently_bridged():
    """Recursion across a gap is undefined; docs/04 section 5 guarantees OHLC has
    no NaNs, so this indicates a bug upstream and must not be papered over."""
    src = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])
    with pytest.raises(ValueError, match="interior NaN"):
        rma(src, 3)
