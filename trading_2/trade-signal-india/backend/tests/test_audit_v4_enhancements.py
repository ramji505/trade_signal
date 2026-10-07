import pytest
import pandas as pd
from datetime import datetime, timezone

from app.ml.probability_calibrator import ProbabilityCalibrator
from app.database.ledger import ResearchAuditLedger
from app.strategy.key_levels import KeyLevelsEngine
from app.broker.execution_adapter import SmartExecutionAdapter
from app.evaluation.walk_forward import QuantitativeEdgeValidator
from fastapi.testclient import TestClient
from app.main import app


def test_probability_calibrator():
    res = ProbabilityCalibrator.calibrate(
        raw_score=92,
        market_regime="STRONG_TREND_BULLISH",
        target_pts=28.0,
        stop_loss_pts=14.0,
        lot_size=65
    )
    assert res.calibrated_win_prob >= 0.65
    assert res.expected_value_points > 0
    assert res.expected_value_rupees > 0
    assert res.meta_label_verdict == "ACCEPT"

    # Test below threshold / low score calibration
    res_low = ProbabilityCalibrator.calibrate(
        raw_score=60,
        market_regime="CHOPPY_RANGE"
    )
    assert res_low.calibrated_win_prob <= 0.45
    assert res_low.meta_label_verdict == "REJECT"


def test_research_audit_ledger():
    ledger = ResearchAuditLedger()
    record = ledger.log_decision(
        signal_id="SIG-TEST-001",
        symbol="NIFTY",
        direction="BUY",
        score=88,
        calibrated_prob=0.68,
        expected_value_rupees=550.0,
        market_regime="STRONG_TREND_BULLISH",
        entry_price=22500.0,
        stop_loss=22486.0,
        target_1=22528.0,
        option_symbol="NIFTY22500CE",
        option_entry=110.0,
        option_sl=96.0,
        option_target=138.0,
        decision_type="SIGNAL_GENERATED",
        reasons=["Test reason"]
    )
    assert record.signal_id == "SIG-TEST-001"
    assert record.calibrated_prob == 0.68

    # Update execution
    updated = ledger.update_execution("SIG-TEST-001", 110.5, "TARGET_HIT", 1820.0)
    assert updated is True

    stats = ledger.get_summary_stats()
    assert stats["total_decisions_logged"] >= 1
    assert stats["actionable_signals_count"] >= 1


def test_point_in_time_key_levels_swing_pivots():
    # Build sample intraday dataframe
    data = {
        "open": [22000 + i * 5 for i in range(30)],
        "high": [22000 + i * 5 + 10 for i in range(30)],
        "low": [22000 + i * 5 - 5 for i in range(30)],
        "close": [22000 + i * 5 + 8 for i in range(30)],
        "volume": [1000] * 30
    }
    df = pd.DataFrame(data)
    snap = KeyLevelsEngine.calculate(current_price=22100.0, df_intraday=df)

    assert snap.day_open == 22000.0
    assert snap.orh >= snap.orl
    assert snap.distance_to_resistance_pts > 0
    assert snap.distance_to_support_pts > 0
    assert isinstance(snap.swing_highs, list)
    assert isinstance(snap.swing_lows, list)


def test_execution_adapter_idempotency_and_partial_fill():
    import asyncio
    async def _run():
        adapter = SmartExecutionAdapter(broker=None)
        now = datetime.now(timezone.utc)
        ref_id = "REF-UNIQUE-TEST-123"

        res1 = await adapter.execute_smart_order(
            symbol="NIFTY22600CE",
            direction="BUY",
            limit_price=120.0,
            quantity=65,
            signal_timestamp=now,
            order_reference_id=ref_id
        )
        assert res1["status"] == "FILLED"
        assert res1["order_reference_id"] == ref_id

        # Duplicate call with same reference ID must be rejected/ignored
        res2 = await adapter.execute_smart_order(
            symbol="NIFTY22600CE",
            direction="BUY",
            limit_price=120.0,
            quantity=65,
            signal_timestamp=now,
            order_reference_id=ref_id
        )
        assert res2["status"] == "DUPLICATE_IGNORED"

    asyncio.run(_run())


def test_purged_embargoed_walk_forward():
    sample_trades = [
        {"net_pnl_after_costs": 1500.0 if i % 2 == 0 else -600.0, "pnl_points": 20.0}
        for i in range(40)
    ]
    wf_results = QuantitativeEdgeValidator.run_walk_forward_splits(
        trades=sample_trades,
        num_windows=2,
        train_ratio=0.70,
        embargo_ratio=0.05
    )
    assert len(wf_results) == 2
    assert wf_results[0].purged_trades_count >= 1
    assert wf_results[0].train_profit_factor > 0


def test_execution_api_routes():
    client = TestClient(app)
    res_pos = client.post("/execution/position-size", json={
        "account_equity": 100000.0,
        "risk_pct": 0.01,
        "entry_price": 22500.0,
        "stop_loss": 22485.0,
        "symbol": "NIFTY"
    })
    assert res_pos.status_code == 200
    data = res_pos.json()
    assert data["allowed"] is True
    assert data["lots"] >= 1

    res_audit = client.get("/execution/audit-ledger?limit=10")
    assert res_audit.status_code == 200
    assert "summary" in res_audit.json()
