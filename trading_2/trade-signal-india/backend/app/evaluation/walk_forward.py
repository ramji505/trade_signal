"""
Institutional Walk-Forward Optimization, Purged & Embargoed Cross-Validation, and Deflated Sharpe Ratio (DSR) Engine.
Implements Marcos López de Prado's quantitative validation standards:
- Purged & Embargoed cross-validation splits (prevents label overlap and serial correlation leakage).
- Walk Forward Efficiency (WFE) ratio: WFE = Out-of-Sample PF / In-Sample PF.
- Deflated Sharpe Ratio (DSR) accounting for multiple testing, skewness, and fat-tailed kurtosis.
- Multi-stress testing matrix (2x/3x slippage, wider bid-ask spreads).
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import math


def norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


@dataclass
class DeflatedSharpeResult:
    standard_sharpe: float
    deflated_sharpe_ratio: float
    p_value: float
    estimated_trials: int
    skewness: float
    kurtosis: float
    is_statistically_genuine: bool


@dataclass
class WalkForwardWindowResult:
    window_id: int
    train_trades_count: int
    test_trades_count: int
    purged_trades_count: int
    train_profit_factor: float
    test_profit_factor: float
    oos_efficiency_ratio: float  # Test PF / Train PF (> 0.70 desired)
    net_pnl_rupees: float
    pass_window: bool


class QuantitativeEdgeValidator:
    """
    Computes Deflated Sharpe Ratio (DSR) and executes purged rolling walk-forward cross-validation.
    """

    @staticmethod
    def calculate_deflated_sharpe(
        returns: List[float],
        estimated_trials: int = 100,
        benchmark_sharpe: float = 0.0
    ) -> DeflatedSharpeResult:
        if not returns or len(returns) < 10:
            return DeflatedSharpeResult(
                standard_sharpe=0.0,
                deflated_sharpe_ratio=0.0,
                p_value=1.0,
                estimated_trials=estimated_trials,
                skewness=0.0,
                kurtosis=3.0,
                is_statistically_genuine=False
            )

        arr = np.array(returns)
        n = len(arr)
        mean_ret = np.mean(arr)
        std_ret = np.std(arr, ddof=1)

        if std_ret <= 1e-8:
            return DeflatedSharpeResult(0.0, 0.0, 1.0, estimated_trials, 0.0, 3.0, False)

        sharpe = (mean_ret / std_ret) * math.sqrt(252)  # Annualized

        # Moments
        diff = arr - mean_ret
        skew = float(np.mean((diff / std_ret) ** 3))
        kurt = float(np.mean((diff / std_ret) ** 4))

        # Euler-Mascheroni constant
        euler = 0.5772156649
        expected_max_sharpe = benchmark_sharpe + math.sqrt(2.0 * math.log(max(1, estimated_trials))) + (euler / math.sqrt(2.0 * math.log(max(2, estimated_trials))))

        # Standard error of Sharpe ratio
        var_sr = (1.0 - skew * sharpe + ((kurt - 1.0) / 4.0) * (sharpe ** 2)) / max(1, n - 1)
        std_sr = math.sqrt(max(1e-6, var_sr))

        dsr_stat = (sharpe - expected_max_sharpe) / std_sr
        dsr_prob = norm_cdf(dsr_stat)
        p_val = 1.0 - dsr_prob

        return DeflatedSharpeResult(
            standard_sharpe=round(sharpe, 2),
            deflated_sharpe_ratio=round(dsr_prob, 4),
            p_value=round(p_val, 4),
            estimated_trials=estimated_trials,
            skewness=round(skew, 2),
            kurtosis=round(kurt, 2),
            is_statistically_genuine=(dsr_prob >= 0.90)  # >90% probability it is not overfit luck
        )

    @staticmethod
    def run_walk_forward_splits(
        trades: List[Dict[str, Any]],
        num_windows: int = 4,
        train_ratio: float = 0.70,
        embargo_ratio: float = 0.05
    ) -> List[WalkForwardWindowResult]:
        """
        Executes Purged & Embargoed rolling walk-forward splits to prevent label overlap leakage.
        """
        if len(trades) < 20:
            return []

        chunk_size = len(trades) // num_windows
        results = []

        for w_idx in range(num_windows):
            start = w_idx * chunk_size
            end = min(len(trades), (w_idx + 1) * chunk_size if w_idx < num_windows - 1 else len(trades))
            window_trades = trades[start:end]

            split_pt = int(len(window_trades) * train_ratio)
            embargo_count = max(1, int(len(window_trades) * embargo_ratio))

            train_set = window_trades[:split_pt]
            # Purge & Embargo window to separate train and test
            test_start = min(len(window_trades), split_pt + embargo_count)
            test_set = window_trades[test_start:]

            def calc_pf(t_list):
                if not t_list:
                    return 0.0
                g_win = sum(float(t.get("net_pnl_after_costs", 0.0)) for t in t_list if float(t.get("net_pnl_after_costs", 0.0)) > 0)
                g_loss = abs(sum(float(t.get("net_pnl_after_costs", 0.0)) for t in t_list if float(t.get("net_pnl_after_costs", 0.0)) < 0))
                return round(g_win / g_loss, 2) if g_loss > 0 else (9.99 if g_win > 0 else 0.0)

            train_pf = calc_pf(train_set)
            test_pf = calc_pf(test_set)
            net_test_pnl = sum(float(t.get("net_pnl_after_costs", 0.0)) for t in test_set)

            eff_ratio = round(test_pf / train_pf, 2) if train_pf > 0 else 0.0
            pass_win = (test_pf >= 1.20) and (eff_ratio >= 0.65) and (net_test_pnl > 0)

            results.append(WalkForwardWindowResult(
                window_id=w_idx + 1,
                train_trades_count=len(train_set),
                test_trades_count=len(test_set),
                purged_trades_count=embargo_count,
                train_profit_factor=train_pf,
                test_profit_factor=test_pf,
                oos_efficiency_ratio=eff_ratio,
                net_pnl_rupees=round(net_test_pnl, 2),
                pass_window=pass_win
            ))

        return results

    @staticmethod
    def calculate_wfe(train_pf: float, test_pf: float) -> Dict[str, Any]:
        """
        Calculates Walk Forward Efficiency (WFE) ratio: WFE = Test PF / Train PF.
        WFE < 0.50: Fragile / Over-optimized
        WFE 0.50 - 0.70: Acceptable
        WFE >= 0.70: Robust institutional grade
        """
        if train_pf <= 0:
            return {"wfe": 0.0, "status": "INVALID_TRAIN_PF", "is_robust": False}

        wfe = round(test_pf / train_pf, 3)
        if wfe >= 0.70:
            status = "ROBUST_EDGE"
            is_robust = True
        elif wfe >= 0.50:
            status = "ACCEPTABLE"
            is_robust = True
        else:
            status = "FRAGILE_OVERFIT"
            is_robust = False

        return {
            "wfe_ratio": wfe,
            "train_profit_factor": round(train_pf, 2),
            "test_profit_factor": round(test_pf, 2),
            "status": status,
            "is_robust": is_robust,
            "recommendation": "Deployable" if is_robust else "Do not trade live - parameter curve fitting detected"
        }

    @staticmethod
    def run_stress_test_matrix(
        trades: List[Dict[str, Any]],
        slippage_multipliers: List[float] = [1.0, 2.0, 3.0],
        spread_multipliers: List[float] = [1.0, 1.5, 2.0]
    ) -> List[Dict[str, Any]]:
        """
        Evaluates strategy survival across 2x/3x slippage, wider bid-ask spreads, and fee shocks.
        """
        matrix_results = []
        for slip_mult in slippage_multipliers:
            for spread_mult in spread_multipliers:
                adjusted_pnls = []
                for t in trades:
                    raw_net = float(t.get("net_pnl_after_costs", t.get("pnl_points", 0.0)))
                    stat_cost = float(t.get("statutory_costs_rs", t.get("statutory_costs", 50.0)))
                    # Inject spread and slippage stress shock
                    penalty = (stat_cost * (spread_mult - 1.0) * 0.5) + (25.0 * (slip_mult - 1.0))
                    adjusted_pnls.append(raw_net - penalty)

                total_net = sum(adjusted_pnls)
                win_count = sum(1 for p in adjusted_pnls if p > 0)
                tot = len(adjusted_pnls)
                wr = round((win_count / tot) * 100.0, 1) if tot > 0 else 0.0

                g_win = sum(p for p in adjusted_pnls if p > 0)
                g_loss = abs(sum(p for p in adjusted_pnls if p < 0))
                pf = round(g_win / g_loss, 2) if g_loss > 0 else (9.99 if g_win > 0 else 0.0)

                matrix_results.append({
                    "slippage_multiplier": slip_mult,
                    "spread_multiplier": spread_mult,
                    "stressed_net_pnl_rupees": round(total_net, 2),
                    "stressed_win_rate_pct": wr,
                    "stressed_profit_factor": pf,
                    "survives_stress": (total_net > 0 and pf >= 1.10)
                })

        return matrix_results
