from __future__ import annotations
"""
Institutional Risk Controls, Operational Vetoes & Circuit Breakers.
Enforces:
1. Max Daily Drawdown / Loss Limit kill-switch.
2. Max Consecutive Loss lockouts.
3. Max Daily Signal Cap (anti-overtrading).
4. Stale Tick Veto & Bid-Ask Spread Veto.
5. Time-in-Force (TIF) & Intraday 15:15 IST Square-off Audit.
6. Anti-Whipsaw signal frequency rate-limiting & invalidation checks.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time


class CircuitBreakerEngine:
    def __init__(
        self,
        max_daily_loss: float = 5000.0,
        max_consecutive_losses: int = 3,
        cooldown_bars: int = 5,
        cutoff_time_str: str = "15:15",
        max_daily_signals: int = 6,
        max_stale_seconds: float = 5.0,
        max_spread_pct: float = 0.15
    ):
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_bars = cooldown_bars
        self.cutoff_hour = int(cutoff_time_str.split(":")[0])
        self.cutoff_minute = int(cutoff_time_str.split(":")[1])
        self.max_daily_signals = max_daily_signals
        self.max_stale_seconds = max_stale_seconds
        self.max_spread_pct = max_spread_pct
        
        self.consecutive_losses = 0
        self.accumulated_daily_pnl = 0.0
        self.daily_signal_count = 0
        self.is_circuit_tripped = False
        self.trip_reason = ""
        self.last_signal_bar_index = -100

    def reset_day(self):
        """Reset daily tracking at 09:15 open."""
        self.consecutive_losses = 0
        self.accumulated_daily_pnl = 0.0
        self.daily_signal_count = 0
        self.is_circuit_tripped = False
        self.trip_reason = ""
        self.last_signal_bar_index = -100

    def record_trade_result(self, net_pnl: float):
        """Update consecutive loss counter and cumulative daily PnL."""
        self.accumulated_daily_pnl += net_pnl
        if net_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # Check circuit trip conditions
        if self.accumulated_daily_pnl <= -self.max_daily_loss:
            self.is_circuit_tripped = True
            self.trip_reason = f"MAX_DAILY_LOSS_EXCEEDED (Loss: ₹{abs(self.accumulated_daily_pnl):.2f} >= ₹{self.max_daily_loss})"
        elif self.consecutive_losses >= self.max_consecutive_losses:
            self.is_circuit_tripped = True
            self.trip_reason = f"MAX_CONSECUTIVE_LOSSES ({self.consecutive_losses} losses in a row)"

    def check_operational_vetoes(
        self,
        tick_age_seconds: Optional[float] = None,
        bid_ask_spread: Optional[float] = None,
        spot_price: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Hard operational safety vetoes."""
        if tick_age_seconds is not None and tick_age_seconds > self.max_stale_seconds:
            return False, f"STALE_TICK_VETO: Data feed age ({tick_age_seconds:.1f}s) exceeds max limit ({self.max_stale_seconds}s)"

        if bid_ask_spread is not None and spot_price is not None and spot_price > 0:
            spread_pct = (bid_ask_spread / spot_price) * 100.0
            if spread_pct > self.max_spread_pct:
                return False, f"SPREAD_VETO: Bid-Ask spread ({spread_pct:.3f}%) exceeds max allowable ({self.max_spread_pct}%)"

        return True, "OK"

    def can_generate_signal(
        self,
        current_time_str: str,
        current_bar_index: int,
        tick_age_seconds: Optional[float] = None,
        bid_ask_spread: Optional[float] = None,
        spot_price: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Validate whether signal generation is permissible across all risk and operational layers.
        """
        if self.is_circuit_tripped:
            return False, f"CIRCUIT_BREAKER_ACTIVE: {self.trip_reason}"

        # Check daily signal quota
        if self.daily_signal_count >= self.max_daily_signals:
            return False, f"DAILY_SIGNAL_CAP_EXCEEDED: Maximum {self.max_daily_signals} signals generated for today"

        # Check cooldown between signals
        if (current_bar_index - self.last_signal_bar_index) < self.cooldown_bars:
            return False, f"COOLDOWN_ACTIVE: {self.cooldown_bars - (current_bar_index - self.last_signal_bar_index)} bars remaining"

        # Check operational vetoes
        veto_ok, veto_reason = self.check_operational_vetoes(
            tick_age_seconds=tick_age_seconds,
            bid_ask_spread=bid_ask_spread,
            spot_price=spot_price
        )
        if not veto_ok:
            return False, veto_reason

        # Check intraday cutoff (15:15 IST)
        try:
            parts = current_time_str.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            if h > self.cutoff_hour or (h == self.cutoff_hour and m >= self.cutoff_minute):
                return False, "TIME_IN_FORCE_EXPIRED: Past 15:15 IST intraday cutoff"
            if h < 9 or (h == 9 and m < 20):
                return False, "OPENING_VOLATILITY_FILTER: First 5 minutes opening range"
        except Exception:
            pass

        return True, "OK"

    def mark_signal_issued(self, bar_index: int):
        self.last_signal_bar_index = bar_index
        self.daily_signal_count += 1
