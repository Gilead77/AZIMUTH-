"""Config schema regression tests.

Covers ``docs/07_PARAMETERS.md`` section 1 key names and the two validators that
are deliberately hard errors.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from azimuth.config.schema import (
    AzimuthConfig,
    default_config_path,
    load_default,
)
from azimuth.core.params import PINE_TO_YAML


def test_default_yaml_loads_and_validates():
    cfg = load_default()
    assert isinstance(cfg, AzimuthConfig)


def test_defaults_match_docs_07_table():
    """Every default in docs/07_PARAMETERS.md section 1, checked literally."""
    c = load_default()

    assert c.ribbon.lengths == (8, 13, 21, 34, 55, 89, 144, 233)
    assert c.ribbon.slope_lookback == 5
    assert c.ribbon.compress_lookback == 200
    assert c.ribbon.compress_pctile == 20.0

    assert c.bollinger.length == 20
    assert c.bollinger.mult == 2.0
    assert c.bollinger.bw_lookback == 200
    assert c.bollinger.squeeze_pctile == 20.0

    assert c.rsi.length == 14
    assert c.rsi.span == 25.0
    assert c.rsi.div_legs == 5
    assert c.rsi.div_bonus == 0.35

    assert c.htf.tf1 == "240"
    assert c.htf.tf2 == "1D"
    assert c.htf.ema_length == 50
    assert c.htf.confirmed_only is True

    assert c.corr.length == 60
    assert c.corr.min_abs_rho == 0.30
    assert c.corr.ref_ema == 50

    assert c.regime.er_length == 20
    assert c.regime.er_threshold == 0.30
    assert c.regime.adx_length == 14
    assert c.regime.adx_threshold == 20.0
    assert c.regime.mode == "adaptive"

    # docs/07 section 1: 1.0/0.8/0.8/1.2/0.5 for ribbon/bb/rsi/htf/corr
    assert (
        c.weights.ribbon,
        c.weights.bollinger,
        c.weights.rsi,
        c.weights.htf,
        c.weights.corr,
    ) == (1.0, 0.8, 0.8, 1.2, 0.5)

    assert c.signal.enter == 45.0
    assert c.signal.exit == 15.0
    assert c.signal.cooldown_bars == 8

    assert c.risk.atr_stop_mult == 2.0
    assert c.risk.rr_target == 2.0
    assert c.risk.atr_length == 14  # FINDING-13


def test_confirmed_only_false_is_rejected():
    """docs/07 section 1: 'fixed true -- Never sweep. False = lookahead'.

    CLAUDE.md rule 1 admits no exceptions, so this must be impossible to express
    in a config file at all, not merely discouraged.
    """
    with pytest.raises(ValidationError, match="confirmed_only"):
        AzimuthConfig.model_validate({"htf": {"confirmed_only": False}})


def test_exit_must_be_below_enter():
    """docs/07 section 1: exit 'must be < enter'. Equal is also rejected --
    a zero-width dead band is the chattering single threshold docs/02 section 3
    exists to avoid."""
    with pytest.raises(ValidationError, match="strictly less than"):
        AzimuthConfig.model_validate({"signal": {"enter": 45.0, "exit": 45.0}})

    with pytest.raises(ValidationError, match="strictly less than"):
        AzimuthConfig.model_validate({"signal": {"enter": 30.0, "exit": 50.0}})


def test_unknown_key_is_rejected():
    """A typo must fail loudly rather than silently falling back to a default."""
    with pytest.raises(ValidationError):
        AzimuthConfig.model_validate({"ribbon": {"slope_lookbak": 5}})


def test_ribbon_lengths_must_be_ascending_and_distinct():
    """The stacking score counts adjacent pairs; an unordered set is meaningless."""
    with pytest.raises(ValidationError, match="ascending"):
        AzimuthConfig.model_validate({"ribbon": {"lengths": [8, 21, 13, 34, 55, 89, 144, 233]}})

    with pytest.raises(ValidationError, match="ascending"):
        AzimuthConfig.model_validate({"ribbon": {"lengths": [8, 8, 21, 34, 55, 89, 144, 233]}})


def test_weights_may_be_zeroed_individually_for_ablation():
    """docs/02 section 5 requires running with any component's weight zeroed."""
    for component in ("ribbon", "bollinger", "rsi", "htf", "corr"):
        cfg = AzimuthConfig.model_validate({"weights": {component: 0.0}})
        assert getattr(cfg.weights, component) == 0.0


def test_all_weights_zero_is_rejected():
    with pytest.raises(ValidationError, match="not all be zero"):
        AzimuthConfig.model_validate(
            {"weights": {"ribbon": 0.0, "bollinger": 0.0, "rsi": 0.0, "htf": 0.0, "corr": 0.0}}
        )


def test_equal_weight_baseline_is_expressible():
    """docs/02 section 1 makes (1,1,1,1,1) a mandatory walk-forward baseline."""
    cfg = AzimuthConfig.model_validate(
        {"weights": {"ribbon": 1.0, "bollinger": 1.0, "rsi": 1.0, "htf": 1.0, "corr": 1.0}}
    )
    assert cfg.weights.corr == 1.0


def test_every_yaml_key_in_default_file_is_known_to_the_schema():
    """extra='forbid' already enforces this, but assert it on the shipped file so a
    stale default.yaml cannot pass unnoticed."""
    raw = yaml.safe_load(default_config_path().read_text(encoding="utf-8"))
    AzimuthConfig.model_validate(raw)


def test_pine_mapping_targets_resolve_against_the_schema():
    """docs/03 section 3 naming contract: every Pine input maps to a real config key.

    Guards against a rename on one side silently desynchronising the two cores.
    """
    cfg = load_default()
    for pine_name, dotted in PINE_TO_YAML.items():
        base = dotted.split("[")[0]
        node: object = cfg
        for part in base.split("."):
            assert hasattr(node, part), f"{pine_name} -> {dotted}: no such config key {part!r}"
            node = getattr(node, part)
