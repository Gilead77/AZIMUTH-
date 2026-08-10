"""Regression: Pine seeds EMA with an SMA; ``ewm(adjust=False)`` does not.

``docs/06_PARITY_TESTS.md`` section 3, and named explicitly in CLAUDE.md's known
traps. This is the single most expensive primitive to get wrong, because the
error DECAYS rather than failing: at ``(1-alpha)^n`` a 233-period EMA is still
visibly off hundreds of bars after the burn-in that was supposed to hide it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core.primitives import ema

# alpha = 2/(3+1) = 0.5, so every step is a clean average and the fixture can be
# verified by hand without floating-point argument.
SRC = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
LENGTH = 3

# seed  = SMA(1,2,3) = 2.0            at index 2
# i=3   = 0.5*4 + 0.5*2 = 3.0
# i=4   = 0.5*5 + 0.5*3 = 4.0  ... and so on
EXPECTED = [np.nan, np.nan, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_ema_matches_hand_computed_pine_values():
    result = ema(SRC, LENGTH)
    assert result.iloc[:2].isna().all(), "EMA must be na before `length` bars exist"
    np.testing.assert_allclose(result.iloc[2:], EXPECTED[2:], rtol=0, atol=1e-12)


def test_naive_ewm_gives_a_different_answer():
    """The whole point of the regression. If this ever stops differing, the test
    above has stopped proving anything."""
    naive = SRC.ewm(span=LENGTH, adjust=False).mean()

    # ewm seeds with the FIRST OBSERVATION: 1.0, 1.5, 2.25, ...
    assert naive.iloc[2] == pytest.approx(2.25)
    assert ema(SRC, LENGTH).iloc[2] == pytest.approx(2.0)
    assert naive.iloc[2] != pytest.approx(ema(SRC, LENGTH).iloc[2])


def test_naive_ewm_emits_values_during_the_seeding_window():
    """A subtler symptom: ewm produces numbers where Pine produces na, so a
    burn-in that trims `length` bars trims the wrong ones."""
    naive = SRC.ewm(span=LENGTH, adjust=False).mean()
    assert naive.iloc[:2].notna().all(), "ewm fills the seeding window"
    assert ema(SRC, LENGTH).iloc[:2].isna().all(), "Pine leaves it na"


def test_seed_uses_only_the_first_length_bars():
    """The seed must not consult the whole series -- that would be lookahead, not
    merely a seeding difference."""
    src = pd.Series([1.0] * 3 + [1000.0] * 30)
    assert ema(src, 3).iloc[2] == pytest.approx(1.0)


def test_error_persists_far_beyond_a_naive_burn_in():
    """Quantifies why this matters: with length 233, the seeding error is still
    material long after the 283-bar burn-in of docs/06 section 2."""
    rng = np.random.default_rng(7)
    src = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, 1200)))

    ours = ema(src, 233)
    naive = src.ewm(span=233, adjust=False).mean()

    at_burn_in = abs(ours.iloc[283] - naive.iloc[283])
    assert at_burn_in > 1e-6, (
        f"seeding error at the burn-in boundary is {at_burn_in:.3e}, which would "
        "break the 1e-6 parity gate -- this is the bug the test exists to catch"
    )
