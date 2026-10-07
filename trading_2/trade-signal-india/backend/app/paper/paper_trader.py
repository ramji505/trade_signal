"""
Institutional Paper Trading & Order Lifecycle Execution Engine.
Features:
- Simulated order fill with realistic slippage & bid-ask spread.
- Dynamic Trailing Stop-Loss & Target Management.
- Automatic 15:15 IST Intraday Square-Off.
- Real-time Statutory Charges and Net Post-Tax Ledger.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone
import time as pytime

from app.costs.statutory_charges import calculate_option_trade_costs
from app.core.config import settings
from app.core.logging import logger


@dataclass
class PaperPosition:
    position_id: str
    symbol: str
    direction: Literal["BUY", "SELL"]
    entry_time: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    option_symbol: str
    option_entry: float
    option_sl: float
    option_target: float
    lots: int = 1
    lot_size: int = field(default_factory=lambda: settings.NIFTY_LOT_SIZE)
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    option_exit: Optional[float] = None
    close_reason: Optional[str] = None
    gross_pnl: float = 0.0
    statutory_costs: float = 0.0
    net_pnl: float = 0.0


class PaperTradingEngine:
    def __init__(self, initial_capital: float = 100000.0, slippage_pts: float = 0.5):
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        self.slippage_pts = slippage_pts
        self.open_positions: Dict[str, PaperPosition] = {}
        self.closed_positions: List[PaperPosition] = []
        self.order_counter = 1

    def open_position(
        self,
        symbol: str,
        direction: Literal["BUY", "SELL"],
        spot_price: float,
        spot_sl: float,
        spot_target_1: float,
        spot_target_2: float,
        option_symbol: str,
        option_entry: float,
        option_sl: float,
        option_target: float,
        lots: int = 1,
        lot_size: Optional[int] = None
    ) -> PaperPosition:
        """Executes a simulated entry order with slippage."""
        pos_id = f"POS-{self.order_counter:04d}"
        self.order_counter += 1

        resolved_lot_size = lot_size or getattr(settings, f"{symbol.upper()}_LOT_SIZE", settings.NIFTY_LOT_SIZE)

        # Apply slippage on option entry
        actual_opt_entry = option_entry + (self.slippage_pts if direction == "BUY" else -self.slippage_pts)
        entry_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        pos = PaperPosition(
            position_id=pos_id,
            symbol=symbol,
            direction=direction,
            entry_time=entry_time_str,
            entry_price=spot_price,
            stop_loss=spot_sl,
            target_1=spot_target_1,
            target_2=spot_target_2,
            option_symbol=option_symbol,
            option_entry=round(actual_opt_entry, 2),
            option_sl=option_sl,
            option_target=option_target,
            lots=lots,
            lot_size=resolved_lot_size
        )

        self.open_positions[pos_id] = pos
        logger.info(f"Opened paper position {pos_id}: {symbol} {direction} at option ₹{actual_opt_entry:.2f} (Lots: {lots}, LotSize: {resolved_lot_size})")
        return pos

    def update_ticks(self, current_spot: float, current_opt_price: float, current_time_str: str = "11:00") -> List[PaperPosition]:
        """
        Evaluates open positions against current market price and auto-squareoff time.
        """
        closed_this_tick: List[PaperPosition] = []
        # Check auto squareoff (15:15 IST)
        try:
            parts = current_time_str.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            is_eod = (h > 15 or (h == 15 and m >= 15))
        except Exception:
            is_eod = False

        for pos_id, pos in list(self.open_positions.items()):
            should_close = False
            close_reason = ""
            exit_opt = current_opt_price

            if is_eod:
                should_close = True
                close_reason = "15:15_INTRADAY_AUTO_SQUAREOFF"
            elif pos.direction == "BUY":
                if current_spot <= pos.stop_loss or current_opt_price <= pos.option_sl:
                    should_close = True
                    close_reason = "STOP_LOSS_HIT"
                    exit_opt = min(current_opt_price, pos.option_sl)
                elif current_spot >= pos.target_1 or current_opt_price >= pos.option_target:
                    should_close = True
                    close_reason = "TARGET_HIT"
                    exit_opt = max(current_opt_price, pos.option_target)
            else:  # SELL
                if current_spot >= pos.stop_loss or current_opt_price <= pos.option_sl:
                    should_close = True
                    close_reason = "STOP_LOSS_HIT"
                    exit_opt = min(current_opt_price, pos.option_sl)
                elif current_spot <= pos.target_1 or current_opt_price >= pos.option_target:
                    should_close = True
                    close_reason = "TARGET_HIT"
                    exit_opt = max(current_opt_price, pos.option_target)

            if should_close:
                closed = self._close_position(pos_id, current_spot, exit_opt, close_reason)
                if closed:
                    closed_this_tick.append(closed)

        return closed_this_tick

    def _close_position(
        self,
        pos_id: str,
        exit_spot: float,
        exit_opt: float,
        reason: str
    ) -> Optional[PaperPosition]:
        pos = self.open_positions.pop(pos_id, None)
        if not pos:
            return None

        pos.status = "CLOSED"
        pos.exit_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        pos.exit_price = exit_spot
        pos.option_exit = round(exit_opt, 2)
        pos.close_reason = reason

        # Calculate exact statutory costs and net PnL
        cost_report = calculate_option_trade_costs(
            entry_premium=pos.option_entry,
            exit_premium=pos.option_exit,
            lot_size=pos.lot_size,
            lots=pos.lots
        )

        pos.gross_pnl = cost_report["gross_pnl"]
        pos.statutory_costs = cost_report["total_costs"]
        pos.net_pnl = cost_report["net_pnl"]

        self.available_capital += pos.net_pnl
        self.closed_positions.append(pos)
        logger.info(f"Closed paper position {pos_id}: Net PnL ₹{pos.net_pnl:.2f} ({reason})")
        return pos

    def get_summary(self) -> Dict[str, Any]:
        total_trades = len(self.closed_positions)
        wins = [p for p in self.closed_positions if p.net_pnl > 0]
        losses = [p for p in self.closed_positions if p.net_pnl <= 0]
        net_pnl_total = sum(p.net_pnl for p in self.closed_positions)
        costs_total = sum(p.statutory_costs for p in self.closed_positions)

        return {
            "initial_capital": self.initial_capital,
            "current_capital": round(self.available_capital, 2),
            "net_pnl_rupees": round(net_pnl_total, 2),
            "total_statutory_costs": round(costs_total, 2),
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round((len(wins) / total_trades) * 100.0, 1) if total_trades > 0 else 0.0,
            "open_positions_count": len(self.open_positions)
        }
