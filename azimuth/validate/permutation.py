"""Permutation nulls. Implements ``docs/05_SPEC_VALIDATION.md`` section 4.1.

1,000 surrogate series per method:

* Method A -- block bootstrap of returns, block = 20 bars (partial autocorrelation)
* Method B -- IID shuffle of returns (destroys all structure)
* Method C -- stationary bootstrap (Politis-Romano)

AZIMUTH's real Sharpe must sit above the 95th percentile of each surrogate
distribution; report the empirical p-value.

docs/11_FINDINGS.md finding 5 -- A CORRECTNESS HOLE, not a refinement.

docs/05 section 4.1 specifies surrogates for the traded instrument only. If the
instrument's returns are permuted while the correlation reference series are left
intact, then in every surrogate ``rho -> 0``, the ``|rho| >= corr.min_abs_rho``
gate fails for every reference, and ``corrScore -> 0`` on essentially every bar.
The surrogate strategy is a FOUR-component system while the observed strategy has
five. Comparing them does not test the null of no predictive ability; it tests a
different strategy.

Therefore: the permutation MUST be applied as a single shared index permutation
across all series simultaneously -- own OHLCV and every reference. This destroys
temporal structure while preserving contemporaneous cross-sectional dependence,
which is the point. The null must retain everything except the time ordering the
signal claims to exploit. For the block and stationary bootstraps, draw the block
indices ONCE and apply them to all series.

docs/11_FINDINGS.md also notes the interpretation is diagnostic, not just a
conjunction: passing IID while failing block bootstrap means the edge lives in
volatility clustering rather than in the signal. Report which nulls are beaten,
not only whether all three are.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def iid_shuffle(
    frames: dict[str, pd.DataFrame], rng: np.random.Generator
) -> dict[str, pd.DataFrame]:
    """Method B. ONE permutation applied across all frames (finding 5)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.1")


def block_bootstrap(
    frames: dict[str, pd.DataFrame], block: int, rng: np.random.Generator
) -> dict[str, pd.DataFrame]:
    """Method A. Block indices drawn once, applied to all frames (finding 5)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.1")


def stationary_bootstrap(
    frames: dict[str, pd.DataFrame], mean_block: float, rng: np.random.Generator
) -> dict[str, pd.DataFrame]:
    """Method C, Politis-Romano. Indices drawn once, applied to all (finding 5)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.1")


def empirical_p_value(observed: float, surrogates: pd.Series[float]) -> float:
    """Fraction of surrogates at or above the observed statistic."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.1")
