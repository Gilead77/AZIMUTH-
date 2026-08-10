"""Component scores against hand-computed fixtures.

Each section mirrors a subsection of ``docs/01_SPEC_COMPONENTS.md``. HTF has its
own file (``test_htf_alignment.py``) and so does the state machine
(``test_state_machine.py``); this covers the other five.

Fixtures are small enough to check on paper. The regime-polarity tests are the
ones to read carefully -- ``docs/01`` section 2 calls that flip "the single most
important design decision in AZIMUTH", and getting its sign backwards produces a
system that trades confidently in the wrong direction in one of the two regimes.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from azimuth.config.schema import WeightsConfig
from azimuth.core import bollinger, correlation, regime, ribbon, rsi_mod, score

RISING = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def _flags(values: list[bool]) -> pd.Series:
    return pd.Series(values, dtype=bool)


# ── 1. ribbon (docs/01 section 1) ────────────────────────────────────────────────


def test_clip_is_the_docs_01_preamble_definition():
    assert ribbon.clip(_series([-5.0, -1.0, 0.0, 1.0, 5.0])).tolist() == [
        -1.0,
        -1.0,
        0.0,
        1.0,
        1.0,
    ]


def test_ribbon_order_is_plus_one_for_a_perfect_bullish_fan():
    """All adjacent pairs in bullish order. Rising price puts the fast EMAs above
    the slow ones."""
    close = pd.Series(np.arange(1.0, 61.0))
    order = ribbon.ribbon_order(close, (2, 3, 5, 8))
    assert order.iloc[-1] == pytest.approx(1.0)


def test_ribbon_order_is_minus_one_for_a_perfect_bearish_fan():
    close = pd.Series(np.arange(60.0, 0.0, -1.0))
    order = ribbon.ribbon_order(close, (2, 3, 5, 8))
    assert order.iloc[-1] == pytest.approx(-1.0)


def test_ribbon_order_maps_pair_count_onto_minus_one_to_plus_one():
    """(bullPairs / n_pairs) * 2 - 1. With 3 pairs, 0..3 maps to -1, -1/3, 1/3, 1."""
    close = pd.Series(np.arange(1.0, 61.0))
    order = ribbon.ribbon_order(close, (2, 3, 5, 8)).dropna()

    lattice = np.array([-1.0, -1 / 3, 1 / 3, 1.0])
    for value in order.unique():
        assert np.min(np.abs(lattice - value)) < 1e-12, f"{value} is off the 3-pair lattice"


def test_ribbon_order_is_nan_until_the_slowest_ema_seeds():
    close = pd.Series(np.arange(1.0, 20.0))
    order = ribbon.ribbon_order(close, (2, 3, 5, 8))
    assert order.iloc[:7].isna().all(), "the 8-period EMA seeds at index 7"
    assert pd.notna(order.iloc[7])


def test_ribbon_score_weights_order_and_slope_65_35():
    """docs/01 section 1.3. With a perfect fan and a saturated slope, both terms
    are +1 and the composite is 0.65 + 0.35 = 1.0."""
    assert pytest.approx(1.0) == ribbon.ORDER_WEIGHT + ribbon.SLOPE_WEIGHT

    close = pd.Series(np.arange(1.0, 121.0))
    atr = pd.Series(0.01, index=close.index)  # tiny ATR -> slope saturates at +1
    result = ribbon.ribbon_score(close, atr, (2, 3, 5, 8), 3)
    assert result.iloc[-1] == pytest.approx(1.0)


def test_ribbon_slope_is_atr_normalised():
    """A slope of exactly one ATR per bar gives (e - e[k]) / (atr*k) = 1."""
    close = pd.Series(np.arange(0.0, 100.0))  # +1 per bar
    atr = pd.Series(1.0, index=close.index)
    slope = ribbon.ribbon_slope(close, atr, 2, 5)
    assert slope.iloc[-1] == pytest.approx(1.0)


def test_ribbon_slope_uses_the_fourth_length_not_the_literal_34():
    """docs/01 section 1.2 says "EMA_34" because 34 is the fourth default. It is
    the POSITION that is fixed -- a different ribbon preset must move the slope
    with it, or the presets in docs/07 section 1 are not comparable."""
    assert ribbon.SLOPE_EMA_INDEX == 3

    rng = np.random.default_rng(17)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, 300)))
    atr = pd.Series(2.0, index=close.index)

    # Same ribbon except for the FOURTH length. If the slope tracked a literal 34
    # (or any fixed length), these two would be identical.
    a = ribbon.ribbon_score(close, atr, (2, 3, 5, 8, 13, 21, 34, 55), 5)
    b = ribbon.ribbon_score(close, atr, (2, 3, 5, 40, 13000, 21000, 34000, 55000), 5)
    assert not a.dropna().equals(b.dropna())

    # And the slope term really is the 4th EMA's, not the 1st or last.
    lengths = (2, 3, 5, 8, 13, 21, 34, 55)
    direct = ribbon.ribbon_slope(close, atr, lengths[3], 5)
    assert direct.equals(ribbon.ribbon_slope(close, atr, 8, 5))


# ── 2. bollinger (docs/01 section 2) ─────────────────────────────────────────────

# close = [1,2,3,4,5], length 5, mult 1:
#   basis = 3, population variance = 10/5 = 2, sigma = sqrt(2)
#   upper = 3 + sqrt(2), lower = 3 - sqrt(2)
#   %B    = (5 - (3-sqrt2)) / (2*sqrt2) = (2 + sqrt2) / (2*sqrt2)
_SIGMA = math.sqrt(2.0)
_PCT_B = (2.0 + _SIGMA) / (2.0 * _SIGMA)


def test_bollinger_bands_use_population_sigma():
    basis, upper, lower = bollinger.bollinger_bands(RISING, 5, 1.0)

    assert basis.iloc[4] == pytest.approx(3.0)
    assert upper.iloc[4] == pytest.approx(3.0 + _SIGMA)
    assert lower.iloc[4] == pytest.approx(3.0 - _SIGMA)


def test_percent_b_is_not_clipped():
    """%B above 1 is the "band ride" the trend branch reads as strength. Clipping
    it here would flatten exactly the signal the component is built on."""
    assert bollinger.percent_b(RISING, 5, 1.0).iloc[4] == pytest.approx(_PCT_B)
    assert _PCT_B > 1.0


def test_bandwidth_is_width_over_basis():
    assert bollinger.bandwidth(RISING, 5, 1.0).iloc[4] == pytest.approx(2.0 * _SIGMA / 3.0)


def test_bollinger_polarity_flips_with_the_regime():
    """docs/01 section 2 and docs/02 section 2 -- THE design decision.

    Trend: band ride = strength.  Range: band tag = exhaustion. Same bar, same
    %B, opposite sign.
    """
    trend = bollinger.bollinger_score(RISING, _flags([True] * 5), 5, 1.0)
    range_ = bollinger.bollinger_score(RISING, _flags([False] * 5), 5, 1.0)

    assert trend.iloc[4] == pytest.approx(1.0), "clip((%B-0.5)*2) saturates high"
    assert range_.iloc[4] == pytest.approx(-1.0), "clip((0.5-%B)*2) saturates low"
    assert trend.iloc[4] == pytest.approx(-range_.iloc[4])


def test_polarity_can_flip_bar_to_bar_within_one_series():
    """finding 1's mechanism in miniature: the same %B produces opposite scores on
    adjacent bars purely because the regime boolean flickered."""
    flags = _flags([True, False, True, False, True])
    scored = bollinger.bollinger_score(RISING, flags, 5, 1.0)
    unflipped = bollinger.bollinger_score(RISING, _flags([True] * 5), 5, 1.0)

    assert scored.iloc[4] == pytest.approx(unflipped.iloc[4])
    assert scored.iloc[3] != pytest.approx(unflipped.iloc[3])


def test_squeeze_is_a_boolean_and_never_na():
    result = bollinger.squeeze(pd.Series(np.arange(1.0, 60.0)), 5, 2.0, 20, 20.0)
    assert result.dtype == bool
    assert result.notna().all()


# ── 3. RSI (docs/01 section 3) ───────────────────────────────────────────────────


def test_rsi_base_score_is_centred_on_fifty_not_thirty_seventy():
    """docs/01 section 3.1: in an uptrend RSI oscillates roughly 40-80 and never
    reaches 30, so an 'oversold buy' rule never fires where it would have worked."""
    rsi_values = _series([50.0, 75.0, 25.0, 60.0])
    trending = _flags([True] * 4)

    result = rsi_mod.rsi_base_score(rsi_values, trending, 25.0)
    assert result.iloc[0] == pytest.approx(0.0), "50 is neutral"
    assert result.iloc[1] == pytest.approx(1.0), "50 + span -> +1"
    assert result.iloc[2] == pytest.approx(-1.0)
    assert result.iloc[3] == pytest.approx(0.4)


def test_rsi_polarity_flips_with_the_regime():
    rsi_values = _series([75.0])
    assert rsi_mod.rsi_base_score(rsi_values, _flags([True]), 25.0).iloc[0] == pytest.approx(1.0)
    assert rsi_mod.rsi_base_score(rsi_values, _flags([False]), 25.0).iloc[0] == pytest.approx(-1.0)


def test_rsi_span_rejects_non_positive():
    with pytest.raises(ValueError, match="span"):
        rsi_mod.rsi_base_score(_series([50.0]), _flags([True]), 0.0)


def test_bullish_divergence_needs_price_lower_low_and_rsi_higher_low():
    """docs/01 section 3.2. The two comparisons point in OPPOSITE directions;
    swapping them yields a plausible-looking but inverted signal."""
    # Two confirmable pivot lows: at index 2 and index 6. Both need `legs` bars of
    # clearance on each side, so a trough at index 1 would never be evaluated.
    rsi_values = _series([50, 50, 30, 50, 50, 50, 35, 50, 50, 50, 50])
    low = _series([10, 10, 8, 10, 10, 10, 6, 10, 10, 10, 10])
    high = low + 5.0

    bullish, bearish = rsi_mod.divergences(rsi_values, high, low, 2)
    assert bullish.any(), "RSI 30 -> 35 (higher low) with price 8 -> 6 (lower low)"
    assert not bearish.any()

    # Stamped at the confirmation bar, `legs` after the second pivot at index 6.
    assert bullish.iloc[8]


def test_no_bullish_divergence_when_both_make_lower_lows():
    rsi_values = _series([50, 50, 30, 50, 50, 50, 25, 50, 50, 50, 50])
    low = _series([10, 10, 8, 10, 10, 10, 6, 10, 10, 10, 10])
    high = low + 5.0

    bullish, _ = rsi_mod.divergences(rsi_values, high, low, 2)
    assert not bullish.any(), "RSI also made a lower low -- that is confirmation, not divergence"


def test_divergence_bonus_of_zero_disables_the_term():
    """docs/07 section 1 puts 0.0 in the sweep range deliberately: it tests whether
    divergence adds anything at all."""
    rng = np.random.default_rng(5)
    n = 120
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    high, low = close + 1.0, close - 1.0
    trending = _flags([True] * n)

    with_bonus = rsi_mod.rsi_score(close, high, low, trending, 14, 25.0, 5, 0.35)
    without = rsi_mod.rsi_score(close, high, low, trending, 14, 25.0, 5, 0.0)
    base = rsi_mod.rsi_base_score(
        __import__("azimuth.core.primitives", fromlist=["rsi"]).rsi(close, 14), trending, 25.0
    )

    pd.testing.assert_series_equal(without, base, check_names=False)
    assert not with_bonus.equals(without)


# ── 5. correlation (docs/01 section 5) ───────────────────────────────────────────


def test_log_returns_not_price_levels():
    """docs/01 section 5: price-level correlation between two trending series is
    close to meaningless (spurious regression)."""
    close = _series([100.0, 110.0, 121.0])
    result = correlation.log_returns(close)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(math.log(1.1))
    assert result.iloc[2] == pytest.approx(math.log(1.1))


def test_positive_rho_with_rising_reference_votes_long():
    n = 200
    rng = np.random.default_rng(9)
    steps = rng.normal(0.5, 0.2, n)
    close = pd.Series(100.0 + np.cumsum(steps))
    ref = pd.Series(50.0 + np.cumsum(steps * 2.0))  # perfectly correlated, rising

    result = correlation.correlation_score(close, [ref], 60, 0.3, 20)
    assert result.iloc[-1] > 0.5, "positively correlated with a rising reference -> long"


def test_negative_rho_flips_the_vote():
    """docs/01 section 5: 'exactly right for DXY vs. most risk assets'."""
    n = 200
    rng = np.random.default_rng(9)
    steps = rng.normal(0.5, 0.2, n)
    close = pd.Series(100.0 + np.cumsum(steps))
    ref = pd.Series(600.0 - np.cumsum(steps * 2.0))  # anti-correlated, falling, stays positive

    result = correlation.correlation_score(close, [ref], 60, 0.3, 20)
    assert result.iloc[-1] > 0.5, "negatively correlated with a FALLING reference -> long"


def test_reference_below_the_rho_floor_casts_no_vote():
    n = 200
    rng = np.random.default_rng(4)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    ref = pd.Series(50.0 + np.cumsum(rng.normal(0, 1, n)))  # independent

    strict = correlation.correlation_score(close, [ref], 60, 0.99, 20)
    assert (strict.abs() < 1e-12).all(), "no reference clears |rho| >= 0.99"


def test_no_references_scores_zero_not_nan():
    """pine/AZIMUTH.pine:175 is ``corrN > 0 ? clip(...) : 0.0`` -- the component
    abstains rather than going na and poisoning the composite."""
    result = correlation.correlation_score(RISING, [], 60, 0.3, 20)
    assert (result == 0.0).all()


def test_crowding_divides_by_enabled_reference_count():
    """finding 0: the Pine bug pinned this denominator at 1, letting crowding
    exceed its documented [0, 1] range."""
    rho1 = _series([0.5, 0.5])
    rho2 = _series([-0.5, -0.5])

    result = correlation.crowding([rho1, rho2], n_enabled=2)
    assert result.tolist() == [0.5, 0.5]
    assert result.max() <= 1.0


def test_crowding_uses_absolute_values():
    """Everything moving together is one trade whichever sign the moves have."""
    result = correlation.crowding([_series([-0.9])], n_enabled=1)
    assert result.iloc[0] == pytest.approx(0.9)


def test_effective_observations_detects_a_stale_reference():
    """finding 3, M1 diagnostic. A reference trading ~27% of bars should report
    roughly 0.27, not 1.0 -- and rho is computed regardless."""
    n = 400
    rng = np.random.default_rng(21)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    ref_live = pd.Series(50.0 + np.cumsum(rng.normal(0, 1, n)))
    traded = rng.random(n) < 0.27
    ref_stale = ref_live.where(traded).ffill().bfill()

    fresh = correlation.effective_observations(close, ref_live, 60).dropna()
    stale = correlation.effective_observations(close, ref_stale, 60).dropna()

    assert fresh.mean() > 0.95
    assert stale.mean() < 0.5, f"stale reference should report a low share, got {stale.mean():.2f}"


def test_rho_stability_reports_both_halves():
    """docs/07 section 5: if the sign flips between halves, DROP that reference."""
    n = 400
    rng = np.random.default_rng(2)
    steps = rng.normal(0, 1, n)
    close = pd.Series(100.0 + np.cumsum(steps))
    # Correlated in the first half, anti-correlated in the second.
    ref_steps = np.concatenate([steps[: n // 2], -steps[n // 2 :]])
    ref = pd.Series(50.0 + np.cumsum(ref_steps))

    first, second = correlation.rho_stability(close, ref, 60)
    assert first > 0.0 and second < 0.0, "an unstable reference must be visible as a sign flip"


# ── 6. regime (docs/01 section 6) ────────────────────────────────────────────────


def test_efficiency_ratio_is_one_for_a_straight_line():
    """Directional travel equals total travel."""
    assert regime.efficiency_ratio(RISING, 4).iloc[4] == pytest.approx(1.0)


def test_efficiency_ratio_is_zero_for_a_round_trip():
    zigzag = _series([1.0, 2.0, 1.0, 2.0, 1.0])
    assert regime.efficiency_ratio(zigzag, 4).iloc[4] == pytest.approx(0.0)


def test_efficiency_ratio_is_bounded():
    rng = np.random.default_rng(6)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, 300)))
    values = regime.efficiency_ratio(close, 20).dropna()
    assert values.min() >= 0.0 and values.max() <= 1.0


def test_regime_modes_force_the_gate():
    """docs/01 section 6: the three modes are separate hypotheses, not a sweep axis."""
    n = 60
    rng = np.random.default_rng(8)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)))
    high, low = close + 1.0, close - 1.0

    args = (high, low, close, 20, 0.3, 14, 20.0)
    assert regime.trending(*args, mode="trend_only").all()
    assert not regime.trending(*args, mode="range_only").any()


def test_gate_is_the_or_of_er_and_adx():
    """Either estimator alone is enough -- docs/01 section 6."""
    n = 200
    close = pd.Series(np.arange(100.0, 100.0 + n))  # a straight line: ER = 1
    high, low = close + 0.5, close - 0.5

    # ADX threshold impossibly high, ER threshold low: the gate still fires on ER.
    assert regime.trending(high, low, close, 20, 0.3, 14, 1e9).iloc[-1]


def test_warmup_reads_as_range_not_trend():
    """NaN comparisons are False in Pine, so the warm-up is 'range'. Reproduced
    rather than masked: forcing 'trend' would change which branch the first real
    bars take."""
    n = 40
    close = pd.Series(np.arange(100.0, 100.0 + n))
    high, low = close + 0.5, close - 0.5
    result = regime.trending(high, low, close, 20, 0.3, 14, 20.0)

    assert result.dtype == bool
    assert not result.iloc[0]


def test_regime_diagnostics_hand_computed():
    """finding 1, M1 diagnostic. flags = [T,T,F,F,T]:
    duty 3/5, 2 flips, runs [2 trend, 2 range, 1 trend]."""
    stats = regime.regime_diagnostics(_flags([True, True, False, False, True]))

    assert stats["n_bars"] == 5.0
    assert stats["duty_cycle"] == pytest.approx(0.6)
    assert stats["range_share"] == pytest.approx(0.4)
    assert stats["n_flips"] == 2.0
    assert stats["mean_trend_run"] == pytest.approx(1.5)
    assert stats["mean_range_run"] == pytest.approx(2.0)


def test_regime_diagnostics_on_a_constant_series():
    stats = regime.regime_diagnostics(_flags([True] * 10))
    assert stats["duty_cycle"] == 1.0
    assert stats["n_flips"] == 0.0
    assert stats["mean_trend_run"] == 10.0
    assert stats["mean_range_run"] == 0.0


def test_regime_diagnostics_rejects_an_empty_series():
    with pytest.raises(ValueError, match="empty"):
        regime.regime_diagnostics(pd.Series([], dtype=bool))


# ── composite (docs/02 section 1) ────────────────────────────────────────────────


def test_composite_saturates_at_one_hundred():
    ones = _series([1.0])
    result = score.composite(ones, ones, ones, ones, ones, WeightsConfig())
    assert result.iloc[0] == pytest.approx(100.0)


def test_composite_is_the_weighted_mean_scaled_by_one_hundred():
    """Default weights 1.0/0.8/0.8/1.2/0.5, sum 4.3. Only the ribbon fires."""
    one, zero = _series([1.0]), _series([0.0])
    result = score.composite(one, zero, zero, zero, zero, WeightsConfig())
    assert result.iloc[0] == pytest.approx(100.0 * 1.0 / 4.3)


def test_equal_weights_baseline():
    """docs/02 section 1 makes (1,1,1,1,1) mandatory in every walk-forward."""
    equal = WeightsConfig(ribbon=1.0, bollinger=1.0, rsi=1.0, htf=1.0, corr=1.0)
    one, zero = _series([1.0]), _series([0.0])
    result = score.composite(one, zero, zero, zero, zero, equal)
    assert result.iloc[0] == pytest.approx(20.0)


def test_zeroing_a_weight_removes_that_component():
    """docs/02 section 5's ablation mechanism."""
    ablated = WeightsConfig(ribbon=0.0)
    one, zero = _series([1.0]), _series([0.0])
    assert score.composite(one, zero, zero, zero, zero, ablated).iloc[0] == pytest.approx(0.0)


