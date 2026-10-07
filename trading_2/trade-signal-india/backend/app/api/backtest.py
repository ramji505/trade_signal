from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd

from app.core.config import settings
from app.data.mock_provider import MockNiftyProvider
from app.backtest.engine import BacktestEngine, BacktestSummaryReport
from app.data.candle_builder import CandleBuilder

router = APIRouter(prefix="/backtest", tags=["Backtesting & Simulation"])
provider = MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE, seed=101)

# In-memory cache for the latest backtest run
latest_backtest_cache: Optional[Dict[str, Any]] = None


class TimeOfDayResponse(BaseModel):
    bucket: str
    total_trades: int
    winning_trades: int
    win_rate_pct: float
    net_pnl_points: float


class BacktestRunResponse(BaseModel):
    symbol: str
    timeframe: str
    total_candles_analyzed: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: Optional[float]
    expectancy_points: float
    max_drawdown_points: float
    gross_profit_points: float
    gross_loss_points: float
    net_pnl_points: float
    avg_winner_points: float
    avg_loser_points: float
    total_gross_pnl_rupees: Optional[float] = 0.0
    total_statutory_costs_rupees: Optional[float] = 0.0
    total_net_pnl_rupees: Optional[float] = 0.0
    max_drawdown_rupees: Optional[float] = 0.0
    score_tier_stats: Optional[List[Dict[str, Any]]] = []
    time_of_day_stats: List[TimeOfDayResponse]
    regime_stats: Optional[List[Dict[str, Any]]] = []
    sample_size_warning: Optional[str] = None
    performance_is_statistically_actionable: Optional[bool] = False
    trade_log: List[Dict[str, Any]]


@router.post("/run", response_model=BacktestRunResponse, summary="Execute Historical Strategy Backtest")
async def run_backtest(
    symbol: str = "NIFTY",
    candles_count: int = Query(150, ge=40, le=1000),
    score_threshold: int = Query(80, ge=50, le=95)
):
    """
    Executes a walk-forward chronological backtest using True Multi-Timeframe candles (1m base).
    Calculates transparent win rate, profit factor, expectancy, drawdown, options PnL, statutory taxes, and time-of-day stats.
    """
    global latest_backtest_cache
    
    # Request 1-minute base candles
    raw_1m = await provider.get_historical_candles(symbol=symbol, timeframe="1m", count=candles_count * 5)
    df_1m = pd.DataFrame(raw_1m)
    df_1m["dt"] = pd.to_datetime(df_1m["timestamp"])
    df_1m.set_index("dt", inplace=True)

    # Build primary 5m candles
    df_5m = CandleBuilder.resample_candles(df_1m, "5m")

    backtester = BacktestEngine(score_threshold=score_threshold)
    report = backtester.run(symbol=symbol, df_5m=df_5m, df_1m=df_1m)

    tod_list = [
        TimeOfDayResponse(
            bucket=t.bucket,
            total_trades=t.total_trades,
            winning_trades=t.winning_trades,
            win_rate_pct=t.win_rate_pct,
            net_pnl_points=t.net_pnl_points
        )
        for t in report.time_of_day_stats
    ]

    response_data = BacktestRunResponse(
        symbol=report.symbol,
        timeframe=report.timeframe,
        total_candles_analyzed=report.total_candles_analyzed,
        total_trades=report.total_trades,
        winning_trades=report.winning_trades,
        losing_trades=report.losing_trades,
        win_rate_pct=report.win_rate_pct,
        profit_factor=report.profit_factor,
        expectancy_points=report.expectancy_points,
        max_drawdown_points=report.max_drawdown_points,
        gross_profit_points=report.gross_profit_points,
        gross_loss_points=report.gross_loss_points,
        net_pnl_points=report.net_pnl_points,
        avg_winner_points=report.avg_winner_points,
        avg_loser_points=report.avg_loser_points,
        total_gross_pnl_rupees=report.total_gross_pnl_rupees,
        total_statutory_costs_rupees=report.total_statutory_costs_rupees,
        total_net_pnl_rupees=report.total_net_pnl_rupees,
        max_drawdown_rupees=report.max_drawdown_rupees,
        score_tier_stats=[vars(s) for s in report.score_tier_stats],
        time_of_day_stats=tod_list,
        regime_stats=[vars(r) for r in report.regime_stats],
        sample_size_warning=report.sample_size_warning,
        performance_is_statistically_actionable=report.performance_is_statistically_actionable,
        trade_log=report.trade_log
    )

    latest_backtest_cache = response_data.model_dump()
    return response_data


