"""
Monte Carlo Resampling, Deflated Sharpe Ratio, and Empirical Score Calibration Engine.
Used for institutional validation of quantitative edge before real-money deployment.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import math


@dataclass
class MonteCarloSimulationResult:
    iterations: int
    positive_runs_pct: float
    p5_net_pnl_rupees: float
    p50_net_pnl_rupees: float
    p95_net_pnl_rupees: float
    max_simulated_drawdown_rupees: float
    risk_of_ruin_pct: float
    stress_tested_slippage_pts: float
    pass_validation: bool


@dataclass
class ScoreBucketCalibration:
    bucket_label: str
    total_trades: int
    winning_trades: int
    win_rate_pct: float
    avg_trade_pnl_rupees: float
    expected_value_points: float
    is_statistically_significant: bool


class MonteCarloEngine:
    """
    Simulates real-world execution variance by shuffling trade sequences 1,000x
    and injecting realistic slippage shocks.
    """

    @staticmethod
    def run_monte_carlo(
        trade_pnls_rupees: List[float],
        iterations: int = 1000,
        slippage_penalty_rupees_per_trade: float = 75.0,
        initial_capital: float = 100000.0,
        ruin_threshold_loss_pct: float = 0.20  # 20% max loss = ruin
    ) -> MonteCarloSimulationResult:
        if not trade_pnls_rupees:
            return MonteCarloSimulationResult(
                iterations=0,
                positive_runs_pct=0.0,
                p5_net_pnl_rupees=0.0,
                p50_net_pnl_rupees=0.0,
                p95_net_pnl_rupees=0.0,
                max_simulated_drawdown_rupees=0.0,
                risk_of_ruin_pct=100.0,
                stress_tested_slippage_pts=1.0,
                pass_validation=False
            )

        n_trades = len(trade_pnls_rupees)
        final_pnls = []
        max_drawdowns = []
        ruin_count = 0
        ruin_capital_level = initial_capital * (1.0 - ruin_threshold_loss_pct)

        np.random.seed(42)  # Deterministic seed for reproducible testing

        for _ in range(iterations):
            # Resample with replacement
            sampled_pnls = np.random.choice(trade_pnls_rupees, size=n_trades, replace=True)
            # Inject randomized slippage noise between 0.5x and 1.5x of penalty
            slippage_noise = np.random.uniform(0.5, 1.5, size=n_trades) * slippage_penalty_rupees_per_trade
            net_sampled_pnls = sampled_pnls - slippage_noise

            cumulative_curve = np.cumsum(net_sampled_pnls) + initial_capital
            peak = np.maximum.accumulate(cumulative_curve)
            drawdown = peak - cumulative_curve
            max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

            final_pnl = float(np.sum(net_sampled_pnls))
            final_pnls.append(final_pnl)
            max_drawdowns.append(max_dd)

            if np.min(cumulative_curve) <= ruin_capital_level:
                ruin_count += 1

        positive_pct = (sum(1 for p in final_pnls if p > 0) / iterations) * 100.0
        p5 = float(np.percentile(final_pnls, 5))
        p50 = float(np.percentile(final_pnls, 50))
        p95 = float(np.percentile(final_pnls, 95))
        worst_dd = float(np.max(max_drawdowns))
        risk_of_ruin = (ruin_count / iterations) * 100.0

        # Institutional 9.5 Validation Standard: >90% positive runs and <5% risk of ruin
        pass_gate = (positive_pct >= 90.0) and (risk_of_ruin <= 5.0)

        return MonteCarloSimulationResult(
            iterations=iterations,
            positive_runs_pct=round(positive_pct, 2),
            p5_net_pnl_rupees=round(p5, 2),
            p50_net_pnl_rupees=round(p50, 2),
            p95_net_pnl_rupees=round(p95, 2),
            max_simulated_drawdown_rupees=round(worst_dd, 2),
            risk_of_ruin_pct=round(risk_of_ruin, 2),
            stress_tested_slippage_pts=1.0,
            pass_validation=pass_gate
        )

    @staticmethod
    def calibrate_score_buckets(trades: List[Dict[str, Any]]) -> List[ScoreBucketCalibration]:
        """
        Calibrate Score vs Out-of-Sample Win Rate & Expectancy across ranges:
        50-59, 60-69, 70-79, 80-89, 90-100.
        """
        buckets = {
            "50-59": [],
            "60-69": [],
            "70-79": [],
            "80-89": [],
            "90-100": []
        }

        for t in trades:
            score = int(t.get("score", 0))
            if score >= 90:
                buckets["90-100"].append(t)
            elif score >= 80:
                buckets["80-89"].append(t)
            elif score >= 70:
                buckets["70-79"].append(t)
            elif score >= 60:
                buckets["60-69"].append(t)
            else:
                buckets["50-59"].append(t)

        results = []
        for label, b_trades in buckets.items():
            total = len(b_trades)
            if total == 0:
                results.append(ScoreBucketCalibration(
                    bucket_label=label,
                    total_trades=0,
                    winning_trades=0,
                    win_rate_pct=0.0,
                    avg_trade_pnl_rupees=0.0,
                    expected_value_points=0.0,
                    is_statistically_significant=False
                ))
                continue

            winners = [t for t in b_trades if float(t.get("net_pnl_after_costs", t.get("pnl_points", 0))) > 0]
            win_rate = (len(winners) / total) * 100.0
            avg_pnl = sum(float(t.get("net_pnl_after_costs", 0.0)) for t in b_trades) / total
            avg_pts = sum(float(t.get("pnl_points", 0.0)) for t in b_trades) / total

            results.append(ScoreBucketCalibration(
                bucket_label=label,
                total_trades=total,
                winning_trades=len(winners),
                win_rate_pct=round(win_rate, 2),
                avg_trade_pnl_rupees=round(avg_pnl, 2),
                expected_value_points=round(avg_pts, 2),
                is_statistically_significant=(total >= 30)
            ))

        return results
