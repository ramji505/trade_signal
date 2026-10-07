from typing import Any, Dict


def normalize_groww_option_chain(payload: Dict[str, Any], spot_price: float | None = None) -> Dict[str, Any]:
    """Normalize Groww's documented strikes{strike:{CE,PE}} payload into the internal format."""
    payload = payload or {}
    raw = payload.get("strikes") or payload.get("option_chain") or payload.get("chain") or {}
    if isinstance(raw, dict):
        items = [(strike, value) for strike, value in raw.items()]
    else:
        items = [(item.get("strike"), item) for item in raw if isinstance(item, dict)]

    resolved_spot = float(spot_price or payload.get("underlying_ltp") or payload.get("spot_price") or 0)
    rows = []
    for strike_key, item in items:
        if not isinstance(item, dict):
            continue
        try:
            strike = float(item.get("strike_price") or item.get("strike") or strike_key)
        except (TypeError, ValueError):
            continue
        ce = item.get("CE") or item.get("ce") or item.get("call") or {}
        pe = item.get("PE") or item.get("pe") or item.get("put") or {}
        if not isinstance(ce, dict):
            ce = {}
        if not isinstance(pe, dict):
            pe = {}
        ce_g = ce.get("greeks") or {}
        pe_g = pe.get("greeks") or {}
        row = {
            "strike": strike,
            "ce_price": float(ce.get("ltp") or ce.get("last_price") or ce.get("price") or 0),
            "ce_delta": float(ce_g.get("delta") if ce_g.get("delta") is not None else ce.get("delta") or 0),
            "ce_theta": float(ce_g.get("theta") if ce_g.get("theta") is not None else ce.get("theta_day") or 0),
            "ce_iv": float(ce_g.get("iv") if ce_g.get("iv") is not None else ce.get("iv") or 0),
            "ce_oi": int(ce.get("open_interest") or ce.get("oi") or 0),
            "ce_volume": int(ce.get("volume") or 0),
            "pe_price": float(pe.get("ltp") or pe.get("last_price") or pe.get("price") or 0),
            "pe_delta": float(pe_g.get("delta") if pe_g.get("delta") is not None else pe.get("delta") or 0),
            "pe_theta": float(pe_g.get("theta") if pe_g.get("theta") is not None else pe.get("theta_day") or 0),
            "pe_iv": float(pe_g.get("iv") if pe_g.get("iv") is not None else pe.get("iv") or 0),
            "pe_oi": int(pe.get("open_interest") or pe.get("oi") or 0),
            "pe_volume": int(pe.get("volume") or 0),
        }
        rows.append(row)

    if not rows:
        return {"spot_price": resolved_spot, "chain": [], "oi_walls": {}, "pcr": {}}

    from app.options.oi_walls import detect_oi_walls
    from app.options.pcr import calculate_pcr
    atm_strike = min(rows, key=lambda r: abs(r["strike"] - resolved_spot))["strike"] if resolved_spot else rows[len(rows) // 2]["strike"]
    atm = next(r for r in rows if r["strike"] == atm_strike)
    atm_iv = atm.get("ce_iv") or atm.get("pe_iv") or 0
    # Groww's documented option-chain IV is already a percentage (e.g. 25.34),
    # whereas the synthetic provider stores IV as a decimal (e.g. 0.13).
    atm_iv_pct = atm_iv * 100.0 if 0 < atm_iv <= 3 else atm_iv

    # Option-chain responses do not expose a single chain-wide bid/ask; retain a conservative
    # default unless a provider adds these fields later.
    return {
        "spot_price": resolved_spot,
        "atm_strike": atm_strike,
        "atm_iv": atm_iv_pct,
        "spread_pct": float(payload.get("spread_pct", 0.20)),
        "liquidity_status": payload.get("liquidity_status", "GOOD"),
        "chain": rows,
        "oi_walls": detect_oi_walls(rows),
        "pcr": calculate_pcr(rows),
    }
