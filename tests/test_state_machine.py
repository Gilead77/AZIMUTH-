"""State machine: table-driven entry, exit, cooldown and hysteresis.

``docs/06_PARITY_TESTS.md`` section 4 names this file. ``x_state`` is compared at
EXACT tolerance bar-for-bar (``docs/06`` section 2), so every branch of
``docs/02_SPEC_SCORING.md`` section 3 needs to be pinned.

The cooldown tests encode finding 2 as CURRENT BEHAVIOUR, not as desired
behaviour: ``lastBar`` is set on entry only, so the gate measures time since the
last entry. Python reproduces Pine bug-for-bug because parity demands it. If the
semantics are ever changed, these tests should fail -- that is the point.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azimuth.config.schema import RiskConfig, SignalConfig
from azimuth.core.signals import cooldown_diagnostics, state_machine


def _run(
    scores: list[float],
    *,
    enter: float = 45.0,
    exit_: float = 15.0,
    cooldown: int = 0,
    require_trend: bool = False,
    require_htf: bool = False,
    trending: list[bool] | None = None,
    htf: list[float] | None = None,
) -> pd.DataFrame:
    n = len(scores)
    index = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    config = SignalConfig(
        enter=enter,
        exit=exit_,
        cooldown_bars=cooldown,
        require_trend=require_trend,
        require_htf=require_htf,
    )
    return state_machine(
        pd.Series(scores, index=index, dtype=float),
        pd.Series(trending if trending is not None else [True] * n, index=index),
        pd.Series(htf if htf is not None else [1.0] * n, index=index, dtype=float),
        config,
    )


def _states(*args, **kwargs) -> list[int]:
    return _run(*args, **kwargs)["state"].tolist()


# ── entry ───────────────────────────────────────────────────────────────────────


def test_long_entry_on_crossover():
    """Entry needs a CROSSOVER, not merely being above the threshold."""
    assert _states([0.0, 20.0, 50.0, 60.0]) == [0, 0, 1, 1]


def test_starting_above_the_threshold_does_not_enter():
    """No crossover event exists if the series begins above it. Reproduces Pine's
    ta.crossover, which needs a prior bar at or below."""
    assert _states([50.0, 60.0, 70.0]) == [0, 0, 0]


def test_short_entry_is_the_mirror():
    assert _states([0.0, -20.0, -50.0, -60.0]) == [0, 0, -1, -1]


def test_touching_the_threshold_exactly_is_not_a_cross():
    assert _states([0.0, 45.0, 45.0]) == [0, 0, 0]


# ── exit and hysteresis ─────────────────────────────────────────────────────────


def test_exit_uses_the_dead_band_not_the_entry_threshold():
    """docs/02 section 3: the 45/15 gap lets a position survive normal score noise.

    Score decays 60 -> 30 -> 20 (all above exit=15, so the long holds) -> 10
    (below, so it closes).
    """
    assert _states([0.0, 60.0, 30.0, 20.0, 10.0]) == [0, 1, 1, 1, 0]


def test_short_exit_mirrors():
    assert _states([0.0, -60.0, -30.0, -20.0, -10.0]) == [0, -1, -1, -1, 0]


def test_a_single_threshold_would_chatter_but_the_dead_band_does_not():
    """Score oscillating between 40 and 50 around enter=45. With a single
    threshold this would open and close repeatedly; with the dead band the
    position opens once and holds."""
    scores = [0.0, 50.0, 40.0, 50.0, 40.0, 50.0]
    assert _states(scores) == [0, 1, 1, 1, 1, 1]


def test_position_flips_directly_from_long_to_short():
    """state <= 0 for long and state >= 0 for short, so a reversal does not need
    to pass through flat -- pine/AZIMUTH.pine:210-211."""
    assert _states([0.0, 60.0, -60.0]) == [0, 1, -1]


# ── gates ───────────────────────────────────────────────────────────────────────


def test_trend_gate_blocks_entry_when_required():
    assert _states([0.0, 60.0], require_trend=True, trending=[False, False]) == [0, 0]
    assert _states([0.0, 60.0], require_trend=True, trending=[True, True]) == [0, 1]


def test_htf_gate_blocks_a_long_when_htf_is_negative():
    assert _states([0.0, 60.0], require_htf=True, htf=[-1.0, -1.0]) == [0, 0]
    assert _states([0.0, 60.0], require_htf=True, htf=[1.0, 1.0]) == [0, 1]


def test_htf_gate_blocks_a_short_when_htf_is_positive():
    assert _states([0.0, -60.0], require_htf=True, htf=[1.0, 1.0]) == [0, 0]
    assert _states([0.0, -60.0], require_htf=True, htf=[-1.0, -1.0]) == [0, -1]


def test_htf_exactly_zero_blocks_both_directions():
    """Pine is ``htfScore > 0`` and ``htfScore < 0``, so zero satisfies neither."""
    assert _states([0.0, 60.0], require_htf=True, htf=[0.0, 0.0]) == [0, 0]
    assert _states([0.0, -60.0], require_htf=True, htf=[0.0, 0.0]) == [0, 0]


def test_a_gate_false_on_the_crossover_bar_loses_the_signal_permanently():
    """finding 2's companion observation: the crossover is a ONE-BAR event ANDed
    with the gates. If a gate is false on exactly that bar, the signal is gone
    even though the score stays at 60 with the gate now true.

    Current behaviour, reproduced from Pine. Documented because it makes trade
    count highly sensitive to gate flicker (finding 1).
    """
    scores = [0.0, 60.0, 60.0, 60.0]
    assert _states(scores, require_trend=True, trending=[True, False, True, True]) == [
        0,
        0,
        0,
        0,
    ]


# ── cooldown (finding 2) ────────────────────────────────────────────────────────


def test_cooldown_blocks_a_re_entry_within_n_bars():
    """Long at bar 1, exits at bar 2, tries to re-enter at bar 4. With
    cooldown=5 and lastBar=1, bar 4 gives 4-1=3 < 5, so it is blocked."""
    scores = [0.0, 60.0, 0.0, 20.0, 60.0]
    assert _states(scores, cooldown=5) == [0, 1, 0, 0, 0]


def test_cooldown_permits_the_re_entry_once_elapsed():
    scores = [0.0, 60.0, 0.0, 20.0, 60.0]
    assert _states(scores, cooldown=2) == [0, 1, 0, 0, 1]


def test_cooldown_measures_from_the_last_entry_not_the_last_exit():
    """FINDING 2, pinned as current behaviour.

    ``lastBar`` is set on entry only (pine/AZIMUTH.pine:216,221), never on exit
    (line 224). Entry at bar 1, exit at bar 6, re-entry attempt at bar 8:

    * measured from the last ENTRY (bar 1): 8-1 = 7 >= 4, so it fires;
    * measured from the last EXIT (bar 6):  8-6 = 2 <  4, so it would not.

    The signal fires, which confirms the entry-only semantics. If this test ever
    fails, the cooldown has been silently redefined and x_state parity is broken.
    """
    scores = [0.0, 60.0, 50.0, 50.0, 50.0, 50.0, 0.0, 20.0, 60.0]
    #          0    1(in) 2     3     4     5     6(out) 7   8(re-entry?)
    states = _states(scores, cooldown=4)

    assert states[1] == 1, "entered at bar 1"
    assert states[6] == 0, "exited at bar 6"
    assert states[8] == 1, (
        "re-entered at bar 8 -- cooldown is measured from the entry at bar 1, not "
        "the exit at bar 6 (finding 2)"
    )


def test_cooldown_is_satisfied_on_the_very_first_bar():
    """Pine seeds ``var int lastBar = -99999`` so the gate never blocks the first
    signal of a run."""
    assert _states([0.0, 60.0], cooldown=100) == [0, 1]


# ── NaN handling ────────────────────────────────────────────────────────────────


def test_nan_scores_cannot_fire_or_exit():
    """The warm-up. NaN comparisons are False in Pine, so no entry, and a held
    position is not closed by a NaN either."""
    scores = [np.nan, np.nan, 0.0, 60.0, np.nan, np.nan]
    states = _states(scores)

    assert states[:3] == [0, 0, 0]
    assert states[3] == 1
    assert states[4:] == [1, 1], "a NaN score must not close an open position"


# ── risk levels ─────────────────────────────────────────────────────────────────


def test_risk_levels_are_recorded_at_entry():
    """docs/02 section 3: stop = entry -/+ 2*ATR, target at rr_target x that.

    These are the levels Pine PLOTS, recorded at the signal bar's close. They are
    not fill prices -- the backtest engine fills at the next bar's open
    (docs/02 section 4).
    """
    n = 4
    index = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    result = state_machine(
        pd.Series([0.0, 60.0, 60.0, 0.0], index=index),
        pd.Series([True] * n, index=index),
        pd.Series([1.0] * n, index=index),
        SignalConfig(
            enter=45.0, exit=15.0, cooldown_bars=0, require_trend=False, require_htf=False
        ),
        atr=pd.Series([2.0] * n, index=index),
        close=pd.Series([100.0] * n, index=index),
        risk=RiskConfig(atr_stop_mult=2.0, rr_target=2.0),
    )

    assert result["entry"].iloc[1] == pytest.approx(100.0)
    assert result["stop"].iloc[1] == pytest.approx(100.0 - 2.0 * 2.0)
    assert result["target"].iloc[1] == pytest.approx(100.0 + 2.0 * 2.0 * 2.0)

    # Held, then cleared on exit.
    assert result["stop"].iloc[2] == pytest.approx(96.0)
    assert pd.isna(result["stop"].iloc[3])


def test_short_risk_levels_invert():
    n = 3
    index = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    result = state_machine(
        pd.Series([0.0, -60.0, -60.0], index=index),
        pd.Series([True] * n, index=index),
        pd.Series([-1.0] * n, index=index),
        SignalConfig(
            enter=45.0, exit=15.0, cooldown_bars=0, require_trend=False, require_htf=False
        ),
        atr=pd.Series([2.0] * n, index=index),
        close=pd.Series([100.0] * n, index=index),
        risk=RiskConfig(atr_stop_mult=2.0, rr_target=2.0),
    )

    assert result["stop"].iloc[1] == pytest.approx(104.0)
    assert result["target"].iloc[1] == pytest.approx(92.0)


# ── causality ───────────────────────────────────────────────────────────────────


def test_state_machine_is_causal_under_truncation():
    """State at bar t depends only on state at t-1 and inputs at t."""
    rng = np.random.default_rng(3)
    n = 200
    index = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    score = pd.Series(np.cumsum(rng.normal(0, 12, n)).clip(-100, 100), index=index)
    trending = pd.Series(rng.random(n) > 0.4, index=index)
    htf = pd.Series(rng.choice([-1.0, 1.0], n), index=index)
    config = SignalConfig(enter=45.0, exit=15.0, cooldown_bars=8)

    full = state_machine(score, trending, htf, config)["state"]
    for t in (50, 99, 150, 199):
        truncated = state_machine(
            score.iloc[: t + 1], trending.iloc[: t + 1], htf.iloc[: t + 1], config
        )["state"]
        pd.testing.assert_series_equal(
            full.iloc[: t + 1], truncated, check_freq=False, check_names=False
        )


# ── diagnostics (findings 2 and 14) ─────────────────────────────────────────────


def test_cooldown_diagnostics_reports_each_gate():
    rng = np.random.default_rng(11)
    n = 500
    index = pd.date_range("2020-01-01", periods=n, freq="1h", tz="UTC")
    score = pd.Series(np.cumsum(rng.normal(0, 15, n)).clip(-100, 100), index=index)
    trending = pd.Series(rng.random(n) > 0.3, index=index)
    htf = pd.Series(rng.choice([-1.0, 1.0], n), index=index)

    stats = cooldown_diagnostics(
        score, trending, htf, SignalConfig(enter=45.0, exit=15.0, cooldown_bars=8)
    )

    assert set(stats) == {
        "threshold_crossings",
        "blocked_by_trend_gate",
        "blocked_by_htf_gate",
        "blocked_by_cooldown_only",
        "surviving",
    }
    assert stats["threshold_crossings"] >= stats["surviving"]
    assert stats["blocked_by_cooldown_only"] >= 0


def test_cooldown_diagnostics_detects_an_inert_cooldown():
    """finding 2's pre-committed reading: blocked_by_cooldown_only == 0 means the
    parameter cannot change any result and should not be swept."""
    scores = [0.0, 60.0, 50.0, 50.0, 50.0, 0.0, 60.0]
    index = pd.date_range("2020-01-01", periods=len(scores), freq="1h", tz="UTC")

    stats = cooldown_diagnostics(
        pd.Series(scores, index=index),
        pd.Series([True] * len(scores), index=index),
        pd.Series([1.0] * len(scores), index=index),
        SignalConfig(enter=45.0, exit=15.0, cooldown_bars=2),
    )
    assert stats["blocked_by_cooldown_only"] == 0
