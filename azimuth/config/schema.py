"""Pydantic configuration schema.

Implements the parameter set defined in ``docs/07_PARAMETERS.md`` section 1.

The YAML keys here are the canonical names. ``docs/03_SPEC_PINE.md`` section 3
states the naming contract: Pine input variable names and Python config keys must
map 1:1 (camelCase in Pine, snake_case in YAML). ``azimuth/core/params.py`` holds
that mapping. Renaming a key here without updating both sides breaks the sweep's
ability to address Pine inputs by name.

Two validators are deliberately hard errors rather than warnings:

* ``htf.confirmed_only`` must be ``True``. ``docs/07_PARAMETERS.md`` section 1
  marks it "fixed true -- Never sweep. False = lookahead", and CLAUDE.md rule 1
  admits no exceptions.
* ``signal.exit`` must be strictly less than ``signal.enter``. The hysteresis dead
  band in ``docs/02_SPEC_SCORING.md`` section 3 is meaningless otherwise, and an
  inverted pair produces a state machine that can never exit.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

RegimeMode = Literal["adaptive", "trend_only", "range_only"]
"""Regime gate mode. ``docs/01_SPEC_COMPONENTS.md`` section 6 requires all three to
be run as separate hypotheses, not searched over as a parameter."""


class _Base(BaseModel):
    """Reject unknown keys so a typo in YAML fails loudly instead of silently
    falling back to a default."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RibbonConfig(_Base):
    """EMA ribbon. ``docs/01_SPEC_COMPONENTS.md`` section 1."""

    lengths: tuple[int, int, int, int, int, int, int, int] = (8, 13, 21, 34, 55, 89, 144, 233)
    """Pine ``l1..l8``. Swept as whole-set presets only -- ``docs/07`` section 1:
    sweeping eight lengths freely is a guaranteed overfit."""

    slope_lookback: int = Field(default=5, ge=1)
    """Pine ``ribSlopeLb``. Bars for the ATR-normalised EMA-34 slope."""

    compress_lookback: int = Field(default=200, ge=20)
    """Pine ``ribCompLb``. See docs/11_FINDINGS.md finding 4 -- ribCompress does not
    reach the score, so this parameter cannot move any metric."""

    compress_pctile: float = Field(default=20.0, ge=0.0, le=100.0)
    """Pine ``ribCompTh``. See docs/11_FINDINGS.md finding 4."""

    @model_validator(mode="after")
    def _lengths_ascending(self) -> Self:
        ascending = list(self.lengths) == sorted(self.lengths)
        distinct = len(set(self.lengths)) == len(self.lengths)
        if not (ascending and distinct):
            raise ValueError(
                f"ribbon.lengths must be strictly ascending and distinct, got {self.lengths}. "
                "The stacking score in docs/01 section 1.1 counts adjacent pairs and is "
                "meaningless for an unordered set."
            )
        return self


class BollingerConfig(_Base):
    """Bollinger bands. ``docs/01_SPEC_COMPONENTS.md`` section 2."""

    length: int = Field(default=20, ge=2)
    """Pine ``bbLen``."""

    mult: float = Field(default=2.0, gt=0.0)
    """Pine ``bbMult``."""

    bw_lookback: int = Field(default=200, ge=20)
    """Pine ``bbLb``. See docs/11_FINDINGS.md finding 4."""

    squeeze_pctile: float = Field(default=20.0, ge=0.0, le=100.0)
    """Pine ``bbSqzTh``. See docs/11_FINDINGS.md finding 4."""


class RsiConfig(_Base):
    """RSI and divergence bonus. ``docs/01_SPEC_COMPONENTS.md`` section 3."""

    length: int = Field(default=14, ge=2)
    """Pine ``rsiLen``."""

    span: float = Field(default=25.0, gt=0.0)
    """Pine ``rsiSpan``. RSI distance from 50 mapping to a full +/-1 score."""

    div_legs: int = Field(default=5, ge=2)
    """Pine ``divLb``. Pivot legs each side. Confirms ``div_legs`` bars late; that
    lag is reproduced deliberately (docs/01 section 3.2, docs/06 section 3)."""

    div_bonus: float = Field(default=0.35, ge=0.0, le=1.0)
    """Pine ``divBonus``. Sweep range includes 0.0 to test whether divergence adds
    anything at all (docs/07 section 1)."""


