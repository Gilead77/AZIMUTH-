"""Cost models. Implements ``docs/05_SPEC_VALIDATION.md`` section 3.

Costs are SWEPT, not assumed:

===========  ================
Scenario     Round-trip cost
===========  ================
Optimistic   5 bps
Realistic    15 bps
Pessimistic  40 bps
Break-even   solve for the cost that zeroes the edge
===========  ================

Report the break-even cost prominently. If break-even is below the realistic cost,
the system is DEAD regardless of the Sharpe. docs/05 section 3 notes that most
confluence systems die exactly here: high trade count, thin per-trade edge.
"""

from __future__ import annotations

import pandas as pd

COST_SCENARIOS: dict[str, float] = {
    "optimistic": 5.0,
    "realistic": 15.0,
    "pessimistic": 40.0,
}
"""Round-trip cost in basis points."""


def per_side_bps(spread_bps: float, commission_bps: float, slippage_bps: float) -> float:
    """``spread_bps/2 + commission_bps + slippage_bps`` (docs/04 section 7)."""
    raise NotImplementedError("M2 — docs/04_SPEC_PYTHON_CLI.md section 7")


def breakeven_cost_bps(gross_returns: pd.Series[float], n_trades: int) -> float:
    """Round-trip cost in bps that drives the edge to exactly zero.

    Criterion 5 requires break-even >= 2x the realistic cost.
    """
    raise NotImplementedError("M2 — docs/05_SPEC_VALIDATION.md section 3")
