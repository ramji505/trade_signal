# TradeSignal India — Upgrade V2

## Implemented

- Real Groww token exchange for TOTP/approval authentication with an injectable HTTP boundary for tests.
- `LIVE_DATA` market-provider selection for historical candles, live quote, and option-chain payloads.
- Groww option-chain normalization into the internal PCR/OI/IV scoring model.
- Unified 100-point score: 45 structure + 30 confirmations + 25 options, minus explicit risk penalties.
- Event-calendar veto using configurable JSON schedule.
- Current configurable NIFTY lot size (65) and current option-sale STT default (0.15%).
- Backtest threshold unified to 80 and daily circuit-breaker state resets per session.
- No-losing-trade profit factor is `null`; fewer than 30 completed trades are marked non-actionable.
- Regression tests updated to validate the upgraded controls.

## Live-data mode

Set `ENVIRONMENT=LIVE_DATA` and supply Groww credentials in `.env`. Run paper trading and a large historical/out-of-sample test before any real-money execution. The repository intentionally contains no live credentials.