class HtfConfig(_Base):
    """Higher-timeframe bias. ``docs/01_SPEC_COMPONENTS.md`` section 4."""

    tf1: str = "240"
    """Pine ``htf1``. Roughly 4x the chart timeframe."""

    tf2: str = "1D"
    """Pine ``htf2``. Roughly 24x the chart timeframe."""

    use_tf2: bool = True
    """Pine ``htfUse2``. When false, ``htf_score`` is HTF1 alone."""

    ema_length: int = Field(default=50, ge=2)
    """Pine ``htfEmaLen``."""

    confirmed_only: bool = True
    """Pine ``htfConfirm``. The repaint contract of docs/01 section 4: return
    ``s[1]`` from inside the HTF context so the value is fixed once the HTF bar
    closes. Costs up to one HTF bar of lag; that cost is non-negotiable."""

    weight_tf1: float = Field(default=0.6, ge=0.0, le=1.0)
    """Blend weight on HTF1 in ``clip(0.6*HTF1 + 0.4*HTF2)`` (docs/01 section 4)."""

    @model_validator(mode="after")
    def _confirmed_only_is_fixed(self) -> Self:
        if not self.confirmed_only:
            raise ValueError(
                "htf.confirmed_only must be true. docs/07_PARAMETERS.md section 1 marks it "
                "'fixed true -- Never sweep. False = lookahead', and CLAUDE.md rule 1 "
                "forbids lookahead unconditionally. There is no override."
            )
        return self


class CorrReference(_Base):
    """One cross-asset correlation reference. ``docs/01_SPEC_COMPONENTS.md`` section 5."""

    symbol: str
    """Pine ``sym1..sym3``."""

    enabled: bool = True
    """Pine ``useC1..useC3``."""


class CorrConfig(_Base):
    """Cross-asset correlation. ``docs/01_SPEC_COMPONENTS.md`` section 5."""

    length: int = Field(default=60, ge=10)
    """Pine ``corrLen``. Correlation window, on LOG RETURNS not prices."""

    min_abs_rho: float = Field(default=0.30, ge=0.0, le=1.0)
    """Pine ``corrMin``. Floor below which a reference casts no vote."""

    ref_ema: int = Field(default=50, ge=2)
    """Pine ``corrRefEma``. EMA defining the reference's own trend direction."""

    references: tuple[CorrReference, ...] = (
        CorrReference(symbol="TVC:DXY", enabled=True),
        CorrReference(symbol="SP:SPX", enabled=True),
        CorrReference(symbol="TVC:GOLD", enabled=False),
    )
    """Defaults are PLACEHOLDERS (docs/01 section 5, docs/07 section 5). Choose by
    causal story, then verify stability; never by highest historical rho.

    See docs/11_FINDINGS.md finding 3: a reference on a different trading calendar
    injects structural zero returns and yields a meaningless rho that parity will
    nonetheless reproduce exactly."""


class RegimeConfig(_Base):
    """Regime gate. ``docs/01_SPEC_COMPONENTS.md`` section 6."""

    er_length: int = Field(default=20, ge=5)
    """Pine ``erLen``. Kaufman efficiency ratio window."""

    er_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    """Pine ``erTh``."""

    adx_length: int = Field(default=14, ge=2)
    """Pine ``adxLen``. Used for both DMI length and ADX smoothing."""

    adx_threshold: float = Field(default=20.0, ge=0.0)
    """Pine ``adxTh``."""

    mode: RegimeMode = "adaptive"
    """Pine ``regimeMode``. Three discrete modes, run as separate hypotheses.

    See docs/11_FINDINGS.md finding 1: the gate inverts the sign of both the
    Bollinger and RSI scores with no hysteresis, so a single flip moves the
    composite by up to ~74 points -- more than signal.enter."""


class WeightsConfig(_Base):
    """Composite weights. ``docs/02_SPEC_SCORING.md`` section 1.

    Hyperparameters: swept, never tuned by eye. An equal-weight configuration
    (1,1,1,1,1) is a MANDATORY baseline in every walk-forward -- if tuned weights
    do not beat equal weights out of sample, use equal weights.
    """

    ribbon: float = Field(default=1.0, ge=0.0)
    bollinger: float = Field(default=0.8, ge=0.0)
    rsi: float = Field(default=0.8, ge=0.0)
    htf: float = Field(default=1.2, ge=0.0)
    corr: float = Field(default=0.5, ge=0.0)

    @model_validator(mode="after")
    def _not_all_zero(self) -> Self:
        if self.ribbon + self.bollinger + self.rsi + self.htf + self.corr <= 0.0:
            raise ValueError("weights must not all be zero -- the composite would be undefined")
        return self


