"""Live watcher. Implements ``docs/08_ALERTS.md`` section 4.

Polls the data source on bar close, recomputes the score locally, and emits the
docs/08 section 2 payload. Two purposes: redundancy against TradingView alert
failures, and a LIVE PARITY CHECK -- persistent divergence between the TV alert and
the local computation means the Pine and Python cores have drifted.

Sinks: ``stdout``, ``webhook://``, ``ntfy://``, ``file://``.

OUT OF SCOPE FOR v0.1 (docs/08 section 5): no broker execution, no order routing,
no auto-trading. Adding execution before the validation protocol has passed would
mean risking capital on an unvalidated system, which is the exact failure this
project exists to prevent. M5 is conditional on M4 passing all ten criteria in
docs/05 section 6.
"""

from __future__ import annotations

from typing import Any

from azimuth.config.schema import AzimuthConfig


def build_payload(symbol: str, timeframe: str, side: str) -> dict[str, Any]:
    """Construct the v1 alert payload (docs/08 section 2).

    ``time`` is BAR CLOSE in UTC, not alert-delivery time. ``stop`` and ``target``
    may be NaN on a ``flat`` event.
    """
    raise NotImplementedError("M5 — docs/08_ALERTS.md section 2")


def watch(symbols: list[str], timeframe: str, sink: str, config: AzimuthConfig) -> None:
    """Poll, recompute, emit. Notifications only -- never execution."""
    raise NotImplementedError("M5 — docs/08_ALERTS.md section 4")
