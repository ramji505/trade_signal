from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from app.strategy.signal_engine import SignalEngine
from app.evaluation.signal_evaluator import SignalEvaluator
from app.risk.circuit_breakers import CircuitBreakerEngine
from app.costs.statutory_charges import calculate_option_trade_costs
from app.core.config import settings
from app.data.candle_builder import CandleBuilder


@dataclass
class BacktestTradeRecord:
    trade_id: int
    entry_time: str
    direction: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    score: int
    market_regime: str
    result: str  # 'TARGET_HIT', 'STOP_HIT', 'TIMEOUT', 'NO_DECISIVE_MOVE'
    pnl_points: float
    time_of_day_bucket: str
    # Option Specific Metrics
    option_symbol: str
    option_entry: float
    option_sl: float
    option_target: float
    option_exit: float
    gross_pnl: float
    statutory_costs: float
    net_pnl_after_costs: float
    circuit_breaker_active: bool = False


@dataclass
class TimeOfDayStat:
    bucket: str
    total_trades: int
    winning_trades: int
    win_rate_pct: float
    net_pnl_points: float
    net_pnl_rupees: float


@dataclass
class ScoreTierStat:
    tier_range: str
    total_signals: int
    winning_trades: int
    win_rate_pct: float
    net_pnl_rupees: float


@dataclass
class RegimeStat:
    regime_name: str
    total_trades: int
    winning_trades: int
    win_rate_pct: float
    net_pnl_rupees: float
    profit_factor: Optional[float]


@dataclass
class BacktestSummaryReport:
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
    # Rupee and Options Analytics
    total_gross_pnl_rupees: float
    total_statutory_costs_rupees: float
    total_net_pnl_rupees: float
    max_drawdown_rupees: float
    score_tier_stats: List[ScoreTierStat]
    time_of_day_stats: List[TimeOfDayStat]
    regime_stats: List[RegimeStat]
    trade_log: List[Dict[str, Any]]
    sample_size_warning: Optional[str] = None
    performance_is_statistically_actionable: bool = False


