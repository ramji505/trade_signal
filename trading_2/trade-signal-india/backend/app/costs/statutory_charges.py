"""Configurable Indian F&O transaction-cost engine (current defaults: Oct 2026)."""
from typing import Dict, Any, Optional
from app.core.config import settings


def _default_lot(symbol: str = "NIFTY") -> int:
    return {
        "NIFTY": settings.NIFTY_LOT_SIZE,
        "BANKNIFTY": settings.BANKNIFTY_LOT_SIZE,
        "FINNIFTY": settings.FINNIFTY_LOT_SIZE,
        "MIDCPNIFTY": settings.MIDCPNIFTY_LOT_SIZE,
    }.get(symbol.upper(), settings.NIFTY_LOT_SIZE)


def calculate_option_trade_costs(
    entry_premium: float,
    exit_premium: float,
    lot_size: Optional[int] = None,
    lots: int = 1,
    brokerage_per_order: Optional[float] = None,
    symbol: str = "NIFTY",
) -> Dict[str, Any]:
    lot_size = int(lot_size or _default_lot(symbol))
    brokerage_per_order = float(brokerage_per_order if brokerage_per_order is not None else settings.BROKERAGE_PER_ORDER)
    quantity = lot_size * lots
    buy_turnover = entry_premium * quantity
    sell_turnover = exit_premium * quantity
    total_turnover = buy_turnover + sell_turnover
    gross_pnl = (exit_premium - entry_premium) * quantity

    brokerage = brokerage_per_order * 2.0
    stt = sell_turnover * settings.OPTION_SELL_STT_RATE
    exchange_charge = total_turnover * settings.OPTION_EXCHANGE_TURNOVER_RATE
    sebi_charge = total_turnover * (settings.SEBI_TURNOVER_PER_CRORE / 1e7)
    stamp_duty = buy_turnover * settings.OPTION_STAMP_DUTY_RATE
    gst = (brokerage + exchange_charge + sebi_charge) * settings.GST_RATE
    total_costs = brokerage + stt + exchange_charge + sebi_charge + stamp_duty + gst

    return {
        "quantity": quantity,
        "buy_turnover": round(buy_turnover, 2),
        "sell_turnover": round(sell_turnover, 2),
        "total_turnover": round(total_turnover, 2),
        "gross_pnl": round(gross_pnl, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charge": round(exchange_charge, 4),
        "exchange_charges": round(exchange_charge, 4),
        "sebi_charge": round(sebi_charge, 4),
        "stamp_duty": round(stamp_duty, 2),
        "gst": round(gst, 2),
        "total_costs": round(total_costs, 2),
        "net_pnl": round(gross_pnl - total_costs, 2),
        "breakeven_points": round(total_costs / quantity, 4),
        "lot_size": lot_size,
        "stt_rate": settings.OPTION_SELL_STT_RATE,
    }


def calculate_statutory_charges(entry_price: float, exit_price: float, lot_size: Optional[int] = None, lots: int = 1, symbol: str = "NIFTY") -> Dict[str, Any]:
    """Compatibility wrapper used by earlier tests/modules."""
    r = calculate_option_trade_costs(entry_price, exit_price, lot_size=lot_size, lots=lots, symbol=symbol)
    return {
        "brokerage": r["brokerage"],
        "stt": r["stt"],
        "exchange_charges": r["exchange_charges"],
        "sebi_charges": r["sebi_charge"],
        "stamp_duty": r["stamp_duty"],
        "gst": r["gst"],
        "total_charges": r["total_costs"],
        "net_pnl": r["net_pnl"],
        **r,
    }
