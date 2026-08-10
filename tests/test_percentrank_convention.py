"""Regression: ``ta.percentrank`` excludes the current bar and counts one way.

``docs/06_PARITY_TESTS.md`` section 3 specifies: percentage of the prior ``len``
values STRICTLY LESS THAN the current one, EXCLUDING the current bar, and
explicitly warns against ``rank(pct=True)``.

OPEN QUESTION -- docs/11_FINDINGS.md finding 12. TradingView's own reference for
``ta.percentrank`` says "less than or EQUAL to". The two disagree on ties. The
spec wins for now (it is authoritative for this project); the committed Pine
fixture settles it empirically, and flipping ``PCTRANK_STRICT`` is the whole
change. This file pins both readings so the flip is a one-line diff with visible
consequences rather than a silent behaviour change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.core import primitives
from azimuth.core.primitives import percentrank


def test_current_bar_is_excluded_from_its_own_window():
    """[1,2,3,4,5] with length 4: the last bar ranks against 1,2,3,4 -- all four
    below it -- giving 100. Including the current bar would rank 5 against
    2,3,4,5 and give 75."""
    src = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert percentrank(src, 4).iloc[4] == pytest.approx(100.0)


def test_first_length_bars_are_na():
    src = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = percentrank(src, 4)
    assert result.iloc[:4].isna().all(), "no window exists yet -- must be na, never 0"


def test_ties_distinguish_the_two_conventions():
    """The bar that decides finding 12. Window [10,20,25,40], current 25."""
    src = pd.Series([10.0, 20.0, 25.0, 40.0, 25.0])

    strict = percentrank(src, 4, strict=True).iloc[4]
    inclusive = percentrank(src, 4, strict=False).iloc[4]

    assert strict == pytest.approx(50.0), "counts 10 and 20"
    assert inclusive == pytest.approx(75.0), "counts 10, 20 and the tied 25"
    assert strict != inclusive, "if these ever agree the fixture cannot settle finding 12"


def test_default_follows_docs_06_not_tradingviews_wording():
    assert primitives.PCTRANK_STRICT is True
    src = pd.Series([10.0, 20.0, 25.0, 40.0, 25.0])
    assert percentrank(src, 4).iloc[4] == pytest.approx(50.0)


def test_rank_pct_is_not_a_substitute():
    """docs/06 section 3: 'do not use rank(pct=True)'. It ranks within the window
    INCLUDING the current bar and averages ties, which is a third convention
    again."""
    src = pd.Series([10.0, 20.0, 25.0, 40.0, 25.0])
    naive = src.rolling(4).apply(lambda w: w.rank(pct=True).iloc[-1] * 100.0, raw=False)

    assert naive.iloc[4] != pytest.approx(percentrank(src, 4).iloc[4])


def test_output_is_bounded_and_quantised_to_the_window():
    """With `length` prior observations the only attainable values are multiples
    of 100/length. A result off that lattice means the window is the wrong size."""
    rng = np.random.default_rng(3)
    src = pd.Series(rng.normal(0, 1, 300))
    length = 20

    values = percentrank(src, length).dropna().to_numpy()
    assert values.min() >= 0.0 and values.max() <= 100.0
    np.testing.assert_allclose(values, np.round(values / (100.0 / length)) * (100.0 / length))