@router.get("/latest", summary="Get Latest Backtest Results")
async def get_latest_backtest():
    global latest_backtest_cache
    if latest_backtest_cache is None:
        # Run default backtest automatically
        return await run_backtest(symbol="NIFTY", candles_count=150, score_threshold=80)
    return latest_backtest_cache


@router.post("/monte-carlo", summary="Run Monte Carlo Resampling & Slippage Stress Test")
async def run_monte_carlo(
    iterations: int = Query(1000, ge=100, le=5000),
    slippage_penalty_rupees: float = Query(75.0, ge=0.0, le=500.0)
):
    """
    Shuffles trade history 1,000x with randomized slippage noise to test robustness against ruin.
    """
    from app.backtest.monte_carlo import MonteCarloEngine
    latest = await get_latest_backtest()
    trade_log = latest.get("trade_log", []) if isinstance(latest, dict) else getattr(latest, "trade_log", [])
    pnls = [float(t.get("net_pnl_after_costs", t.get("pnl_points", 0.0))) for t in trade_log]

    sim_res = MonteCarloEngine.run_monte_carlo(
        trade_pnls_rupees=pnls,
        iterations=iterations,
        slippage_penalty_rupees_per_trade=slippage_penalty_rupees
    )
    return vars(sim_res)


@router.get("/calibration", summary="Empirical Score-to-Expectancy Calibration")
async def get_score_calibration():
    """
    Returns empirical win rates and expected value across score buckets (50-59, 60-69, 70-79, 80-89, 90-100).
    """
    from app.backtest.monte_carlo import MonteCarloEngine
    latest = await get_latest_backtest()
    trade_log = latest.get("trade_log", []) if isinstance(latest, dict) else getattr(latest, "trade_log", [])
    buckets = MonteCarloEngine.calibrate_score_buckets(trade_log)
    return [vars(b) for b in buckets]


@router.post("/walk-forward", summary="Run Rolling Window Walk-Forward Validation")
async def run_walk_forward(windows: int = Query(4, ge=2, le=10)):
    """
    Executes rolling train/test splits to measure Out-of-Sample Efficiency Ratio (PF_oos / PF_is).
    """
    from app.evaluation.walk_forward import QuantitativeEdgeValidator
    latest = await get_latest_backtest()
    trade_log = latest.get("trade_log", []) if isinstance(latest, dict) else getattr(latest, "trade_log", [])
    wf_results = QuantitativeEdgeValidator.run_walk_forward_splits(trade_log, num_windows=windows)
    return [vars(r) for r in wf_results]


@router.get("/deflated-sharpe", summary="Calculate Deflated Sharpe Ratio (DSR)")
async def get_deflated_sharpe(estimated_trials: int = Query(100, ge=1, le=10000)):
    """
    Calculates DSR to verify that strategy returns are genuine and not an artifact of multiple testing.
    """
    from app.evaluation.walk_forward import QuantitativeEdgeValidator
    latest = await get_latest_backtest()
    trade_log = latest.get("trade_log", []) if isinstance(latest, dict) else getattr(latest, "trade_log", [])
    returns = [float(t.get("pnl_points", 0.0)) / float(t.get("entry_price", 25000.0)) for t in trade_log]
    dsr = QuantitativeEdgeValidator.calculate_deflated_sharpe(returns, estimated_trials=estimated_trials)
    return vars(dsr)


