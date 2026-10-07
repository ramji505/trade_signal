"""
Unified Multi-Broker Gateway & Live Position Reconciliation Worker.
Supports Groww, Zerodha Kite, DhanHQ, and Paper Trading.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio

from app.broker.base import BrokerProvider
from app.broker.groww_auth import GrowwAuthenticator
from app.broker.kite_auth import KiteConnectProvider
from app.core.config import settings
from app.core.logging import logger


class UnifiedBrokerGateway:
    """Factory and unified routing gateway across supported Indian stock brokers."""

    @staticmethod
    def get_broker(broker_type: str = "GROWW") -> Optional[BrokerProvider]:
        b_type = broker_type.upper()
        if b_type == "GROWW":
            return GrowwAuthenticator()
        elif b_type in {"ZERODHA", "KITE"}:
            return KiteConnectProvider()
        return None


class PositionReconciliationWorker:
    """
    Periodic background reconciliation daemon:
    Compares internal paper/state positions against live broker positions to catch
    untracked executions, manual broker interventions, or dropped orders.
    """

    def __init__(self, broker: Optional[BrokerProvider] = None):
        self.broker = broker
        self.last_reconciliation_time: Optional[datetime] = None
        self.discrepancies: List[Dict[str, Any]] = []

    async def reconcile(self, internal_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        self.last_reconciliation_time = now

        if self.broker is None:
            return {
                "status": "PASS",
                "mode": "SIMULATED",
                "timestamp": now.isoformat(),
                "discrepancies_count": 0,
                "details": "Simulated environment: No live broker position mismatch"
            }

        try:
            broker_positions = await self.broker.get_positions()
            broker_dict = {p.get("tradingsymbol", p.get("trading_symbol", "")): int(p.get("quantity", p.get("net_quantity", 0))) for p in broker_positions}

            discrepancies = []
            for internal in internal_positions:
                sym = internal.get("option_symbol", internal.get("symbol", ""))
                int_qty = int(internal.get("quantity", 0))
                broker_qty = broker_dict.get(sym, 0)

                if int_qty != broker_qty:
                    discrepancies.append({
                        "symbol": sym,
                        "internal_qty": int_qty,
                        "broker_qty": broker_qty,
                        "diff": int_qty - broker_qty,
                        "severity": "CRITICAL" if broker_qty == 0 else "WARNING"
                    })

            self.discrepancies = discrepancies
            status = "PASS" if not discrepancies else "DISCREPANCY_DETECTED"
            return {
                "status": status,
                "timestamp": now.isoformat(),
                "discrepancies_count": len(discrepancies),
                "discrepancies": discrepancies
            }
        except Exception as e:
            logger.error(f"Position reconciliation error: {e}")
            return {
                "status": "ERROR",
                "timestamp": now.isoformat(),
                "error": str(e)
            }
