import json
import asyncio
import os
import pandas as pd
from app.data.mock_provider import MockNiftyProvider
from app.backtest.engine import BacktestEngine
from app.data.candle_builder import CandleBuilder

async def main():
    feed = MockNiftyProvider(base_price=25000.0, seed=123)
    # Generate 1m base candles for multi-day session simulation
    records_1m = await feed.get_historical_candles(symbol="NIFTY", timeframe="1m", count=400 * 5)
    df_1m = pd.DataFrame(records_1m)
    df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"])
    df_1m = df_1m.set_index("timestamp")

    # Resample to 5m
    df_5m = CandleBuilder.resample_candles(df_1m, "5m")

    bt = BacktestEngine(score_threshold=80)
    report = bt.run(symbol="NIFTY", df_5m=df_5m, df_1m=df_1m)

    print(f"Total Trades: {report.total_trades}")
    print(f"Winning Trades: {report.winning_trades}")
    print(f"Losing Trades: {report.losing_trades}")
    print(f"Win Rate: {report.win_rate_pct}%")
    print(f"Profit Factor: {report.profit_factor}")
    print(f"Net PnL (Rs): {report.total_net_pnl_rupees}")
    print(f"Statutory Costs (Rs): {report.total_statutory_costs_rupees}")

    summary_dict = {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "total_candles_analyzed": report.total_candles_analyzed,
        "total_trades": report.total_trades,
        "winning_trades": report.winning_trades,
        "losing_trades": report.losing_trades,
        "win_rate_pct": report.win_rate_pct,
        "profit_factor": report.profit_factor,
        "expectancy_points": report.expectancy_points,
        "max_drawdown_points": report.max_drawdown_points,
        "gross_profit_points": report.gross_profit_points,
        "gross_loss_points": report.gross_loss_points,
        "net_pnl_points": report.net_pnl_points,
        "total_gross_pnl_rupees": report.total_gross_pnl_rupees,
        "total_statutory_costs_rupees": report.total_statutory_costs_rupees,
        "total_net_pnl_rupees": report.total_net_pnl_rupees,
        "score_tier_stats": [vars(s) for s in report.score_tier_stats],
        "time_of_day_stats": [vars(s) for s in report.time_of_day_stats],
        "regime_stats": [vars(s) for s in report.regime_stats],
        "sample_size_warning": report.sample_size_warning,
        "performance_is_statistically_actionable": report.performance_is_statistically_actionable,
        "trade_log": report.trade_log
    }

    os.makedirs("../outputs", exist_ok=True)

    with open("../outputs/backtest_latest.json", "w") as f:
        json.dump(summary_dict, f, indent=2)

    perf_dict = {
        "total_trades": report.total_trades,
        "winning_trades": report.winning_trades,
        "losing_trades": report.losing_trades,
        "win_rate_pct": report.win_rate_pct,
        "profit_factor": report.profit_factor,
        "net_pnl_points": report.net_pnl_points,
        "net_pnl_rupees": report.total_net_pnl_rupees,
        "statutory_costs_rupees": report.total_statutory_costs_rupees,
        "expectancy_points": report.expectancy_points,
        "max_drawdown_points": report.max_drawdown_points,
        "active_circuit_breaker": False,
        "sample_size_warning": report.sample_size_warning,
        "performance_is_statistically_actionable": report.performance_is_statistically_actionable
    }

    with open("../outputs/performance.json", "w") as f:
        json.dump(perf_dict, f, indent=2)

    if report.trade_log:
        df_trades = pd.DataFrame(report.trade_log)
        df_trades.to_csv("../outputs/trades_history.csv", index=False)
        print("Successfully saved outputs/trades_history.csv and backtest_latest.json")

if __name__ == "__main__":
    asyncio.run(main())
