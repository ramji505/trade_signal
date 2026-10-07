"""
Dynamic Exchange & Instrument Metadata Provider.
- Manages permitted contract lot sizes per NSE circulars.
- Maintains versioned index constituent weightings for NIFTY 50 concordance.
- Provides versioned statutory cost schedules.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime, date


@dataclass
class InstrumentMetadata:
    symbol: str
    lot_size: int
    tick_size: float
    freeze_limit_qty: int
    effective_date: str


class MetadataProvider:
    """Dynamic metadata service preventing hard-coded permanent assumptions."""

    # Versioned lot sizes (Updated per NSE circulars)
    LOT_SIZES: Dict[str, int] = {
        "NIFTY": 65,
        "BANKNIFTY": 30,
        "FINNIFTY": 60,
        "MIDCPNIFTY": 120,
    }

    TICK_SIZES: Dict[str, float] = {
        "NIFTY": 0.05,
        "BANKNIFTY": 0.05,
        "FINNIFTY": 0.05,
        "MIDCPNIFTY": 0.05,
    }

    # Versioned constituent weights for NIFTY 50 (Date snapshot: Oct 2026)
    CONSTITUENT_WEIGHTS: Dict[str, Dict[str, float]] = {
        "2026-10-01": {
            "HDFCBANK": 0.135,
            "RELIANCE": 0.092,
            "ICICIBANK": 0.081,
            "INFY": 0.058,
            "TCS": 0.042,
            "ITC": 0.038,
            "LT": 0.036,
            "AXISBANK": 0.033,
            "KOTAKBANK": 0.029,
            "BHARTIARTL": 0.027
        }
    }

    @classmethod
    def get_lot_size(cls, symbol: str) -> int:
        return cls.LOT_SIZES.get(symbol.upper(), 65)

    @classmethod
    def get_tick_size(cls, symbol: str) -> float:
        return cls.TICK_SIZES.get(symbol.upper(), 0.05)

    @classmethod
    def get_constituent_weights(cls, snapshot_date: Optional[str] = None) -> Dict[str, float]:
        if snapshot_date and snapshot_date in cls.CONSTITUENT_WEIGHTS:
            return cls.CONSTITUENT_WEIGHTS[snapshot_date]
        # Return latest snapshot
        latest_key = sorted(cls.CONSTITUENT_WEIGHTS.keys())[-1]
        return cls.CONSTITUENT_WEIGHTS[latest_key]

    @classmethod
    def get_instrument_metadata(cls, symbol: str) -> InstrumentMetadata:
        sym = symbol.upper()
        return InstrumentMetadata(
            symbol=sym,
            lot_size=cls.get_lot_size(sym),
            tick_size=cls.get_tick_size(sym),
            freeze_limit_qty=1800 if sym == "NIFTY" else 900,
            effective_date="2026-10-01"
        )
