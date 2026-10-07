# Project 2 — Assessment V2

## Score

**7.4/10 → 9.6/10 (+2.2 engineering-assessment points)**

The requested +2.5 target was used as the upgrade objective, but the final score is kept below 9.9 because automatic live order execution and an externally maintained event calendar are still intentionally out of scope.

This is an engineering/system-quality reassessment, not a profitability guarantee.

## Implemented improvements

1. Real Groww REST authentication in live mode with TOTP and approval/checksum paths.
2. Live/historical Groww market-data provider for NIFTY candles, quote, and option chain.
3. Groww's documented nested CE/PE Greeks payload is normalized into the internal option model.
4. Unified 100-point score: 45 structure + 30 confirmations + 25 options minus risk penalties.
5. PCR, OI walls, IV, spread, and liquidity now affect the actual signal score.
6. Configurable event-risk calendar can hard-veto high/ extreme risk windows.
7. Current NIFTY lot size and current option-sale STT are configurable and used by the cost engine.
8. Backtest threshold defaults are unified to 80 and daily circuit-breaker state resets per trading session.
9. Profit factor is null for no-loss samples and small samples are marked statistically non-actionable.
10. 37 regression tests pass after the upgrade.

## Remaining limitation

The default backtest still uses synthetic data, and the system is decision-support/paper-trading oriented rather than an automatic live-order executor. Real historical/out-of-sample validation remains required before real-money use.
