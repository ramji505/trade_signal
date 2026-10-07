"""
Put-Call Ratio (PCR) Engine.
Calculates Volume PCR, Open Interest PCR, and assesses sentiment regime.
"""

from typing import List, Dict, Any

def calculate_pcr(option_chain_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute PCR for Open Interest and Volume.
    PCR > 1.2: Bullish sentiment (Put writing exceeds Call writing)
    PCR < 0.8: Bearish sentiment (Call writing exceeds Put writing)
    0.8 <= PCR <= 1.2: Neutral sentiment
    PCR > 1.6: Extreme Overbought / Reversal Risk
    PCR < 0.5: Extreme Oversold / Bounce Risk
    """
    total_ce_oi = sum(item.get("ce_oi", 0) for item in option_chain_data)
    total_pe_oi = sum(item.get("pe_oi", 0) for item in option_chain_data)
    total_ce_vol = sum(item.get("ce_volume", 0) for item in option_chain_data)
    total_pe_vol = sum(item.get("pe_volume", 0) for item in option_chain_data)

    oi_pcr = round(total_pe_oi / max(1, total_ce_oi), 3)
    volume_pcr = round(total_pe_vol / max(1, total_ce_vol), 3)

    if oi_pcr > 1.6:
        sentiment = "EXTREME_BULLISH_OVERBOUGHT"
    elif oi_pcr > 1.15:
        sentiment = "BULLISH"
    elif oi_pcr < 0.55:
        sentiment = "EXTREME_BEARISH_OVERSOLD"
    elif oi_pcr < 0.85:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    return {
        "oi_pcr": oi_pcr,
        "volume_pcr": volume_pcr,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "sentiment": sentiment
    }
