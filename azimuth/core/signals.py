"""Signal state machine. Mirrors ``docs/02_SPEC_SCORING.md`` section 3 exactly.

::

    state in {-1 short, 0 flat, +1 long}

    longTrig = state <= 0
             and crossover(score, +enter)
             and (bar_index - lastSignalBar >= cooldown)
             and (not require_trend or trending)
             and (not require_htf   or htf_score > 0)

    exitLong  = state == +1 and score < +exit
    exitShort = state == -1 and score > -exit

The 45/15 gap is a deliberate hysteresis dead band: a single threshold produces
chatter at the boundary, while the dead band lets a position survive normal score
noise and close when confluence genuinely decays.

Exported to Pine's ``x_state``; parity is EXACT, bar for bar (docs/06 section 2).

Execution assumptions (docs/02 section 4) are NON-NEGOTIABLE and belong to the
backtest engine, not here:

* signal evaluated on bar close only -- intrabar signals repaint;
* fill at NEXT bar open -- filling at the signal bar's close is lookahead, and is
  the single most common backtest lie;
* costs on both sides; no pyramiding in v0.1.

The ``entry``/``stop``/``target`` columns produced here are the levels Pine PLOTS,
recorded at the signal bar's close. They are not fill prices. The backtest engine
computes its own fills at the next bar's open; these exist for parity and for the
alert payload (docs/08 section 2).

docs/11_FINDINGS.md finding 2 -- ``lastSignalBar`` is set on ENTRY only in
``pine/AZIMUTH.pine:216,221`` (never on exit), so the cooldown measures time since
the last entry. Whenever the mean holding period exceeds ``cooldown_bars`` the
gate never binds. REPRODUCED HERE DELIBERATELY: parity on ``x_state`` is exact, so
Python must match Pine bug for bug. :func:`cooldown_diagnostics` measures the
impact; changing the semantics is a design change and a new hypothesis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from azimuth.config.schema import RiskConfig, SignalConfig
from azimuth.core._types import BoolSeries, FloatSeries
from azimuth.core.primitives import crossover, crossunder

__all__ = ["cooldown_diagnostics", "risk_levels", "state_machine"]

_NEVER = -99999
"""Pine's ``var int lastBar = -99999`` (``AZIMUTH.pine:200``): the cooldown is
satisfied on the first bar."""


def _entry_gates(
    score: FloatSeries,
    trending: BoolSeries,
    htf: FloatSeries,
    config: SignalConfig,
) -> tuple[BoolSeries, BoolSeries, BoolSeries, BoolSeries, BoolSeries]:
    """Vectorised, per-bar parts of the entry conditions.

    Everything here depends only on bar ``t``; the sequential part (state and
    cooldown) is the loop in :func:`state_machine`.
    """
    cross_up = crossover(score, pd.Series(config.enter, index=score.index))
    cross_down = crossunder(score, pd.Series(-config.enter, index=score.index))

    gate_ok = pd.Series(True, index=score.index) if not config.require_trend else trending
    if config.require_htf:
        htf_long_ok = (htf > 0.0).fillna(value=False)
        htf_short_ok = (htf < 0.0).fillna(value=False)
    else:
        htf_long_ok = pd.Series(True, index=score.index)
        htf_short_ok = pd.Series(True, index=score.index)

    return cross_up, cross_down, gate_ok.astype(bool), htf_long_ok, htf_short_ok


def state_machine(
    score: FloatSeries,
    trending: BoolSeries,
    htf: FloatSeries,
    config: SignalConfig,
    atr: FloatSeries | None = None,
    close: FloatSeries | None = None,
    risk: RiskConfig | None = None,
) -> pd.DataFrame:
    """Run the state machine. Returns a frame with ``state`` (Pine ``x_state``).

    Sequential by construction: state at bar ``t`` depends only on state at
    ``t-1`` and inputs at ``t``. No vectorisation that would let a later bar
    influence an earlier one -- ``tests/test_lookahead.py`` enforces this.

    Args:
        atr, close, risk: Supply all three to also get ``entry``, ``stop`` and
            ``target`` (the levels Pine records at the signal bar). Omit them for
            the state series alone.

    Returns:
        Columns ``state`` (int), ``long_trigger``, ``short_trigger``,
        ``exit_signal`` (bool), and when risk inputs are given, ``entry``,
        ``stop``, ``target`` (float, NaN while flat).
    """
    cross_up, cross_down, gate_ok, htf_long_ok, htf_short_ok = _entry_gates(
        score, trending, htf, config
    )

    want_levels = atr is not None and close is not None and risk is not None

    score_values = score.to_numpy(dtype=float)
    up = cross_up.to_numpy(dtype=bool)
    down = cross_down.to_numpy(dtype=bool)
    gate = gate_ok.to_numpy(dtype=bool)
    long_ok = htf_long_ok.to_numpy(dtype=bool)
    short_ok = htf_short_ok.to_numpy(dtype=bool)
    atr_values = atr.to_numpy(dtype=float) if atr is not None else None
    close_values = close.to_numpy(dtype=float) if close is not None else None

    n = score_values.size
    states = np.zeros(n, dtype=np.int64)
    long_triggers = np.zeros(n, dtype=bool)
    short_triggers = np.zeros(n, dtype=bool)
    exit_signals = np.zeros(n, dtype=bool)
    entries = np.full(n, np.nan)
    stops = np.full(n, np.nan)
    targets = np.full(n, np.nan)

    state = 0
    last_bar = _NEVER
    entry_px = stop_px = target_px = np.nan

    for i in range(n):
        cooled = (i - last_bar) >= config.cooldown_bars
        current = score_values[i]

        # NaN comparisons are False in Pine, so the warm-up cannot fire or exit.
        long_trigger = state <= 0 and up[i] and cooled and gate[i] and long_ok[i]
        short_trigger = state >= 0 and down[i] and cooled and gate[i] and short_ok[i]
        exit_long = state == 1 and current < config.exit
        exit_short = state == -1 and current > -config.exit

        if long_trigger:
            state = 1
            last_bar = i  # FINDING-2: entry only, never on exit. Matches Pine.
            if want_levels:
                entry_px = close_values[i]  # type: ignore[index]
                stop_px = entry_px - risk.atr_stop_mult * atr_values[i]  # type: ignore[union-attr,index]
                target_px = entry_px + risk.atr_stop_mult * atr_values[i] * risk.rr_target  # type: ignore[union-attr,index]
        elif short_trigger:
            state = -1
            last_bar = i
            if want_levels:
                entry_px = close_values[i]  # type: ignore[index]
                stop_px = entry_px + risk.atr_stop_mult * atr_values[i]  # type: ignore[union-attr,index]
                target_px = entry_px - risk.atr_stop_mult * atr_values[i] * risk.rr_target  # type: ignore[union-attr,index]
        elif exit_long or exit_short:
            state = 0
            entry_px = stop_px = target_px = np.nan

        states[i] = state
        long_triggers[i] = long_trigger
        short_triggers[i] = short_trigger
        exit_signals[i] = exit_long or exit_short
        entries[i] = entry_px
        stops[i] = stop_px
        targets[i] = target_px

    result = pd.DataFrame(
        {
            "state": states,
            "long_trigger": long_triggers,
            "short_trigger": short_triggers,
            "exit_signal": exit_signals,
        },
        index=score.index,
    )
    if want_levels:
        result["entry"] = entries
        result["stop"] = stops
        result["target"] = targets
    return result


def risk_levels(
    entry_price: FloatSeries,
    state: pd.Series,
    atr: FloatSeries,
    config: RiskConfig,
) -> tuple[FloatSeries, FloatSeries]:
    """ATR-anchored ``(stop, target)`` for an already-known entry and direction.

    ``docs/02`` section 3::

        stop   = entry -/+ atr_stop_mult * ATR
        target = entry +/- atr_stop_mult * ATR * rr_target

    :func:`state_machine` produces these inline when given the risk inputs; this
    is for recomputing them from a trade ledger.
    """
    direction = state.astype(float)
    distance = config.atr_stop_mult * atr
    return (
        entry_price - direction * distance,
        entry_price + direction * distance * config.rr_target,
    )


def cooldown_diagnostics(
    score: FloatSeries,
    trending: BoolSeries,
    htf: FloatSeries,
    config: SignalConfig,
) -> dict[str, int]:
    """Count signals suppressed by each entry gate, separately.

    docs/11_FINDINGS.md finding 2, M2 diagnostic. Returns the number of threshold
    crossings, how many each gate blocked in isolation, and how many survived all
    of them.

    PRE-COMMITTED READING: if ``blocked_by_cooldown_only`` is **0**, the cooldown
    is inert, and sweeping ``signal.cooldown_bars`` over 0-20 adds ~20
    configurations to N that cannot change any result.

    Also feeds finding 14 (statistical power): ``surviving`` is the expected trade
    count, which decides whether criterion 10 (>= 100 out-of-sample trades) is
    reachable at all. Criterion 10 applies to the 30% walk-forward slice, so the
    full sample needs roughly 330+ for it to be satisfiable -- and that must be
    known BEFORE the pre-registration is signed, because choosing the instrument
    or timeframe afterwards is a researcher degree of freedom.

    A trade count is not a performance metric, so this may be run before parity.
    """
    cross_up, cross_down, gate_ok, htf_long_ok, htf_short_ok = _entry_gates(
        score, trending, htf, config
    )

    crossings = cross_up | cross_down
    gate_blocks = crossings & ~gate_ok
    htf_ok = (cross_up & htf_long_ok) | (cross_down & htf_short_ok)
    htf_blocks = crossings & ~htf_ok

    # The cooldown is sequential, so it needs the state machine to evaluate.
    with_cooldown = state_machine(score, trending, htf, config)
    fired = with_cooldown["long_trigger"] | with_cooldown["short_trigger"]

    unlimited = config.model_copy(update={"cooldown_bars": 0})
    without_cooldown = state_machine(score, trending, htf, unlimited)
    fired_uncapped = without_cooldown["long_trigger"] | without_cooldown["short_trigger"]

    return {
        "threshold_crossings": int(crossings.sum()),
        "blocked_by_trend_gate": int(gate_blocks.sum()),
        "blocked_by_htf_gate": int(htf_blocks.sum()),
        "blocked_by_cooldown_only": int(fired_uncapped.sum() - fired.sum()),
        "surviving": int(fired.sum()),
    }
