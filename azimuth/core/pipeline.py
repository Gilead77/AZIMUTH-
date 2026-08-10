"""End-to-end signal computation, in Pine's order.

Produces one frame whose columns are exactly the ``x_*`` series that
``pine/AZIMUTH.pine`` exports via ``display.data_window``, which is what
``azimuth parity`` compares (``docs/06_PARITY_TESTS.md`` section 1).

Not listed in ``docs/04_SPEC_PYTHON_CLI.md`` section 3's tree -- a deliberate
addition, on the same justification as ``azimuth/validate/gate.py``. The parity
harness, ``azimuth signals`` and the backtest engine all need one callable that
turns OHLCV into the full component set; assembling the eight component modules by
hand at each call site is how the HTF shift gets dropped from one of them.

ORDER IS LOAD-BEARING. ``pine/AZIMUTH.pine`` computes the regime gate at line 185
and only then derives ``bbScore`` and ``rsiScore`` at 189-191, because
``trending`` inverts the sign of both (``docs/02`` section 2). Computing them
before the gate, or against a stale gate, silently produces a different system --
one that would still generate signals and still backtest.
"""

from __future__ import annotations

import pandas as pd

from azimuth.config.schema import AzimuthConfig
from azimuth.core import bollinger, correlation, htf, regime, ribbon, rsi_mod, score, signals
from azimuth.core._types import FloatSeries
from azimuth.core.primitives import atr as atr_primitive

__all__ = ["EXPORT_COLUMNS", "compute_frame"]

EXPORT_COLUMNS = (
    "x_ribbon",
    "x_bb",
    "x_rsi",
    "x_htf",
    "x_corr",
    "x_er",
    "x_adx",
    "x_pctb",
    "x_bwpct",
    "x_state",
)
"""The ``x_*`` plots in ``pine/AZIMUTH.pine``, per ``docs/03`` section 4.

``x_ref1..3``, ``x_rho1..3`` and ``x_crowd`` were added in commit 4 (finding 19)
and are compared when the fixture carries them; they are not required, since a
fixture exported before that change will not have them.
"""


def compute_frame(
    df: pd.DataFrame,
    config: AzimuthConfig,
    refs: dict[str, FloatSeries] | None = None,
) -> pd.DataFrame:
    """Compute every component, the composite and the state machine.

    Args:
        df: Canonical OHLCV frame (``docs/04`` section 5).
        config: Validated configuration.
        refs: Correlation reference closes, keyed by symbol, already aligned to
            ``df``'s timeframe. Omit to run with ``x_corr`` identically 0, which
            is what Pine does when every ``useC*`` is false.

    Returns:
        A frame on ``df``'s index carrying the ``x_*`` export columns plus the
        intermediates (``score``, ``trending``, ``atr``, the per-reference rho,
        the trade levels) that the backtest engine and diagnostics need.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]

    out = pd.DataFrame(index=df.index)

    # ── shared ─────────────────────────────────────────────────────────────────
    atr = atr_primitive(high, low, close, config.risk.atr_length)
    out["atr"] = atr

    # ── 1. ribbon (AZIMUTH.pine:110-128) ───────────────────────────────────────
    lengths = list(config.ribbon.lengths)
    out["x_ribbon"] = ribbon.ribbon_score(close, atr, lengths, config.ribbon.slope_lookback)
    out["rib_compress"] = ribbon.ribbon_compression(
        close, lengths, config.ribbon.compress_lookback, config.ribbon.compress_pctile
    )

    # ── 2. bollinger, direction-free parts (AZIMUTH.pine:130-135) ──────────────
    bb_length, bb_mult = config.bollinger.length, config.bollinger.mult
    out["x_pctb"] = bollinger.percent_b(close, bb_length, bb_mult)
    out["x_bwpct"] = bollinger.bandwidth_pctile(
        close, bb_length, bb_mult, config.bollinger.bw_lookback
    )
    out["bb_squeeze"] = bollinger.squeeze(
        close, bb_length, bb_mult, config.bollinger.bw_lookback, config.bollinger.squeeze_pctile
    )

    # ── 4. HTF bias (AZIMUTH.pine:147-156) ─────────────────────────────────────
    out["x_htf"] = htf.htf_component(
        df,
        tf1=config.htf.tf1,
        tf2=config.htf.tf2 if config.htf.use_tf2 else None,
        ema_length=config.htf.ema_length,
        rsi_length=config.htf.rsi_length,
        slope_lookback=config.htf.slope_lookback,
        weight_tf1=config.htf.weight_tf1,
        confirmed_only=config.htf.confirmed_only,
    )

    # ── 5. correlation (AZIMUTH.pine:158-180) ──────────────────────────────────
    enabled = [ref for ref in config.corr.references if ref.enabled]
    ref_series: list[FloatSeries] = []
    if refs:
        for index, reference in enumerate(enabled, start=1):
            series = refs.get(reference.symbol)
            if series is None:
                continue
            aligned = series.reindex(df.index)
            ref_series.append(aligned)
            out[f"x_ref{index}"] = aligned
            rho, _, _ = correlation.reference_contribution(
                correlation.log_returns(close),
                aligned,
                config.corr.length,
                config.corr.min_abs_rho,
                config.corr.ref_ema,
            )
            out[f"x_rho{index}"] = rho

    out["x_corr"] = correlation.correlation_score(
        close, ref_series, config.corr.length, config.corr.min_abs_rho, config.corr.ref_ema
    )
    if ref_series:
        out["x_crowd"] = correlation.crowding(
            [out[f"x_rho{i}"] for i in range(1, len(ref_series) + 1)], n_enabled=len(enabled)
        )

    # ── 6. regime gate (AZIMUTH.pine:179-186) ──────────────────────────────────
    # MUST precede the Bollinger and RSI scores: it inverts both.
    out["x_er"] = regime.efficiency_ratio(close, config.regime.er_length)
    out["x_adx"] = regime.adx(high, low, close, config.regime.adx_length)
    trending = regime.trending(
        high,
        low,
        close,
        config.regime.er_length,
        config.regime.er_threshold,
        config.regime.adx_length,
        config.regime.adx_threshold,
        config.regime.mode,
    )
    out["trending"] = trending

    # ── regime-flipped scores (AZIMUTH.pine:188-191) ───────────────────────────
    out["x_bb"] = bollinger.bollinger_score(close, trending, bb_length, bb_mult)
    out["x_rsi"] = rsi_mod.rsi_score(
        close,
        high,
        low,
        trending,
        config.rsi.length,
        config.rsi.span,
        config.rsi.div_legs,
        config.rsi.div_bonus,
    )

    # ── composite (AZIMUTH.pine:193-196) ───────────────────────────────────────
    out["score"] = score.composite(
        out["x_ribbon"],
        out["x_bb"],
        out["x_rsi"],
        out["x_htf"],
        out["x_corr"],
        config.weights,
    )

    # ── state machine (AZIMUTH.pine:198-224) ───────────────────────────────────
    machine = signals.state_machine(
        out["score"],
        trending,
        out["x_htf"],
        config.signal,
        atr=atr,
        close=close,
        risk=config.risk,
    )
    out["x_state"] = machine["state"]
    for column in ("long_trigger", "short_trigger", "exit_signal", "entry", "stop", "target"):
        out[column] = machine[column]

    return out
