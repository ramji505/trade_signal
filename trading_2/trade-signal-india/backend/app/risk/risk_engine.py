from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any
from datetime import datetime, timedelta


@dataclass
class RiskParameters:
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_points: float
    reward_1_points: float
    reward_2_points: float
    risk_reward_ratio: float
    is_valid_risk: bool


@dataclass
class PositionSizingResult:
    allowed: bool
    lots: int
    quantity: int
    risk_amount_rupees: float
    actual_risk_rupees: float
    risk_per_lot_rupees: float
    reason: str


class RiskEngine:
    """
    ATR-based Risk, Trade Sizing, and Institutional Position Management:
    - Never uses arbitrary fixed stops.
    - Dynamically computes Stop Loss = Entry +/- (1.5 * ATR)
    - Target 1 (1:1.5 R:R) and Target 2 (1:2.0 R:R)
    - Anti-Spam Signal Cooldown Management (default: 15 minutes between identical setups)
    - True Fixed Fractional Position Sizing: Never blindly defaults to 1 lot if it violates risk budget.
    - Dynamic Trailing Stop-Loss: Trails SL to Break-Even upon achieving Target 1.
    """

    def __init__(self, atr_multiplier: float = 1.5, min_rr: float = 1.5, cooldown_minutes: int = 15):
        self.atr_multiplier = atr_multiplier
        self.min_rr = min_rr
        self.cooldown_minutes = cooldown_minutes
        self.last_signal_time: Optional[datetime] = None
        self.last_signal_direction: Optional[str] = None

    def calculate_levels(
        self,
        direction: Literal["BUY", "SELL"],
        current_price: float,
        atr_value: float,
        volatility_adjustment: float = 1.0
    ) -> RiskParameters:
        stop_dist = max(18.0, atr_value * self.atr_multiplier * volatility_adjustment)

        if direction == "BUY":
            stop_loss = round(current_price - stop_dist, 2)
            target_1 = round(current_price + (stop_dist * 1.5), 2)
            target_2 = round(current_price + (stop_dist * 2.0), 2)
            reward_1 = target_1 - current_price
        else:
            stop_loss = round(current_price + stop_dist, 2)
            target_1 = round(current_price - (stop_dist * 1.5), 2)
            target_2 = round(current_price - (stop_dist * 2.0), 2)
            reward_1 = current_price - target_1

        rr = reward_1 / stop_dist if stop_dist > 0 else 0.0

        return RiskParameters(
            entry_price=round(current_price, 2),
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_points=round(stop_dist, 2),
            reward_1_points=round(reward_1, 2),
            reward_2_points=round(stop_dist * 2.0, 2),
            risk_reward_ratio=round(rr, 2),
            is_valid_risk=(rr >= self.min_rr)
        )

    @staticmethod
    def calculate_position_size(
        account_equity: float,
        risk_pct_per_trade: float,  # e.g., 0.01 for 1%
        entry_price: float,
        stop_loss: float,
        lot_size: int = 65
    ) -> PositionSizingResult:
        """
        Calculates exact allowed lots based on capital and risk budget.
        Hard rejects trade if minimum 1 lot exceeds allowed risk budget.
        """
        allowed_risk_budget = account_equity * risk_pct_per_trade
        stop_dist = abs(entry_price - stop_loss)

        if stop_dist <= 0 or lot_size <= 0:
            return PositionSizingResult(
                allowed=False,
                lots=0,
                quantity=0,
                risk_amount_rupees=allowed_risk_budget,
                actual_risk_rupees=0.0,
                risk_per_lot_rupees=0.0,
                reason="Invalid stop distance or lot size"
            )

        risk_per_lot = stop_dist * lot_size

        if risk_per_lot > allowed_risk_budget:
            return PositionSizingResult(
                allowed=False,
                lots=0,
                quantity=0,
                risk_amount_rupees=round(allowed_risk_budget, 2),
                actual_risk_rupees=0.0,
                risk_per_lot_rupees=round(risk_per_lot, 2),
                reason=f"Risk for 1 lot (₹{risk_per_lot:.2f}) exceeds allowed risk budget (₹{allowed_risk_budget:.2f})"
            )

        lots = int(allowed_risk_budget // risk_per_lot)
        actual_risk = lots * risk_per_lot

        return PositionSizingResult(
            allowed=True,
            lots=lots,
            quantity=lots * lot_size,
            risk_amount_rupees=round(allowed_risk_budget, 2),
            actual_risk_rupees=round(actual_risk, 2),
            risk_per_lot_rupees=round(risk_per_lot, 2),
            reason="Position sized within risk budget"
        )

    @staticmethod
    def update_trailing_stop(
        direction: Literal["BUY", "SELL"],
        entry_price: float,
        current_price: float,
        current_sl: float,
        target_1: float
    ) -> float:
        """
        Trails stop-loss to Break-Even (entry price) once Target 1 is crossed.
        """
        if direction == "BUY":
            if current_price >= target_1 and current_sl < entry_price:
                return entry_price
        else:  # SELL
            if current_price <= target_1 and current_sl > entry_price:
                return entry_price
        return current_sl

    def is_in_cooldown(self, direction: str, current_time: datetime) -> bool:
        if self.last_signal_time is None or self.last_signal_direction != direction:
            return False
        elapsed = (current_time - self.last_signal_time).total_seconds() / 60.0
        return elapsed < self.cooldown_minutes

    def register_signal(self, direction: str, current_time: datetime):
        self.last_signal_time = current_time
        self.last_signal_direction = direction
