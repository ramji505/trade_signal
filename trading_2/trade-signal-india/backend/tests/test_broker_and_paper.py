import asyncio
import pytest
from app.broker.groww_auth import GrowwAuthenticator
from app.paper.paper_trader import PaperTradingEngine


def test_groww_totp_and_authentication(monkeypatch):
    async def _runner():
        secret = "JBSWY3DPEHPK3PXP"
        totp = GrowwAuthenticator.generate_totp(secret)
        assert len(totp) == 6 and totp.isdigit()

        class FakeResponse:
            def raise_for_status(self):
                return None
            def json(self):
                return {"status": "SUCCESS", "token": "TEST_ACCESS", "expiry": "2099-01-01T00:00:00+00:00", "payload": {}}

        auth = GrowwAuthenticator(api_key="TEST_KEY", api_secret="TEST_SEC", totp_secret=secret)
        async def fake_post(payload):
            assert payload["key_type"] == "totp"
            return FakeResponse()
        async def fake_get(path, params):
            if path == "/v1/user/detail":
                return {"broker": "Groww", "available_margin": 100000}
            return {}
        monkeypatch.setattr(auth, "_post_token", fake_post)
        monkeypatch.setattr(auth, "_get", fake_get)
        assert await auth.authenticate() is True
        assert auth.is_authenticated is True
        profile = await auth.get_profile()
        assert profile["broker"] == "Groww"
        assert profile["available_margin"] > 0

    asyncio.run(_runner())


def test_paper_trading_lifecycle():
    engine = PaperTradingEngine(initial_capital=100000.0, slippage_pts=0.5)

    # Open Buy Position
    pos = engine.open_position(
        symbol="NIFTY",
        direction="BUY",
        spot_price=25000.0,
        spot_sl=24970.0,
        spot_target_1=25050.0,
        spot_target_2=25070.0,
        option_symbol="NIFTY25000CE",
        option_entry=100.0,
        option_sl=80.0,
        option_target=135.0,
        lots=1
    )
    assert pos.status == "OPEN"
    assert pos.option_entry == 100.5  # Includes 0.5 slippage
    assert len(engine.open_positions) == 1

    # Price moves to target
    closed = engine.update_ticks(current_spot=25055.0, current_opt_price=140.0, current_time_str="10:30")
    assert len(closed) == 1
    assert closed[0].status == "CLOSED"
    assert closed[0].close_reason == "TARGET_HIT"
    assert closed[0].net_pnl > 0
    assert closed[0].statutory_costs > 0

    summary = engine.get_summary()
    assert summary["total_trades"] == 1
    assert summary["winning_trades"] == 1
    assert summary["current_capital"] > summary["initial_capital"]


def test_paper_trading_eod_squareoff():
    engine = PaperTradingEngine(initial_capital=100000.0)
    engine.open_position(
        symbol="NIFTY",
        direction="BUY",
        spot_price=25000.0,
        spot_sl=24950.0,
        spot_target_1=25100.0,
        spot_target_2=25150.0,
        option_symbol="NIFTY25000CE",
        option_entry=100.0,
        option_sl=75.0,
        option_target=140.0,
        lots=1
    )
    # At 15:15 IST intraday auto square-off must trigger
    closed = engine.update_ticks(current_spot=25010.0, current_opt_price=105.0, current_time_str="15:15")
    assert len(closed) == 1
    assert closed[0].close_reason == "15:15_INTRADAY_AUTO_SQUAREOFF"
