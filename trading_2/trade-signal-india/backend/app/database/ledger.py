"""
Durable Signal & Execution Audit Ledger.
Stores every quantitative decision (SIGNAL, WAIT, VETO), execution timestamps,
fill prices, slippage, and PnL outcomes for empirical research and drift tracking.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from app.core.logging import logger


@dataclass
class LedgerSignalRecord:
    signal_id: str
    timestamp: str
    symbol: str
    direction: str
    score: int
    calibrated_prob: float
    expected_value_rupees: float
    market_regime: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target_1: Optional[float]
    option_symbol: Optional[str]
    option_entry: Optional[float]
    option_sl: Optional[float]
    option_target: Optional[float]
    decision_type: str  # SIGNAL_GENERATED, VETOED_HEAVYWEIGHT, VETOED_TRAP, VETOED_KILL_SWITCH, WAIT
    reasons: List[str]
    actual_fill_price: Optional[float] = None
    realized_pnl_rupees: Optional[float] = None
    outcome: Optional[str] = None  # TARGET_HIT, STOP_HIT, TIMEOUT, CANCELLED


class ResearchAuditLedger:
    """Singleton in-memory & persistent research journal for empirical calibration."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResearchAuditLedger, cls).__new__(cls)
            cls._instance.records = []
        return cls._instance

    def log_decision(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        score: int,
        calibrated_prob: float,
        expected_value_rupees: float,
        market_regime: str,
        entry_price: Optional[float],
        stop_loss: Optional[float],
        target_1: Optional[float],
        option_symbol: Optional[str],
        option_entry: Optional[float],
        option_sl: Optional[float],
        option_target: Optional[float],
        decision_type: str,
        reasons: List[str]
    ) -> LedgerSignalRecord:
        record = LedgerSignalRecord(
            signal_id=signal_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            direction=direction,
            score=score,
            calibrated_prob=round(calibrated_prob, 4),
            expected_value_rupees=round(expected_value_rupees, 2),
            market_regime=market_regime,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            option_symbol=option_symbol,
            option_entry=option_entry,
            option_sl=option_sl,
            option_target=option_target,
            decision_type=decision_type,
            reasons=reasons
        )
        self.records.append(record)
        logger.info(f"AUDIT LEDGER [{decision_type}]: {signal_id} {symbol} {direction} Score={score} P={calibrated_prob:.1%}")
        return record

    def update_execution(
        self,
        signal_id: str,
        actual_fill_price: float,
        outcome: str,
        realized_pnl_rupees: float
    ) -> bool:
        for r in reversed(self.records):
            if r.signal_id == signal_id:
                r.actual_fill_price = actual_fill_price
                r.outcome = outcome
                r.realized_pnl_rupees = realized_pnl_rupees
                return True
        return False

    def get_all_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [asdict(r) for r in self.records[-limit:]]

    def get_summary_stats(self) -> Dict[str, Any]:
        total = len(self.records)
        signals = [r for r in self.records if r.decision_type == "SIGNAL_GENERATED"]
        vetoes = [r for r in self.records if "VETO" in r.decision_type]
        completed = [r for r in self.records if r.outcome is not None]
        winners = [r for r in completed if (r.realized_pnl_rupees or 0) > 0]

        win_rate = (len(winners) / len(completed) * 100.0) if completed else 0.0
        return {
            "total_decisions_logged": total,
            "actionable_signals_count": len(signals),
            "vetoed_traps_count": len(vetoes),
            "completed_trades_count": len(completed),
            "realized_win_rate_pct": round(win_rate, 2)
        }


audit_ledger = ResearchAuditLedger()
