"""White's Reality Check and Hansen's SPA. ``docs/05_SPEC_VALIDATION.md`` section 5.

Tests the best configuration against the FULL set of configurations under the null
of no predictive ability -- the complement to DSR, which corrects a single Sharpe
for the number of trials.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def reality_check(performance: pd.DataFrame, n_bootstrap: int, rng: np.random.Generator) -> float:
    """White's Reality Check p-value across all evaluated configurations."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 5")


def hansen_spa(performance: pd.DataFrame, n_bootstrap: int, rng: np.random.Generator) -> float:
    """Hansen's SPA p-value; less conservative than the Reality Check."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 5")