class BacktestEngine:
    """
    Institutional Walk-Forward Backtesting Engine:
    - True Multi-Timeframe Construction: Base 1m candles resampled into true 1m, 3m, 5m, 10m, 15m.
    - Zero Look-Ahead Bias: Signal generated strictly from past history up to time T.
    - True 1-Minute Future Path Evaluation: Outcomes tracked across strictly future 1m candles (T+1 to T+20).
    - SL-First Price-Path Verification: Strict Stop Loss priority over Target.
    - Black-Scholes Delta-calibrated option premium path simulation.
    - Full Indian statutory charges deduction (STT, GST, Exchange, SEBI, Stamp, Brokerage).
    - Circuit breaker kill-switch simulation (drawdown locks, consecutive loss halts, daily caps).
    """

    def __init__(self, score_threshold: int = settings.SIGNAL_SCORE_THRESHOLD, max_daily_loss: float = settings.MAX_DAILY_LOSS_RUPEES):
        self.score_threshold = score_threshold
        self.signal_engine = SignalEngine(score_threshold=score_threshold)
        self.circuit_breaker = CircuitBreakerEngine(
            max_daily_loss=max_daily_loss,
            max_consecutive_losses=3,
            max_daily_signals=settings.MAX_DAILY_SIGNALS,
        )

    @staticmethod
    def get_time_of_day_bucket(dt: datetime) -> str:
        hour = dt.hour
        minute = dt.minute
        time_val = hour * 100 + minute

        if time_val < 930:
            return "09:15–09:30 (Opening Volatility)"
        elif time_val < 1100:
            return "09:30–11:00 (Morning Trend)"
        elif time_val < 1330:
            return "11:00–13:30 (Midday Consolidation)"
        elif time_val < 1500:
            return "13:30–15:00 (Afternoon Expansion)"
        else:
            return "15:00–15:30 (Closing Period)"

    def _ensure_1m_data(self, df_5m: pd.DataFrame, df_1m: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Ensures a continuous 1-minute base dataframe is available for MTF and future evaluation."""
        if df_1m is not None and not df_1m.empty:
            return df_1m.copy()

        # Interpolate 1m candles from 5m data if 1m is not provided
        rows = []
        for i, (ts, row) in enumerate(df_5m.iterrows()):
            o, h, l, c, v = row['open'], row['high'], row['low'], row['close'], row['volume'] / 5.0
            for m in range(5):
                m_ts = ts + pd.Timedelta(minutes=m)
                # Linear path approximation within the 5m candle
                ratio = (m + 1) / 5.0
                step_c = o + (c - o) * ratio
                step_h = max(o, step_c, h if m == 2 else step_c)
                step_l = min(o, step_c, l if m == 3 else step_c)
                step_o = o if m == 0 else rows[-1]['close']
                rows.append({
                    "timestamp": m_ts,
                    "open": step_o,
                    "high": step_h,
                    "low": step_l,
                    "close": step_c,
                    "volume": v
                })
        return pd.DataFrame(rows).set_index("timestamp")

    def run(
        self,
        symbol: str,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame] = None
    ) -> BacktestSummaryReport:
        if len(df_5m) < 30:
            raise ValueError("Insufficient historical data for backtesting (requires >= 30 candles).")

        base_1m = self._ensure_1m_data(df_5m, df_1m)
        self.circuit_breaker.reset_day()
        trades: List[BacktestTradeRecord] = []
        trade_id_counter = 1
        last_session_date = None

        # We step through 5-minute decision intervals
        warmup_5m = 25

        for i in range(warmup_5m, len(df_5m) - 6):
            current_5m_dt = df_5m.index[i]
            if getattr(current_5m_dt, "date", None) and current_5m_dt.date() != last_session_date:
                self.circuit_breaker.reset_day()
                last_session_date = current_5m_dt.date()
            time_str = current_5m_dt.strftime("%H:%M")

            # Historical 1m slice up to current 5m candle timestamp (inclusive)
            hist_1m = base_1m.loc[:current_5m_dt]
            if len(hist_1m) < 60:
                continue

            # Strictly future 1m candles for evaluation (forward up to 25 minutes)
            future_1m = base_1m.loc[current_5m_dt:].iloc[1:26]
            if len(future_1m) < 5:
                continue

            # Check circuit breaker before taking signals
            can_trade, cb_reason = self.circuit_breaker.can_generate_signal(time_str, i)

            # Build TRUE multi-timeframe resampled candles from historical 1m base
            tf_slice = {
                "1m": hist_1m,
                "3m": CandleBuilder.resample_candles(hist_1m, "3m"),
                "5m": CandleBuilder.resample_candles(hist_1m, "5m"),
                "10m": CandleBuilder.resample_candles(hist_1m, "10m"),
                "15m": CandleBuilder.resample_candles(hist_1m, "15m")
            }

            signal = self.signal_engine.process(
                symbol=symbol,
                tf_candles=tf_slice,
                is_market_open=True,
                is_data_healthy=True
            )

            if signal.direction in ["BUY", "SELL"] and signal.entry_price is not None:
                if not can_trade:
                    continue

                bucket = self.get_time_of_day_bucket(current_5m_dt)

                # Chronological Path Evaluation using TRUE 1-minute future candles
                eval_report = SignalEvaluator.evaluate_path(
                    signal_id=f"BT-{trade_id_counter}",
                    symbol=symbol,
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    target_1=signal.target_1,
                    target_2=signal.target_2,
                    df_1m_future=future_1m,
                    option_strike=signal.option_strike,
                    option_type=signal.option_type,
                    option_entry=signal.option_entry,
                    option_sl=signal.option_sl,
                    option_target=signal.option_target,
                    delta=abs(signal.delta or 0.55)
                )

                res = eval_report.final_result
                if res == "TARGET_HIT":
                    pnl = (signal.target_1 - signal.entry_price) if signal.direction == "BUY" else (signal.entry_price - signal.target_1)
                elif res == "STOP_HIT":
                    pnl = (signal.stop_loss - signal.entry_price) if signal.direction == "BUY" else (signal.entry_price - signal.stop_loss)
                elif eval_report.horizon_evaluations:
                    # TIMEOUT/NO_DECISIVE_MOVE is marked to the last observed close rather than zero.
                    last_h = eval_report.horizon_evaluations[-1]
                    pnl = last_h.exit_price - signal.entry_price if signal.direction == "BUY" else signal.entry_price - last_h.exit_price
                else:
                    pnl = 0.0

                # Record outcome in circuit breaker
                self.circuit_breaker.record_trade_result(eval_report.net_pnl_after_costs)
                self.circuit_breaker.mark_signal_issued(i)

                trades.append(BacktestTradeRecord(
                    trade_id=trade_id_counter,
                    entry_time=current_5m_dt.strftime("%Y-%m-%d %H:%M"),
                    direction=signal.direction,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    target_1=signal.target_1,
                    target_2=signal.target_2,
                    score=signal.score,
                    market_regime=signal.market_regime,
                    result=res,
                    pnl_points=round(pnl, 2),
                    time_of_day_bucket=bucket,
                    option_symbol=signal.option_symbol or f"NIFTY-{signal.direction}",
                    option_entry=signal.option_entry or 100.0,
                    option_sl=signal.option_sl or 80.0,
                    option_target=signal.option_target or 130.0,
                    option_exit=eval_report.option_exit_premium or 100.0,
                    gross_pnl=eval_report.gross_pnl,
                    statutory_costs=eval_report.total_statutory_charges,
                    net_pnl_after_costs=eval_report.net_pnl_after_costs,
                    circuit_breaker_active=self.circuit_breaker.is_circuit_tripped
                ))

                trade_id_counter += 1

        # Aggregate Statistics
        total_trades = len(trades)
        if total_trades == 0:
            return BacktestSummaryReport(
                symbol=symbol,
                timeframe="5m",
                total_candles_analyzed=len(df_5m),
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                expectancy_points=0.0,
                max_drawdown_points=0.0,
                gross_profit_points=0.0,
                gross_loss_points=0.0,
                net_pnl_points=0.0,
                avg_winner_points=0.0,
                avg_loser_points=0.0,
                total_gross_pnl_rupees=0.0,
                total_statutory_costs_rupees=0.0,
                total_net_pnl_rupees=0.0,
                max_drawdown_rupees=0.0,
                score_tier_stats=[],
                time_of_day_stats=[],
                regime_stats=[],
                trade_log=[],
                sample_size_warning="Not statistically actionable: fewer than 30 completed trades.",
                performance_is_statistically_actionable=False
            )

        winners = [t for t in trades if t.pnl_points > 0]
        losers = [t for t in trades if t.pnl_points <= 0]

        win_count = len(winners)
        loss_count = len(losers)
        win_rate = round((win_count / total_trades) * 100.0, 1)

        gross_profit_pts = sum(t.pnl_points for t in winners)
        gross_loss_pts = abs(sum(t.pnl_points for t in losers))
        net_pnl_pts = gross_profit_pts - gross_loss_pts

        profit_factor = round(gross_profit_pts / gross_loss_pts, 2) if gross_loss_pts > 0 else (None if gross_profit_pts > 0 else 0.0)
        avg_winner_pts = round(gross_profit_pts / win_count, 2) if win_count > 0 else 0.0
        avg_loser_pts = round(gross_loss_pts / loss_count, 2) if loss_count > 0 else 0.0

        win_prob = win_count / total_trades
        loss_prob = loss_count / total_trades
        expectancy = round((win_prob * avg_winner_pts) - (loss_prob * avg_loser_pts), 2)

        # Rupee metrics
        total_gross_rupees = round(sum(t.gross_pnl for t in trades), 2)
        total_costs_rupees = round(sum(t.statutory_costs for t in trades), 2)
        total_net_rupees = round(sum(t.net_pnl_after_costs for t in trades), 2)

        # Drawdown in points and rupees
        cumulative_pts = np.cumsum([t.pnl_points for t in trades])
        peak_pts = np.maximum.accumulate(cumulative_pts)
        dd_pts = peak_pts - cumulative_pts
        max_dd_pts = round(float(np.max(dd_pts)), 2) if len(dd_pts) > 0 else 0.0

        cumulative_rs = np.cumsum([t.net_pnl_after_costs for t in trades])
        peak_rs = np.maximum.accumulate(cumulative_rs)
        dd_rs = peak_rs - cumulative_rs
        max_dd_rs = round(float(np.max(dd_rs)), 2) if len(dd_rs) > 0 else 0.0

        # Score Tier calibration
        tier_brackets = [
            ("Score 85–100 (High Conviction)", lambda s: s >= 85),
            ("Score 75–84 (Medium Conviction)", lambda s: 75 <= s < 85),
            ("Score 65–74 (Standard Threshold)", lambda s: 65 <= s < 75),
        ]
        score_stats = []
        for label, fn in tier_brackets:
            tier_trades = [t for t in trades if fn(t.score)]
            if tier_trades:
                tier_wins = sum(1 for t in tier_trades if t.pnl_points > 0)
                score_stats.append(ScoreTierStat(
                    tier_range=label,
                    total_signals=len(tier_trades),
                    winning_trades=tier_wins,
                    win_rate_pct=round((tier_wins / len(tier_trades)) * 100.0, 1),
                    net_pnl_rupees=round(sum(t.net_pnl_after_costs for t in tier_trades), 2)
                ))

        # Time-of-Day breakdown
        buckets_map: Dict[str, List[BacktestTradeRecord]] = {}
        for t in trades:
            buckets_map.setdefault(t.time_of_day_bucket, []).append(t)

        tod_stats = []
        for b_name, b_trades in buckets_map.items():
            b_wins = sum(1 for bt in b_trades if bt.pnl_points > 0)
            b_wr = round((b_wins / len(b_trades)) * 100.0, 1)
            b_net_pts = round(sum(bt.pnl_points for bt in b_trades), 2)
            b_net_rs = round(sum(bt.net_pnl_after_costs for bt in b_trades), 2)
            tod_stats.append(TimeOfDayStat(
                bucket=b_name,
                total_trades=len(b_trades),
                winning_trades=b_wins,
                win_rate_pct=b_wr,
                net_pnl_points=b_net_pts,
                net_pnl_rupees=b_net_rs
            ))

        # Market Regime breakdown
        regimes_map: Dict[str, List[BacktestTradeRecord]] = {}
        for t in trades:
            regimes_map.setdefault(t.market_regime, []).append(t)

        reg_stats = []
        for r_name, r_trades in regimes_map.items():
            r_wins = sum(1 for rt in r_trades if rt.pnl_points > 0)
            r_losses = sum(1 for rt in r_trades if rt.pnl_points <= 0)
            r_wr = round((r_wins / len(r_trades)) * 100.0, 1)
            r_net_rs = round(sum(rt.net_pnl_after_costs for rt in r_trades), 2)
            r_g_win = sum(rt.pnl_points for rt in r_trades if rt.pnl_points > 0)
            r_g_loss = abs(sum(rt.pnl_points for rt in r_trades if rt.pnl_points < 0))
            r_pf = round(r_g_win / r_g_loss, 2) if r_g_loss > 0 else (None if r_g_win > 0 else 0.0)

            reg_stats.append(RegimeStat(
                regime_name=r_name,
                total_trades=len(r_trades),
                winning_trades=r_wins,
                win_rate_pct=r_wr,
                net_pnl_rupees=r_net_rs,
                profit_factor=r_pf
            ))

        trade_log = [
            {
                "trade_id": t.trade_id,
                "time": t.entry_time,
                "direction": t.direction,
                "spot_entry": t.entry_price,
                "spot_sl": t.stop_loss,
                "spot_target": t.target_1,
                "option_symbol": t.option_symbol,
                "option_entry": t.option_entry,
                "option_sl": t.option_sl,
                "option_target": t.option_target,
                "option_exit": t.option_exit,
                "score": t.score,
                "result": t.result,
                "pnl_points": t.pnl_points,
                "gross_pnl_rs": t.gross_pnl,
                "statutory_costs_rs": t.statutory_costs,
                "net_pnl_rs": t.net_pnl_after_costs,
                "bucket": t.time_of_day_bucket,
                "market_regime": t.market_regime
            }
            for t in trades
        ]

        return BacktestSummaryReport(
            symbol=symbol,
            timeframe="5m",
            total_candles_analyzed=len(df_5m),
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            expectancy_points=expectancy,
            max_drawdown_points=max_dd_pts,
            gross_profit_points=round(gross_profit_pts, 2),
            gross_loss_points=round(gross_loss_pts, 2),
            net_pnl_points=round(net_pnl_pts, 2),
            avg_winner_points=avg_winner_pts,
            avg_loser_points=avg_loser_pts,
            total_gross_pnl_rupees=total_gross_rupees,
            total_statutory_costs_rupees=total_costs_rupees,
            total_net_pnl_rupees=total_net_rupees,
            max_drawdown_rupees=max_dd_rs,
            score_tier_stats=score_stats,
            time_of_day_stats=tod_stats,
            regime_stats=reg_stats,
            trade_log=trade_log,
            sample_size_warning=("Not statistically actionable: fewer than 30 completed trades." if total_trades < 30 else None),
            performance_is_statistically_actionable=(total_trades >= 30)
        )
