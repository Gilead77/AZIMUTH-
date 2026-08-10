"""Plotly figures for the HTML report. ``docs/04_SPEC_PYTHON_CLI.md`` section 3."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def equity_curve(equity: pd.Series, benchmark: pd.Series | None = None) -> go.Figure:
    """Equity curve, optionally against a volatility-matched benchmark."""
    raise NotImplementedError("M3 — docs/04_SPEC_PYTHON_CLI.md section 3")


def parameter_surface(surface: pd.DataFrame, parameter: str) -> go.Figure:
    """Marginal Sharpe profile for one swept parameter (criterion 7).

    docs/11_FINDINGS.md finding 9: criterion 7 is unfalsifiable as written --
    "neighbouring params within +/-20%" is undefined across 8+ parameters, jointly
    or marginally. Suggested concrete metric, to be pinned in docs/09 before the
    sweep: for each CONTINUOUS swept parameter independently, hold the others at
    the selected configuration and take the mean walk-forward Sharpe over grid
    points within +/-20% of the selected value; pass if that is >= 60% of the
    selected configuration's Sharpe for every parameter. Categoricals are excluded
    and reported as a separate sensitivity table.

    docs/05 section 6 says to plot it every time. Plot it regardless of pass or
    fail -- the shape is more informative than the boolean.
    """
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 6")


def permutation_histogram(observed: float, surrogates: pd.Series, method: str) -> go.Figure:
    """Observed Sharpe against the surrogate distribution for one null method."""
    raise NotImplementedError("M3 — docs/05_SPEC_VALIDATION.md section 4.1")
