"""Deflated and Probabilistic Sharpe. Implements ``docs/05_SPEC_VALIDATION.md`` section 5.

DSR (Bailey & Lopez de Prado) corrects an observed Sharpe for the number of trials
N, non-normal returns (skew and kurtosis), and sample length. PSR(SR* = 0) must
exceed 0.95.

docs/05 section 5 puts it plainly: a raw Sharpe of 1.5 from 5,000 configurations is
entirely consistent with noise. DSR is what tells you whether it is.

TWO OPEN ITEMS, both must be settled BEFORE the sweep runs.

finding 6 -- N is under-counted. docs/07 section 2's cumulative 760 excludes
ablations, the three regime modes, the equal-weight baseline, cross-instrument runs
and every exploratory backtest whose Sharpe was displayed. N is the number of
Sharpe values that have been LOOKED AT. The counter is incremented mechanically in
``azimuth/backtest/metrics.py``, not by hand.

finding 7 -- the staged sweep breaks the standard estimator. DSR assumes N draws
from a single family, but docs/07 section 2 conditions stage 2 on stage 1's winner
and so on, making the staging itself a selection step that the formula does not
represent. Applying the vanilla formula to pooled N UNDERSTATES the correction.
Pre-commit to one treatment in docs/09 sections 3-4: either per-stage DSR reporting
the most conservative, or pooled N with the pooled variance of all observed
Sharpes. The latter is the recommendation. Choosing after seeing whether the result
passes is exactly the degree of freedom pre-registration exists to remove.
"""

from __future__ import annotations

import pandas as pd


def probabilistic_sharpe(
    observed_sr: float, benchmark_sr: float, n_obs: int, skew: float, kurtosis: float
) -> float:
    """PSR: probability the true Sharpe exceeds ``benchmark_sr``. Needs >= 0.95."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 5")


def expected_max_sharpe(n_trials: int, trial_sr_variance: float) -> float:
    """Expected maximum Sharpe under the null, given N trials."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 5")


def deflated_sharpe(
    observed_sr: float,
    trial_sharpes: pd.Series[float],
    n_trials: int,
    n_obs: int,
    skew: float,
    kurtosis: float,
) -> float:
    """Deflated Sharpe Ratio. Must be > 0 for criterion 2.

    ``n_trials`` comes from ``runs/N_trials.txt`` (lifetime cumulative), NOT from
    ``len(trial_sharpes)``.
    """
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 5")


def minimum_detectable_sharpe(n_obs: int, n_trades: int, power: float = 0.80) -> float:
    """Smallest Sharpe detectable at the given power for this sample.

    docs/11_FINDINGS.md finding 14. Criterion 1 requires walk-forward Sharpe >= 0.7;
    if the minimum detectable Sharpe exceeds that, criterion 1 is not a test.

    A failure to reject H0 on an underpowered sample is NOT evidence of no edge, and
    "we could not have detected an effect of this size" is a materially different
    verdict from "there is no effect". Compute before signing the pre-registration.
    """
    raise NotImplementedError("M3 — docs/11_FINDINGS.md finding 14")
