from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.risk.event_filter import EventRiskFilter
from app.strategy.scoring import SignalScorer
from app.costs.statutory_charges import calculate_option_trade_costs


def test_unified_score_uses_options_layer():
    b = SignalScorer.calculate_score(
        direction="BUY", mtf_aligned=True, mtf_concordance=100,
        structure_type="BOS_BULLISH", price_vs_vwap=True, ema_aligned=True,
        volume_expanding=True, rsi_value=60, candlestick_pattern="HAMMER",
        headroom_available=True, volatility_tradable=True, event_penalty=0,
        pcr=1.25, call_wall=25400, put_wall=25100, current_price=25200,
        atm_iv=14.0, spread_pct=0.20, liquidity_status="EXCELLENT"
    )
    assert b.tier3_options_score > 0
    assert b.total_score <= 100


def test_event_filter_blocks_scheduled_event():
    event_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    f = EventRiskFilter(events_json=f'[{"{"}"timestamp":"{event_time.isoformat()}","name":"Test RBI","risk_level":"EXTREME"{"}"}]')
    status = f.evaluate_risk(datetime.now(timezone.utc))
    assert status.allow_trading is False
    assert status.risk_level == "EXTREME"


def test_current_nifty_economics_are_configurable_and_used():
    res = calculate_option_trade_costs(100, 130)
    assert res["lot_size"] == settings.NIFTY_LOT_SIZE == 65
    assert res["stt_rate"] == settings.OPTION_SELL_STT_RATE == 0.0015
    assert res["total_costs"] > 0


def test_groww_option_chain_normalization_reads_nested_greeks():
    from app.options.option_adapter import normalize_groww_option_chain
    snap = normalize_groww_option_chain({
        "underlying_ltp": 25200.0,
        "strikes": {
            "25200": {
                "CE": {
                    "greeks": {"delta": 0.51, "theta": -9.2, "iv": 14.5},
                    "ltp": 120.0, "open_interest": 100000, "volume": 5000
                },
                "PE": {
                    "greeks": {"delta": -0.49, "theta": -8.8, "iv": 15.0},
                    "ltp": 115.0, "open_interest": 110000, "volume": 5500
                }
            }
        }
    })
    assert snap["chain"][0]["ce_delta"] == 0.51
    assert snap["atm_iv"] == 14.5
    assert snap["pcr"]["oi_pcr"] > 1.0
