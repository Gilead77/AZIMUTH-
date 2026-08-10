"""Shared type aliases.

``pandas.Series`` is generic under pandas-stubs, so a bare ``pd.Series`` fails
``mypy --strict`` (``disallow_any_generics``). These aliases keep the signatures in
``core/`` and ``validate/`` readable while staying strict-clean.
"""

from __future__ import annotations

from typing import TypeAlias

import pandas as pd

FloatSeries: TypeAlias = "pd.Series[float]"
BoolSeries: TypeAlias = "pd.Series[bool]"
IntSeries: TypeAlias = "pd.Series[int]"

__all__ = ["BoolSeries", "FloatSeries", "IntSeries"]