def test_composite_propagates_nan_rather_than_scoring_a_partial_set():
    """0 is a legal score meaning 'neutral', so a zero-filled warm-up would be
    indistinguishable from a genuine neutral reading."""
    one = _series([1.0])
    nan = _series([np.nan])
    assert pd.isna(score.composite(one, one, one, nan, one, WeightsConfig()).iloc[0])


def test_component_correlation_matrix_covers_every_pair():
    n = 300
    rng = np.random.default_rng(13)
    base = pd.Series(rng.normal(0, 1, n))
    matrix = score.component_correlation_matrix(
        base,
        base * 0.9 + rng.normal(0, 0.2, n),  # highly collinear with ribbon
        pd.Series(rng.normal(0, 1, n)),
        pd.Series(rng.normal(0, 1, n)),
        pd.Series(rng.normal(0, 1, n)),
    )

    assert len(matrix) == 10, "5 components -> 10 unordered pairs"
    assert matrix[("ribbon", "bollinger")] > 0.6, "finding 16's pre-committed threshold"
    assert all(-1.0 <= v <= 1.0 for v in matrix.values())


def test_component_correlation_matrix_needs_overlapping_data():
    nan = pd.Series([np.nan] * 10)
    with pytest.raises(ValueError, match="warm-up"):
        score.component_correlation_matrix(nan, nan, nan, nan, nan)
