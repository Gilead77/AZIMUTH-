"""Walk-forward validation. Implements ``docs/05_SPEC_VALIDATION.md`` sections 1-2.

Splits (section 1): in-sample 50% earliest, walk-forward 30%, holdout 20% latest.
Plus a cross-instrument holdout -- parameters fitted on instrument A are tested
unchanged on B, C, D. A rule that only works on the asset it was fitted to is a
fitted rule.

docs/11_FINDINGS.md finding 8: docs/05 section 2 uses Lopez de Prado's purge and
embargo vocabulary, which is built for supervised learners with overlapping label
windows. AZIMUTH trains nothing -- it is a fixed rule whose parameters are chosen
by grid search -- so "purge training observations whose label window overlaps the
test set" has no referent. What actually matters:

1. WARMUP ISOLATION. The longest lookback is 233 bars, with 200-bar percentranks
   and a 60-bar correlation behind it. Each fold must warm its indicators from data
   inside its own history. The embargo as specified, ``max(233, avg_holding * 3)``,
   achieves this -- it is correctly sized, just misnamed.
2. FOLD-BOUNDARY TRADES. Currently unspecified anywhere, and a real leakage
   channel. A position open when a fold ends needs a stated rule. Recommended:
   force-close at the boundary close, reporting boundary-closed trade count and
   P&L separately.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold with its warmup region marked."""

    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    warmup_bars: int


def make_splits(
    index: pd.DatetimeIndex,
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    """Return ``(in_sample, walk_forward, holdout)`` as 50/30/20 by time."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 1")


def make_folds(index: pd.DatetimeIndex, n_folds: int, embargo_bars: int) -> list[Fold]:
    """Anchored and rolling folds with warmup isolation (finding 8)."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 2")
