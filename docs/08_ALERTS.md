# 08 — Alerts & Webhook Schema

## 1. TradingView alert setup

Condition: **AZIMUTH** → *Any alert() function call*
Frequency: **Once per bar close** (enforced in code, set it here too)
Message: leave empty — the payload comes from `alert()`.

## 2. Payload schema (v1)

```json
{
  "strategy": "AZIMUTH",
  "v": "0.1.0",
  "side": "long | short | flat",
  "symbol": "BINANCE:BTCUSDT",
  "tf": "240",
  "time": "2026-08-10T12:00:00Z",
  "price": 61234.5,
  "score": 52.31,
  "stop": 59100.0,
  "target": 65500.0,
  "regime": "trend | range",
  "htf": 0.83,
  "crowding": 0.41
}
```

### Consumer contract
- `time` is **bar close** in UTC, not alert-delivery time.
- `stop`/`target` may be `NaN` on a `flat` event — handle it.
- Deduplicate on `(symbol, tf, time, side)`. TradingView can deliver twice.
- Reject any payload where `time` is more than 2× the bar interval old — a
  delayed alert is a stale alert.

## 3. Versioning

Bump `v` on any schema change. Consumers must reject unknown major versions
rather than guess.

## 4. Local consumer (`azimuth watch`)

```bash
azimuth watch --symbols BTC-USD,ETH-USD --tf 4h --sink ntfy://azimuth-harry
```

Polls the data source on bar close, recomputes the score locally, and emits the
same schema. Two purposes:
1. Redundancy against TradingView alert failures.
2. **Live parity check** — log any divergence between the TV alert and the local
   computation. Persistent divergence means the Pine and Python cores have drifted.

Sinks: `stdout`, `webhook://`, `ntfy://`, `file://`.

## 5. Explicitly out of scope for v0.1 🔒

No broker execution. No order routing. No auto-trading.

`azimuth watch` emits notifications only. Adding execution before the validation
protocol has passed would mean risking capital on an unvalidated system, which is
the exact failure this project is designed to prevent. Revisit only after
`05_SPEC_VALIDATION.md` §6 acceptance criteria are met and documented.
