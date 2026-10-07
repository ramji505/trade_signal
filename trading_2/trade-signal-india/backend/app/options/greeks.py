"""
Black-Scholes Options Pricing and Greeks Engine.
Calculates European Call and Put theoretical prices, Delta, Gamma, Theta, Vega,
and Implied Volatility (IV) inversion using Newton-Raphson with bisection fallback.
"""

import math
from typing import Tuple, Dict, Any, Optional

# Normal distribution CDF approximation
def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

def calculate_d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float]:
    """Calculate d1 and d2 parameters in Black-Scholes formula."""
    if T <= 0.0 or sigma <= 0.0 or S <= 0.0 or K <= 0.0:
        return 0.0, 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2

def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> float:
    """
    Calculate theoretical option price under Black-Scholes model.
    S: Spot underlying price
    K: Strike price
    T: Time to expiry in years (e.g. 1 day / 365)
    r: Risk-free rate (e.g. 0.065 for 6.5% RBI repo-rate approx)
    sigma: Volatility (e.g. 0.15 for 15% IV)
    option_type: "CE" for Call, "PE" for Put
    """
    if T <= 1e-6:
        # At expiry
        if option_type.upper() == "CE":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)
    
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    
    if option_type.upper() == "CE":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    
    return max(0.05, price)

def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> Dict[str, float]:
    """
    Calculate Greeks: Delta, Gamma, Theta (per day decay), Vega (per 1% IV change).
    """
    if T <= 1e-6 or sigma <= 0.0 or S <= 0.0:
        is_call = option_type.upper() == "CE"
        delta = 1.0 if (is_call and S > K) else (-1.0 if (not is_call and S < K) else 0.0)
        return {
            "price": max(0.05, (S - K) if is_call else (K - S)),
            "delta": delta,
            "gamma": 0.0,
            "theta_day": 0.0,
            "vega": 0.0,
            "iv": sigma
        }
    
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    pdf_d1 = norm_pdf(d1)
    is_call = option_type.upper() == "CE"
    
    # Delta
    delta = norm_cdf(d1) if is_call else (norm_cdf(d1) - 1.0)
    
    # Gamma (identical for Call & Put)
    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    
    # Theta (per year -> convert to per calendar day)
    term1 = -(S * pdf_d1 * sigma) / (2.0 * math.sqrt(T))
    if is_call:
        term2 = -r * K * math.exp(-r * T) * norm_cdf(d2)
    else:
        term2 = r * K * math.exp(-r * T) * norm_cdf(-d2)
    theta_year = term1 + term2
    theta_day = theta_year / 365.0
    
    # Vega (per 1% = 0.01 change in volatility)
    vega = (S * math.sqrt(T) * pdf_d1) * 0.01
    
    price = black_scholes_price(S, K, T, r, sigma, option_type)
    
    return {
        "price": round(price, 2),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta_day": round(theta_day, 2),
        "vega": round(vega, 4),
        "iv": round(sigma, 4)
    }

def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float = 0.065,
    option_type: str = "CE",
    max_iter: int = 100,
    tolerance: float = 1e-4
) -> float:
    """
    Invert Black-Scholes formula using Newton-Raphson to find Implied Volatility (IV).
    Falls back to bisection if Newton step diverges.
    """
    if market_price <= 0.05 or T <= 1e-6:
        return 0.15 # fallback standard 15% IV
    
    # Initial IV guess
    sigma = 0.20
    low_sigma = 0.001
    high_sigma = 3.0
    
    for _ in range(max_iter):
        price = black_scholes_price(S, K, T, r, sigma, option_type)
        diff = price - market_price
        if abs(diff) < tolerance:
            return round(sigma, 4)
        
        # Calculate vega derivative
        d1, _ = calculate_d1_d2(S, K, T, r, sigma)
        vega = S * math.sqrt(T) * norm_pdf(d1)
        
        if vega > 1e-5:
            sigma_new = sigma - diff / vega
            if low_sigma < sigma_new < high_sigma:
                sigma = sigma_new
                continue
        
        # Bisection fallback
        if diff > 0:
            high_sigma = sigma
        else:
            low_sigma = sigma
        sigma = (low_sigma + high_sigma) / 2.0
    
    return round(sigma, 4)


def calculate_iv_skew(chain: list[dict], spot_price: float) -> Dict[str, Any]:
    """
    Calculate Implied Volatility Skew: ΔIV_skew = IV_OTM_Put - IV_OTM_Call.
    A positive skew spike during consolidation indicates institutional downside hedging.
    """
    if not chain or spot_price <= 0:
        return {"iv_skew": 0.0, "otm_call_iv": 0.0, "otm_put_iv": 0.0, "skew_sentiment": "NEUTRAL"}

    # Find OTM Call (strike ~ 1% above spot) and OTM Put (strike ~ 1% below spot)
    otm_call_strike = spot_price * 1.01
    otm_put_strike = spot_price * 0.99

    otm_call = min(chain, key=lambda r: abs(float(r.get("strike", 0)) - otm_call_strike))
    otm_put = min(chain, key=lambda r: abs(float(r.get("strike", 0)) - otm_put_strike))

    call_iv = float(otm_call.get("ce_iv", 0.0))
    put_iv = float(otm_put.get("pe_iv", 0.0))

    # Normalize to percentage if in decimal form
    call_iv_pct = call_iv * 100.0 if 0 < call_iv <= 3.0 else call_iv
    put_iv_pct = put_iv * 100.0 if 0 < put_iv <= 3.0 else put_iv

    skew = put_iv_pct - call_iv_pct
    sentiment = "BEARISH_HEDGING" if skew > 2.5 else ("BULLISH_DEMAND" if skew < -2.5 else "NEUTRAL")

    return {
        "iv_skew": round(skew, 2),
        "otm_call_iv": round(call_iv_pct, 2),
        "otm_put_iv": round(put_iv_pct, 2),
        "skew_sentiment": sentiment
    }


def calculate_oi_velocity(current_oi: int, prev_oi: int, dt_seconds: float, volume: int) -> float:
    """
    Calculate Time-Weighted OI Velocity: (ΔOI / Δt) * Volume.
    Measures acceleration of institutional positioning in real-time.
    """
    if dt_seconds <= 0:
        return 0.0
    delta_oi = current_oi - prev_oi
    return round((delta_oi / dt_seconds) * (volume / 1000.0), 2)

