"""Pine <-> Python parameter name mapping.

``docs/03_SPEC_PINE.md`` section 3 fixes the naming contract: Pine input variable
names and Python config keys are identical modulo case convention (camelCase in
Pine, snake_case in YAML), mapped 1:1 here.

The mapping exists so the sweep can address Pine inputs by name, and so a rename
on one side fails loudly in CI instead of silently desynchronising the two cores.
The canonical table is ``docs/07_PARAMETERS.md`` section 1.
"""

from __future__ import annotations

PINE_TO_YAML: dict[str, str] = {
    "l1": "ribbon.lengths[0]",
    "l2": "ribbon.lengths[1]",
    "l3": "ribbon.lengths[2]",
    "l4": "ribbon.lengths[3]",
    "l5": "ribbon.lengths[4]",
    "l6": "ribbon.lengths[5]",
    "l7": "ribbon.lengths[6]",
    "l8": "ribbon.lengths[7]",
    "ribSlopeLb": "ribbon.slope_lookback",
    "ribCompLb": "ribbon.compress_lookback",
    "ribCompTh": "ribbon.compress_pctile",
    "bbLen": "bollinger.length",
    "bbMult": "bollinger.mult",
    "bbLb": "bollinger.bw_lookback",
    "bbSqzTh": "bollinger.squeeze_pctile",
    "rsiLen": "rsi.length",
    "rsiSpan": "rsi.span",
    "divLb": "rsi.div_legs",
    "divBonus": "rsi.div_bonus",
    "htf1": "htf.tf1",
    "htf2": "htf.tf2",
    "htfUse2": "htf.use_tf2",
    "htfEmaLen": "htf.ema_length",
    "htfConfirm": "htf.confirmed_only",
    # FINDING-20: these two have no Pine input yet -- they are hardcoded at
    # pine/AZIMUTH.pine:150-151. Listed with their intended Pine names so the
    # contract is recorded now and the Pine side can be brought into line later
    # without a second rename.
    "htfRsiLen": "htf.rsi_length",
    "htfSlopeLb": "htf.slope_lookback",
    "corrLen": "corr.length",
    "corrMin": "corr.min_abs_rho",
    "corrRefEma": "corr.ref_ema",
    "erLen": "regime.er_length",
    "erTh": "regime.er_threshold",
    "adxLen": "regime.adx_length",
    "adxTh": "regime.adx_threshold",
    "regimeMode": "regime.mode",
    "wRib": "weights.ribbon",
    "wBB": "weights.bollinger",
    "wRSI": "weights.rsi",
    "wHTF": "weights.htf",
    "wCorr": "weights.corr",
    "enterTh": "signal.enter",
    "exitTh": "signal.exit",
    "cooldown": "signal.cooldown_bars",
    "reqTrend": "signal.require_trend",  # FINDING-13: absent from docs/07 section 1
    "reqHTF": "signal.require_htf",  # FINDING-13
    "atrLen": "risk.atr_length",  # FINDING-13
    "atrStop": "risk.atr_stop_mult",
    "rrTarget": "risk.rr_target",
}
"""Every Pine input in ``pine/AZIMUTH.pine`` that affects a calculation.

Visual-only inputs (``showRibbon``, ``showBB``, ``showLevels``, ``showTable``) are
deliberately excluded: they cannot change a score, and including them would imply
they are sweepable.

Correlation reference symbols (``sym1..sym3``, ``useC1..useC3``) map to the
structured ``corr.references`` list rather than to scalar keys, so they are handled
separately by the sweep driver.
"""

YAML_TO_PINE: dict[str, str] = {v: k for k, v in PINE_TO_YAML.items()}
