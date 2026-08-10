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

docs/11_FINDINGS.md finding 2 -- ``lastSignalBar`` is set on ENTRY only in
``pine/AZIMUTH.pine`` (never on exit), so the cooldown measures time since the last
entry. Whenever the mean holding period exceeds ``cooldown_bars`` the gate never
binds. :func:`cooldown_diagnostics` measures it at M2.
"""

from __future__ import annotations

from azimuth.config.schema import RiskConfig, SignalConfig
from azimuth.core._types import BoolSeries, FloatSeries, IntSeries


def state_machine(
    score: FloatSeries,
    trending: BoolSeries,
    htf: FloatSeries,
    config: SignalConfig,
) -> IntSeries:
    """Run the state machine. Returns the integer state series (Pine ``x_state``).

    Sequential by construction: state at bar t depends only on state at t-1 and
    inputs at t. No vectorisation that would let a later bar influence an earlier
    one -- ``tests/test_lookahead.py`` enforces this.
    """
    raise NotImplementedError("M1 — docs/02_SPEC_SCORING.md section 3")


def risk_levels(
    entry_price: FloatSeries,
    state: IntSeries,
    atr: FloatSeries,
    config: RiskConfig,
) -> tuple[FloatSeries, FloatSeries]:
    """ATR-anchored ``(stop, target)`` recorded at entry (docs/02 section 3)."""
    raise NotImplementedError("M1 — docs/02_SPEC_SCORING.md section 3")


def cooldown_diagnostics(
    score: FloatSeries,
    trending: BoolSeries,
    htf: FloatSeries,
    config: SignalConfig,
) -> dict[str, int]:
    """Count signals suppressed by each entry gate, separately.

    docs/11_FINDINGS.md finding 2, M2 diagnostic. Returns counts of crossovers
    blocked by the cooldown alone, by the trend gate alone, by the HTF gate alone,
    and the number surviving all three.

    If the cooldown blocks zero signals it is inert, and sweeping it 0-20 adds ~20
    configurations to N that cannot change any result.

    Also feeds finding 14 (statistical power): the surviving count is the expected
    trade count, which decides whether criterion 10 (>= 100 out-of-sample trades)
    is reachable at all before the pre-registration is signed.
    """
    raise NotImplementedError("M2 — docs/11_FINDINGS.md findings 2 and 14")
