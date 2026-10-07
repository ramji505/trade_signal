"""
Open Interest (OI) Walls & Buildup Engine.
Detects Call Resistance Walls, Put Support Walls, Max Pain Strike,
and classifies OI price-volume-OI changes (Long Buildup, Short Covering, Short Buildup, Long Unwinding).
"""

from typing import List, Dict, Any, Optional

def calculate_max_pain(strikes: List[float], ce_oi: List[int], pe_oi: List[int]) -> float:
    """
    Compute Option Max Pain strike price.
    Max Pain is the strike at which option buyers lose the most money at expiry.
    """
    if not strikes or len(strikes) != len(ce_oi) or len(strikes) != len(pe_oi):
        return strikes[0] if strikes else 25000.0

    min_loss = float("inf")
    max_pain_strike = strikes[0]

    for test_strike in strikes:
        total_loss = 0.0
        for strike, c_oi, p_oi in zip(strikes, ce_oi, pe_oi):
            # If spot expires at test_strike:
            # Call buyer payoff = max(0, test_strike - strike) * c_oi
            # Put buyer payoff = max(0, strike - test_strike) * p_oi
            call_payoff = max(0.0, test_strike - strike) * c_oi
            put_payoff = max(0.0, strike - test_strike) * p_oi
            total_loss += (call_payoff + put_payoff)
        
        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = test_strike

    return max_pain_strike

def detect_oi_walls(option_chain_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Identifies Call Resistance Wall (highest CE OI) and Put Support Wall (highest PE OI).
    """
    if not option_chain_data:
        return {
            "call_wall_strike": 0.0,
            "call_wall_oi": 0,
            "put_wall_strike": 0.0,
            "put_wall_oi": 0,
            "max_pain": 0.0
        }

    strikes = [item["strike"] for item in option_chain_data]
    ce_ois = [item.get("ce_oi", 0) for item in option_chain_data]
    pe_ois = [item.get("pe_oi", 0) for item in option_chain_data]

    max_ce_idx = ce_ois.index(max(ce_ois)) if ce_ois else 0
    max_pe_idx = pe_ois.index(max(pe_ois)) if pe_ois else 0

    max_pain = calculate_max_pain(strikes, ce_ois, pe_ois)

    return {
        "call_wall_strike": strikes[max_ce_idx],
        "call_wall_oi": ce_ois[max_ce_idx],
        "put_wall_strike": strikes[max_pe_idx],
        "put_wall_oi": pe_ois[max_pe_idx],
        "max_pain": max_pain
    }

def classify_buildup(price_change: float, oi_change: float) -> str:
    """
    Classify 4-quadrant institutional derivative microstructure buildup:
    1. Price UP + OI UP   -> LONG_BUILDUP (Strong Bullish)
    2. Price UP + OI DOWN -> SHORT_COVERING (Weak/Momentum Bullish)
    3. Price DOWN + OI UP -> SHORT_BUILDUP (Strong Bearish)
    4. Price DOWN + OI DOWN -> LONG_UNWINDING (Weak/Panic Bearish)
    """
    if price_change > 0:
        if oi_change > 0:
            return "LONG_BUILDUP"
        else:
            return "SHORT_COVERING"
    else:
        if oi_change > 0:
            return "SHORT_BUILDUP"
        else:
            return "LONG_UNWINDING"