class SignalConfig(_Base):
    """State machine. ``docs/02_SPEC_SCORING.md`` section 3."""

    enter: float = Field(default=45.0, gt=0.0, le=100.0)
    """Pine ``enterTh``."""

    exit: float = Field(default=15.0, ge=0.0, le=100.0)
    """Pine ``exitTh``. The gap to ``enter`` is the hysteresis dead band."""

    cooldown_bars: int = Field(default=8, ge=0)
    """Pine ``cooldown``. See docs/11_FINDINGS.md finding 2: measured from the last
    ENTRY, not the last signal, so it is likely inert whenever the mean holding
    period exceeds it."""

    require_trend: bool = True
    """Pine ``reqTrend``. Not tabulated in docs/07 section 1 -- see finding 13."""

    require_htf: bool = True
    """Pine ``reqHTF``. Not tabulated in docs/07 section 1 -- see finding 13."""

    @model_validator(mode="after")
    def _exit_below_enter(self) -> Self:
        if self.exit >= self.enter:
            raise ValueError(
                f"signal.exit ({self.exit}) must be strictly less than signal.enter "
                f"({self.enter}). docs/07 section 1: 'must be < enter'. Without the dead band "
                "of docs/02 section 3 the state machine chatters at the boundary, and with "
                "exit > enter it can never exit."
            )
        return self


class RiskConfig(_Base):
    """ATR-anchored risk levels. ``docs/02_SPEC_SCORING.md`` section 3."""

    atr_stop_mult: float = Field(default=2.0, gt=0.0)
    """Pine ``atrStop``."""

    rr_target: float = Field(default=2.0, gt=0.0)
    """Pine ``rrTarget``."""

    atr_length: int = Field(default=14, ge=1)
    """Pine ``atrLen``. FINDING-13: has no row in docs/07 section 1 despite feeding
    both the ribbon slope normalisation and the stop distance. Recommendation in
    docs/11_FINDINGS.md is to fix it at 14 and not sweep it, precisely because it
    changes two things at once."""


class AzimuthConfig(_Base):
    """Root configuration. Mirrors ``docs/07_PARAMETERS.md`` section 1 in full."""

    ribbon: RibbonConfig = RibbonConfig()
    bollinger: BollingerConfig = BollingerConfig()
    rsi: RsiConfig = RsiConfig()
    htf: HtfConfig = HtfConfig()
    corr: CorrConfig = CorrConfig()
    regime: RegimeConfig = RegimeConfig()
    weights: WeightsConfig = WeightsConfig()
    signal: SignalConfig = SignalConfig()
    risk: RiskConfig = RiskConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> AzimuthConfig:
        """Load and validate a config file. Raises on unknown or invalid keys."""
        text = Path(path).read_text(encoding="utf-8")
        raw: Any = yaml.safe_load(text)
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: expected a YAML mapping at the top level, got {type(raw)}")
        return cls.model_validate(raw)


DEFAULT_CONFIG_RESOURCE = "default.yaml"


def default_config_path() -> Path:
    """Path to the packaged default config.

    Canonical location is ``azimuth/config/default.yaml`` per
    ``docs/04_SPEC_PYTHON_CLI.md`` section 3, so it survives an install. See
    docs/11_FINDINGS.md finding 17 for the docs/00 vs docs/04 path discrepancy.
    """
    with resources.as_file(
        resources.files("azimuth.config").joinpath(DEFAULT_CONFIG_RESOURCE)
    ) as p:
        return Path(p)


def load_default() -> AzimuthConfig:
    """Load the packaged default configuration."""
    return AzimuthConfig.from_yaml(default_config_path())


def load_config(path: str | Path | None = None) -> AzimuthConfig:
    """Load ``path``, or the packaged default when ``path`` is None."""
    return load_default() if path is None else AzimuthConfig.from_yaml(path)
