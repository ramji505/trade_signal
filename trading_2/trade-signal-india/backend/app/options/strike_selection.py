"""
Algorithmic Strike Selection & Premium Translation Engine.
Selects optimal NIFTY option strike (ATM or 0.50-0.60 Delta slight-ITM)
and calculates theoretical option entry, SL, and Target based on Spot Delta and Greeks.
"""

from typing import Dict, Any, List, Optional
from .greeks import calculate_greeks, black_scholes_price

def select_optimal_strike(
    spot_price: float,
    signal_type: str,
    days_to_expiry: float = 2.0,
    strike_step: float = 50.0,
    target_delta: float = 0.55
) -> Dict[str, Any]:
    """
    Selects the optimal strike for a NIFTY trade signal.
    - For BUY signal: Calls (CE) - select ATM or 1 strike ITM (0.50 to 0.60 Delta)
    - For SELL signal: Puts (PE) - select ATM or 1 strike ITM (-0.50 to -0.60 Delta)
    """
    atm_strike = round(spot_price / strike_step) * strike_step
    T = max(0.5, days_to_expiry) / 365.0
    r = 0.065
    sigma = 0.14 # 14% typical NIFTY IV

    if signal_type.upper() in ["BUY", "LONG", "BULLISH"]:
        option_type = "CE"
        # Check ATM vs 1 strike ITM
        strikes_to_eval = [atm_strike, atm_strike - strike_step]
    else:
        option_type = "PE"
        # Check ATM vs 1 strike ITM
        strikes_to_eval = [atm_strike, atm_strike + strike_step]

    best_strike = strikes_to_eval[0]
    best_greeks = None
    min_delta_diff = float("inf")

    for strike in strikes_to_eval:
        greeks = calculate_greeks(spot_price, strike, T, r, sigma, option_type)
        delta_mag = abs(greeks["delta"])
        diff = abs(delta_mag - target_delta)
        if diff < min_delta_diff:
            min_delta_diff = diff
            best_strike = strike
            best_greeks = greeks

    return {
        "strike": best_strike,
        "option_type": option_type,
        "symbol": f"NIFTY{int(best_strike)}{option_type}",
        "entry_premium": best_greeks["price"],
        "delta": best_greeks["delta"],
        "gamma": best_greeks["gamma"],
        "theta_day": best_greeks["theta_day"],
        "vega": best_greeks["vega"],
        "iv": best_greeks["iv"]
    }

def translate_spot_to_option_levels(
    spot_entry: float,
    spot_sl: float,
    spot_target: float,
    option_strike_info: Dict[str, Any]
) -> Dict[str, float]:
    """
    Translates underlying Spot Stop Loss and Target into exact Option Premium SL and Target
    using instantaneous Delta with Gamma buffer.
    """
    entry_prem = option_strike_info["entry_premium"]
    delta = abs(option_strike_info["delta"])
    is_call = option_strike_info["option_type"] == "CE"

    if is_call:
        spot_risk = spot_entry - spot_sl
        spot_reward = spot_target - spot_entry
    else:
        spot_risk = spot_sl - spot_entry
        spot_reward = spot_entry - spot_target

    # Option risk = spot_risk * delta (minimum 10% floor)
    option_risk = max(5.0, spot_risk * delta)
    option_reward = max(10.0, spot_reward * delta)

    option_sl = max(1.0, round(entry_prem - option_risk, 2))
    option_target = round(entry_prem + option_reward, 2)

    return {
        "option_entry": round(entry_prem, 2),
        "option_sl": option_sl,
        "option_target": option_target,
        "option_risk_points": round(entry_prem - option_sl, 2),
        "option_reward_points": round(option_target - entry_prem, 2)
    }
