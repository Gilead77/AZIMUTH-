"""Event-ordered backtest engine. Implements ``docs/04_SPEC_PYTHON_CLI.md`` section 7.

RULES, none of them negotiable (docs/02 section 4, docs/04 section 7):

* signals computed on the close of bar t are filled at the OPEN of bar t+1.
  Filling at the signal bar's close is lookahead, and docs/02 section 4 calls it
  "the single most common backtest lie";
* stop and target are checked intrabar from t+1 onwards;
* when both are touched in the same bar, assume the STOP filled first --
  conservative -- and log the ambiguity count;
* costs on both sides: ``spread_bps/2 + commission_bps + slippage_bps`` per side;
* fixed-fractional sizing by default; no pyramiding in v0.1.

docs/11_FINDINGS.md finding 8: fold-boundary trade handling is unspecified in
docs/05 section 2. A position open when a fold ends must be handled by a stated
rule -- recommended: force-close at the boundary bar's close, reporting the count
and P&L of boundary-closed trades separately so their contribution is visible.
"""

from __future__ import annotations

import pandas as pd

from azimuth.config.schema import AzimuthConfig


def run_backtest(df: pd.DataFrame, config: AzimuthConfig, cost_bps: float) -> pd.DataFrame:
    """Execute the state machine over ``df``; return the trade ledger."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 7")


def equity_curve(ledger: pd.DataFrame, index: pd.DatetimeIndex) -> pd.Series:
    """Mark-to-market equity series from a trade ledger."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 7")
