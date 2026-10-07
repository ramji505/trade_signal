"""
Option Chain Builder and Real-time Aggregator.
"""

from typing import List, Dict, Any, Optional
from .greeks import calculate_greeks
from .oi_walls import detect_oi_walls
from .pcr import calculate_pcr

def generate_synthetic_option_chain(
    spot_price: float,
    days_to_expiry: float = 2.0,
    strike_step: float = 50.0,
    num_strikes_each_side: int = 10
) -> Dict[str, Any]:
    """
    Generates realistic synthetic Option Chain snapshot for backtesting/mock feed
    with calibrated Greeks, IV smile, and realistic OI clustering around round numbers.
    """
    atm_strike = round(spot_price / strike_step) * strike_step
    strikes = [atm_strike + i * strike_step for i in range(-num_strikes_each_side, num_strikes_each_side + 1)]
    
    T = max(0.5, days_to_expiry) / 365.0
    r = 0.065
    
    chain_rows = []
    
    for K in strikes:
        moneyness = (spot_price - K) / spot_price
        # Volatility smile (higher IV for OTM puts/calls)
        base_iv = 0.13 + 0.5 * (moneyness ** 2)
        
        # CE Greeks
        ce_greeks = calculate_greeks(spot_price, K, T, r, base_iv, "CE")
        # PE Greeks
        pe_greeks = calculate_greeks(spot_price, K, T, r, base_iv, "PE")
        
        # Realistic OI simulation: higher near ATM and round numbers (e.g. 500/1000 intervals)
        dist_from_atm = abs(K - atm_strike) / strike_step
        round_bonus = 1.8 if K % 500 == 0 else 1.0
        
        ce_oi = int(max(50000, (500000 / (1.0 + 0.3 * dist_from_atm)) * round_bonus))
        pe_oi = int(max(50000, (480000 / (1.0 + 0.3 * dist_from_atm)) * round_bonus))
        
        chain_rows.append({
            "strike": K,
            "ce_price": ce_greeks["price"],
            "ce_delta": ce_greeks["delta"],
            "ce_theta": ce_greeks["theta_day"],
            "ce_iv": ce_greeks["iv"],
            "ce_oi": ce_oi,
            "ce_volume": int(ce_oi * 0.4),
            "pe_price": pe_greeks["price"],
            "pe_delta": pe_greeks["delta"],
            "pe_theta": pe_greeks["theta_day"],
            "pe_iv": pe_greeks["iv"],
            "pe_oi": pe_oi,
            "pe_volume": int(pe_oi * 0.38)
        })
        
    oi_walls = detect_oi_walls(chain_rows)
    pcr_data = calculate_pcr(chain_rows)
    
    return {
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "days_to_expiry": days_to_expiry,
        "chain": chain_rows,
        "oi_walls": oi_walls,
        "pcr": pcr_data
    }
