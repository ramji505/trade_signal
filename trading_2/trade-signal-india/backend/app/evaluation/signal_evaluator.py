from dataclasses import dataclass
from typing import Literal, Optional, List
from datetime import datetime
import pandas as pd

from app.costs.statutory_charges import calculate_option_trade_costs


@dataclass
class HorizonResult:
    horizon_minutes: int
    exit_price: float
    mfe: float  # Maximum Favorable Excursion in points
    mae: float  # Maximum Adverse Excursion in points
    result: Literal["TARGET_HIT", "STOP_HIT", "TIMEOUT", "NO_DECISIVE_MOVE"]
    points_pnl: float
    option_exit_premium: Optional[float] = None
    option_gross_pnl: Optional[float] = None
    statutory_costs: Optional[float] = None
    option_net_pnl: Optional[float] = None
    time_to_hit_minutes: Optional[int] = None


@dataclass
class SignalEvaluationReport:
    signal_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    horizon_evaluations: list[HorizonResult]
    final_result: str
    overall_mfe: float
    overall_mae: float
    # Option Specific Metrics
    option_strike: Optional[float] = None
    option_type: Optional[str] = None
    option_entry: Optional[float] = None
    option_sl: Optional[float] = None
    option_target: Optional[float] = None
    option_exit_premium: Optional[float] = None
    gross_pnl: float = 0.0
    total_statutory_charges: float = 0.0
    net_pnl_after_costs: float = 0.0


class SignalEvaluator:
    """
    Chronological Price-Path & Options Derivative Outcome Evaluator:
    - Evaluates signals at +1, +3, +5, +10, +15, +20 minute horizons.
    - Zero Horizon-State Contamination: Each horizon is evaluated independently from the entry point.
    - Strict SL-First Rule: If price touches Stop Loss first within the horizon, it is classified as STOP_HIT,
      even if the price later reverses and touches the target.
    - Records MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion).
    - Applies Indian statutory tax engine (STT, GST, Exchange, SEBI, Stamp Duty, Brokerage)
      to compute exact post-tax net P&L.
    """

    HORIZONS = [1, 3, 5, 10, 15, 20]

    @classmethod
    def evaluate_path(
        cls,
        signal_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
        df_1m_future: pd.DataFrame,
        option_strike: Optional[float] = None,
        option_type: Optional[str] = None,
        option_entry: Optional[float] = None,
        option_sl: Optional[float] = None,
        option_target: Optional[float] = None,
        delta: float = 0.55
    ) -> SignalEvaluationReport:
        is_buy = (direction == "BUY")
        results: List[HorizonResult] = []

        overall_mfe = 0.0
        overall_mae = 0.0

        final_opt_exit = option_entry or 100.0
        final_cost_info = {"gross_pnl": 0.0, "total_costs": 0.0, "net_pnl": 0.0}

        # Evaluate each forward horizon independently from Entry
        for h in cls.HORIZONS:
            subset = df_1m_future.iloc[:h]
            if subset.empty:
                continue

            mfe = 0.0
            mae = 0.0
            h_result: Literal["TARGET_HIT", "STOP_HIT", "TIMEOUT", "NO_DECISIVE_MOVE"] = "TIMEOUT"
            hit_minute: Optional[int] = None
            h_stopped_out = False
            h_target_hit = False

            # Walk through the subset candles chronologically for this horizon
            for minute_idx, (_, row) in enumerate(subset.iterrows(), start=1):
                high = float(row['high'])
                low = float(row['low'])
                close = float(row['close'])

                if is_buy:
                    fav = high - entry_price
                    adv = entry_price - low
                    mfe = max(mfe, fav)
                    mae = max(mae, adv)

                    # Strict SL touch check
                    if low <= stop_loss and not h_target_hit:
                        h_stopped_out = True
                        h_result = "STOP_HIT"
                        hit_minute = minute_idx
                        break

                    # Check Target touch
                    if high >= target_1 and not h_stopped_out:
                        h_target_hit = True
                        h_result = "TARGET_HIT"
                        hit_minute = minute_idx
                        break
                else:
                    fav = entry_price - low
                    adv = high - entry_price
                    mfe = max(mfe, fav)
                    mae = max(mae, adv)

                    # Strict SL touch check
                    if high >= stop_loss and not h_target_hit:
                        h_stopped_out = True
                        h_result = "STOP_HIT"
                        hit_minute = minute_idx
                        break

                    # Check Target touch
                    if low <= target_1 and not h_stopped_out:
                        h_target_hit = True
                        h_result = "TARGET_HIT"
                        hit_minute = minute_idx
                        break

            last_close = float(subset['close'].iloc[-1])
            if is_buy:
                pnl = (target_1 - entry_price) if h_result == "TARGET_HIT" else (
                    (stop_loss - entry_price) if h_result == "STOP_HIT" else (last_close - entry_price)
                )
            else:
                pnl = (entry_price - target_1) if h_result == "TARGET_HIT" else (
                    (entry_price - stop_loss) if h_result == "STOP_HIT" else (entry_price - last_close)
                )

            if h_result == "TIMEOUT":
                if abs(pnl) < 5.0:
                    h_result = "NO_DECISIVE_MOVE"

            # Calculate Option Premium Exit & Statutory Taxes
            opt_entry_val = option_entry or 100.0
            if h_result == "TARGET_HIT":
                opt_exit_val = option_target or (opt_entry_val + 30.0)
            elif h_result == "STOP_HIT":
                opt_exit_val = option_sl or max(1.0, opt_entry_val - 20.0)
            else:
                opt_exit_val = max(1.0, opt_entry_val + (pnl * delta))

            cost_info = calculate_option_trade_costs(
                entry_premium=opt_entry_val,
                exit_premium=opt_exit_val,
                lot_size=None,
                lots=1
            )
            final_opt_exit = opt_exit_val
            final_cost_info = cost_info

            results.append(HorizonResult(
                horizon_minutes=h,
                exit_price=last_close,
                mfe=round(mfe, 2),
                mae=round(mae, 2),
                result=h_result,
                points_pnl=round(pnl, 2),
                option_exit_premium=round(opt_exit_val, 2),
                option_gross_pnl=cost_info["gross_pnl"],
                statutory_costs=cost_info["total_costs"],
                option_net_pnl=cost_info["net_pnl"],
                time_to_hit_minutes=hit_minute
            ))

            overall_mfe = max(overall_mfe, mfe)
            overall_mae = max(overall_mae, mae)

        final_result = results[-1].result if results else "TIMEOUT"

        return SignalEvaluationReport(
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            horizon_evaluations=results,
            final_result=final_result,
            overall_mfe=round(overall_mfe, 2),
            overall_mae=round(overall_mae, 2),
            option_strike=option_strike,
            option_type=option_type,
            option_entry=option_entry,
            option_sl=option_sl,
            option_target=option_target,
            option_exit_premium=round(final_opt_exit, 2),
            gross_pnl=final_cost_info["gross_pnl"],
            total_statutory_charges=final_cost_info["total_costs"],
            net_pnl_after_costs=final_cost_info["net_pnl"]
        )
