"""HTF construction. Implements ``docs/04_SPEC_PYTHON_CLI.md`` section 6.

PARITY-CRITICAL. Pine's HTF bars are right-closed and right-labelled, and a value
is only available AFTER the HTF bar closes::

    htf = df.resample(rule, label="right", closed="right").agg(OHLCV_AGG)
    htf_score = compute_htf_score(htf).shift(1)      # confirmed bar only
    aligned = htf_score.reindex(df.index, method="ffill")

The ``.shift(1)`` is the equivalent of returning ``s[1]`` inside
``request.security``. Omitting it produces lookahead and is the most likely source
of a fake edge (docs/04 section 6, CLAUDE.md rule 1).

``tests/test_htf_alignment.py`` asserts zero lookahead on synthetic data.
"""

from __future__ import annotations

import pandas as pd

OHLCV_AGG: dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


def resample_htf(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Right-closed, right-labelled HTF bars matching Pine's bar construction."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 6")


def timeframe_to_rule(timeframe: str) -> str:
    """Map a Pine timeframe string ("240", "1D", "1W") to a pandas offset alias."""
    raise NotImplementedError("M1 — docs/04_SPEC_PYTHON_CLI.md section 6")
