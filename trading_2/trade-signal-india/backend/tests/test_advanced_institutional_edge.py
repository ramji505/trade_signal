"""
Advanced Institutional Edge Regression Tests:
Tests Heavyweight Concordance, Multi-Broker Gateway, Position Reconciliation,
and Deflated Sharpe Ratio (DSR) Walk-Forward Validation.
"""

import pytest
from app.strategy.heavyweight_concordance import HeavyweightConcordanceEngine
from app.broker.unified_gateway import UnifiedBrokerGateway, PositionReconciliationWorker
from app.broker.kite_auth import KiteConnectProvider
from app.evaluation.walk_forward import QuantitativeEdgeValidator


def test_heavyweight_concordance():
    """Validates NIFTY heavyweights alignment (HDFCBANK, RELIANCE, etc.)."""
    # All major components bullish -> PASS for BUY
    bullish_trends = {
        "HDFCBANK": "BULLISH",
        "RELIANCE": "BULLISH",
        "ICICIBANK": "BULLISH",
        "INFY": "BULLISH",
        "BANKNIFTY": "BULLISH"
    }
    res_buy = HeavyweightConcordanceEngine.evaluate(bullish_trends, "BUY")
    assert res_buy.recommendation == "PASS"
    assert res_buy.concordance_score > 0.5
    assert "HDFCBANK" in res_buy.leading_stocks

    # NIFTY triggering BUY while HDFCBANK & RELIANCE are collapsing -> VETO
    divergent_trends = {
        "HDFCBANK": "BEARISH",
        "RELIANCE": "BEARISH",
        "ICICIBANK": "BEARISH",
        "INFY": "NEUTRAL",
        "BANKNIFTY": "BEARISH"
    }
    res_veto = HeavyweightConcordanceEngine.evaluate(divergent_trends, "BUY")
    assert res_veto.recommendation == "VETO"
    assert not res_veto.is_aligned_for_buy


def test_unified_broker_gateway():
    """Validates multi-broker provider instantiation."""
    groww_broker = UnifiedBrokerGateway.get_broker("GROWW")
    assert groww_broker is not None

    kite_broker = UnifiedBrokerGateway.get_broker("ZERODHA")
    assert isinstance(kite_broker, KiteConnectProvider)


def test_position_reconciliation_simulated():
    """Validates simulated position reconciliation daemon."""
    worker = PositionReconciliationWorker(broker=None)
    mock_positions = [{"symbol": "NIFTY26OCT25000CE", "quantity": 65}]
    res = pytest.importorskip("asyncio").run(worker.reconcile(mock_positions))
    assert res["status"] == "PASS"
    assert res["discrepancies_count"] == 0


def test_deflated_sharpe_ratio_and_walk_forward():
    """Validates Deflated Sharpe Ratio calculation and walk-forward splits."""
    # 40 mock trades
    mock_returns = [0.005, 0.008, -0.003, 0.010, -0.004, 0.006, 0.007, -0.002] * 5
    dsr = QuantitativeEdgeValidator.calculate_deflated_sharpe(mock_returns, estimated_trials=50)

    assert dsr.standard_sharpe > 0
    assert 0.0 <= dsr.deflated_sharpe_ratio <= 1.0

    mock_trades = [
        {"net_pnl_after_costs": 1500.0, "entry_price": 25000.0},
        {"net_pnl_after_costs": -500.0, "entry_price": 25000.0},
        {"net_pnl_after_costs": 1200.0, "entry_price": 25000.0},
        {"net_pnl_after_costs": 800.0, "entry_price": 25000.0},
        {"net_pnl_after_costs": -400.0, "entry_price": 25000.0},
    ] * 6 # 30 trades

    wf = QuantitativeEdgeValidator.run_walk_forward_splits(mock_trades, num_windows=3)
    assert len(wf) == 3
    assert wf[0].train_trades_count > 0
    assert wf[0].test_trades_count > 0
