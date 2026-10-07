from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, List
from datetime import datetime, timezone
import pandas as pd

from app.indicators.technical import TechnicalIndicators
from app.indicators.volume_analysis import VolumeAnalysis
from app.strategy.market_regime import MarketRegimeEngine
from app.strategy.market_structure import MarketStructure
from app.strategy.price_action import PriceActionEngine
from app.strategy.key_levels import KeyLevelsEngine
from app.strategy.candlestick import CandlestickEngine
from app.strategy.scoring import SignalScorer, ScoringBreakdown
from app.strategy.heavyweight_concordance import HeavyweightConcordanceEngine
from app.options.strike_selection import select_optimal_strike, translate_spot_to_option_levels
from app.risk.volatility import VolatilityEngine
from app.risk.event_filter import EventRiskFilter
from app.risk.risk_engine import RiskEngine
from app.risk.portfolio_risk import PortfolioRiskManager
from app.ml.anomaly_auditor import AnomalyAuditor
from app.ml.probability_calibrator import ProbabilityCalibrator
from app.database.ledger import audit_ledger


@dataclass
class MasterSignalResult:
    signal_id: str
    symbol: str
    timestamp: datetime
    direction: Literal["BUY", "SELL", "WAIT"]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    score: int
    quality: Literal["NO_TRADE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"]
    market_regime: str
    timeframe_states: Dict[str, str]
    reasons: list[str]
    scoring_breakdown: ScoringBreakdown
    # Calibrated Probability & Meta-Label fields
    calibrated_win_prob: float = 0.50
    expected_value_rupees: float = 0.0
    meta_label_verdict: str = "ACCEPT"
    # Option Specific Layer
    option_strike: Optional[float] = None
    option_type: Optional[str] = None
    option_symbol: Optional[str] = None
    option_entry: Optional[float] = None
    option_sl: Optional[float] = None
    option_target: Optional[float] = None
    delta: Optional[float] = None
    theta: Optional[float] = None
    iv: Optional[float] = None
    status: str = "ACTIVE"


class SignalEngine:
    """
    Master Quantitative Decision & Options Microstructure Engine for NIFTY 50 Intraday.
    Enforces Production Guardrails:
      1. Data Quality & Stale Tick Veto
      2. Multi-Timeframe Concordance (15m, 10m, 5m, 3m, 1m)
      3. Heavyweight Concordance (HDFCBANK, RELIANCE, ICICIBANK, INFY, BANKNIFTY)
      4. Point-in-time Market Structure & Prior Session Key Levels
      5. Intraday VWAP & Cumulative Volume Delta (CVD) Order Flow
      6. AI Anomaly & Low-Volume Trap Audit
      7. Empirical Bayesian Probability Calibration & Meta-Labeling
      8. Options Microstructure (IV, Delta, Theta, Strike Selection)
      9. 4-Tier Kill Switch & Risk Budget Verification
      10. Research Audit Ledger logging
    """

    def __init__(self, score_threshold: int = 80):
        self.score_threshold = score_threshold
        self.risk_engine = RiskEngine()
        self.event_filter = EventRiskFilter()
        self.portfolio_risk = PortfolioRiskManager()

    def process(
        self,
        symbol: str,
        tf_candles: Dict[str, pd.DataFrame],
        is_market_open: bool = True,
        is_data_healthy: bool = True,
        option_snapshot: Optional[Dict[str, Any]] = None,
        component_trends: Optional[Dict[str, str]] = None,
        current_daily_loss: float = 0.0,
        consecutive_losses: int = 0
    ) -> MasterSignalResult:
        now = datetime.now(timezone.utc)
        sig_id = f"{symbol}-{now.strftime('%Y%m%d-%H%M%S')}"

        reasons = []

        # 1. Safety & Kill Switch Checks
        if not is_market_open:
            reasons.append("Market is currently CLOSED")
            return self._build_wait(sig_id, symbol, now, "MARKET_CLOSED", reasons, decision_type="MARKET_CLOSED")

        if not is_data_healthy:
            reasons.append("Data feed quality degraded / Stale ticks detected")
            return self._build_wait(sig_id, symbol, now, "DATA_QUALITY_FAILURE", reasons, decision_type="DATA_QUALITY_FAILURE")

        kill_status = self.portfolio_risk.evaluate_kill_switch(
            current_daily_loss_rupees=current_daily_loss,
            open_unrealized_loss_rupees=0.0,
            consecutive_losses=consecutive_losses,
            data_feed_healthy=is_data_healthy
        )
        if not kill_status.allow_new_entries:
            reasons.append(f"KILL_SWITCH_VETO [{kill_status.level}]: {kill_status.reason}")
            return self._build_wait(sig_id, symbol, now, "KILL_SWITCH_ACTIVE", reasons, decision_type=f"VETOED_{kill_status.level}")

        # 2. Enrich primary 5m candles with indicators
        df_5m = tf_candles.get("5m")
        if df_5m is None or len(df_5m) < 20:
            reasons.append("Insufficient 5-minute candle history (< 20 candles)")
            return self._build_wait(sig_id, symbol, now, "INSUFFICIENT_DATA", reasons, decision_type="INSUFFICIENT_DATA")

        df_5m = TechnicalIndicators.compute_all(df_5m)
        df_5m = VolumeAnalysis.analyze(df_5m)

        # Enrich other timeframes for MTF engine
        enriched_tf = {}
        for tf, df in tf_candles.items():
            if len(df) >= 3:
                enriched_tf[tf] = TechnicalIndicators.compute_all(df)

        # 3. Multi-Timeframe Regime
        mtf_state = MarketRegimeEngine.analyze_mtf(enriched_tf)
        tf_states_str = {k: str(v) for k, v in mtf_state.tf_states.items()}

        current_price = float(df_5m['close'].iloc[-1])
        vwap_val = float(df_5m['vwap'].iloc[-1])
        ema_9 = float(df_5m['ema_9'].iloc[-1])
        ema_21 = float(df_5m['ema_21'].iloc[-1])
        ema_50 = float(df_5m['ema_50'].iloc[-1])
        rsi_val = float(df_5m['rsi_14'].iloc[-1])
        atr_val = float(df_5m['atr_14'].iloc[-1])
        vol_expanding = bool(df_5m['volume_expansion'].iloc[-1])
        rvol_val = float(df_5m.get('rvol', pd.Series([1.0])).iloc[-1])

        # 4. Market Structure & Point-in-Time Key Levels
        structure = MarketStructure.analyze_structure(df_5m)
        key_levels = KeyLevelsEngine.calculate(current_price, df_5m)
        price_action = PriceActionEngine.evaluate(df_5m, key_levels.nearest_resistance, key_levels.nearest_support)
        candle_pattern = CandlestickEngine.detect_pattern(df_5m)

        # 5. Volatility, Options Microstructure & Event Risk
        vol_state = VolatilityEngine.evaluate(current_price, atr_val)
        event_status = self.event_filter.evaluate_risk(now)
        if not event_status.allow_trading:
            reasons.append(f"EVENT_RISK_VETO: {event_status.event_name}")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="VETOED_EVENT")

        # Microstructure & Options Chain validation
        from app.core.config import settings
        if option_snapshot is None:
            if settings.ENVIRONMENT == "LIVE_DATA" or getattr(self, "require_live_data", False):
                reasons.append("HARD_VETO: Live option chain unavailable in LIVE_DATA mode (Synthetic fallback rejected)")
                return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="VETOED_DATA")
            from app.options.option_chain import generate_synthetic_option_chain
            option_snapshot = generate_synthetic_option_chain(current_price)

        pcr_data = option_snapshot.get("pcr", {}) if isinstance(option_snapshot, dict) else {}
        oi_walls = option_snapshot.get("oi_walls", {}) if isinstance(option_snapshot, dict) else {}
        chain = option_snapshot.get("chain", []) if isinstance(option_snapshot, dict) else []
        atm_iv = None
        if chain:
            atm_strike = option_snapshot.get("atm_strike", current_price)
            atm = min(chain, key=lambda r: abs(float(r.get("strike", 0)) - float(atm_strike)))
            atm_iv = float(atm.get("ce_iv") or atm.get("pe_iv") or 0) * 100.0
        spread_pct = float(option_snapshot.get("spread_pct", 0.20)) if isinstance(option_snapshot, dict) else 0.20
        liquidity_status = option_snapshot.get("liquidity_status", "GOOD") if isinstance(option_snapshot, dict) else "GOOD"
        pcr_val = float(pcr_data.get("oi_pcr", 1.0)) if pcr_data.get("oi_pcr") is not None else 1.0

        # 6. Direction Hypothesis & Order Flow CVD check
        direction_candidate: Optional[Literal["BUY", "SELL"]] = None
        cvd_aligned_buy = bool(df_5m.get('cvd_aligned_buy', pd.Series([True])).iloc[-1])
        cvd_aligned_sell = bool(df_5m.get('cvd_aligned_sell', pd.Series([True])).iloc[-1])

        if mtf_state.is_aligned_for_buy and current_price > vwap_val:
            direction_candidate = "BUY"
        elif mtf_state.is_aligned_for_sell and current_price < vwap_val:
            direction_candidate = "SELL"

        if direction_candidate is None:
            reasons.append(f"MTF or VWAP divergence (Regime: {mtf_state.overall_regime}, Price vs VWAP: {'Above' if current_price > vwap_val else 'Below'})")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="WAIT")

        # 7. Heavyweight & Sectoral Concordance Check (P0 Enforcement)
        if component_trends:
            concordance = HeavyweightConcordanceEngine.evaluate(component_trends, direction_candidate)
            if concordance.recommendation == "VETO":
                reasons.append(f"HEAVYWEIGHT_VETO: Divergence in driving stocks (Score: {concordance.concordance_score:.2f}, Lagging: {', '.join(concordance.lagging_stocks)})")
                return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="VETOED_HEAVYWEIGHT")
            elif concordance.recommendation == "CAUTION":
                reasons.append(f"HEAVYWEIGHT_NOTE: Moderate alignment with {', '.join(concordance.leading_stocks)}")

        # 8. Anomaly & Institutional Trap Audit (P0 Enforcement)
        trap_audit = AnomalyAuditor.audit_signal(
            direction=direction_candidate,
            df_5m=df_5m,
            pcr_value=pcr_val,
            rvol=rvol_val,
            nearest_resistance_dist=key_levels.distance_to_resistance_pts,
            nearest_support_dist=key_levels.distance_to_support_pts
        )
        if trap_audit.get("is_trap_likely", False):
            reasons.append(f"TRAP_VETO: {trap_audit.get('audit_summary')}")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="VETOED_TRAP")

        # Order Flow CVD Note
        if direction_candidate == "BUY" and not cvd_aligned_buy:
            reasons.append("ORDER_FLOW_NOTE: Buy setup with negative/neutral Volume Delta (institutional caution)")
        elif direction_candidate == "SELL" and not cvd_aligned_sell:
            reasons.append("ORDER_FLOW_NOTE: Sell setup with positive/neutral Volume Delta (institutional caution)")

        # Cooldown check
        if self.risk_engine.is_in_cooldown(direction_candidate, now):
            reasons.append(f"Signal cooldown active for {direction_candidate} (protecting against repeat alert spam)")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, decision_type="COOLDOWN")

        # 9. 12-Factor Scoring
        is_buy = (direction_candidate == "BUY")
        ema_aligned = (ema_9 > ema_21 > ema_50) if is_buy else (ema_9 < ema_21 < ema_50)
        headroom = key_levels.has_headroom_for_buy if is_buy else key_levels.has_headroom_for_sell

        breakdown = SignalScorer.calculate_score(
            direction=direction_candidate,
            mtf_aligned=(mtf_state.is_aligned_for_buy if is_buy else mtf_state.is_aligned_for_sell),
            mtf_concordance=mtf_state.concordance_score,
            structure_type=structure.trend_type if structure.structure_event == "NONE" else structure.structure_event,
            price_vs_vwap=(current_price > vwap_val if is_buy else current_price < vwap_val),
            ema_aligned=ema_aligned,
            volume_expanding=vol_expanding,
            rsi_value=rsi_val,
            candlestick_pattern=candle_pattern,
            headroom_available=headroom,
            volatility_tradable=vol_state.is_tradable,
            event_penalty=event_status.confidence_penalty,
            pcr=pcr_val,
            call_wall=float(oi_walls.get("call_wall_strike")) if oi_walls.get("call_wall_strike") else None,
            put_wall=float(oi_walls.get("put_wall_strike")) if oi_walls.get("put_wall_strike") else None,
            current_price=current_price,
            atm_iv=atm_iv,
            spread_pct=spread_pct,
            liquidity_status=liquidity_status,
        )

        if breakdown.total_score < self.score_threshold:
            reasons.append(f"Score {breakdown.total_score}/100 is below minimum threshold {self.score_threshold}")
            for k, v in breakdown.details.items():
                reasons.append(f"{k}: {v}")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, breakdown, decision_type="SCORE_BELOW_THRESHOLD")

        # 10. Empirical Bayesian Probability Calibration & Meta-Labeling (P1 Enforcement)
        prob_calibration = ProbabilityCalibrator.calibrate(
            raw_score=breakdown.total_score,
            market_regime=mtf_state.overall_regime,
            target_pts=28.0,
            stop_loss_pts=14.0,
            lot_size=getattr(settings, f"{symbol.upper()}_LOT_SIZE", 65)
        )

        if prob_calibration.meta_label_verdict == "REJECT":
            reasons.append(f"META_LABEL_VETO: {prob_calibration.rationale}")
            return self._build_wait(sig_id, symbol, now, mtf_state.overall_regime, reasons, tf_states_str, breakdown, decision_type="VETOED_META_LABEL")

        # 11. Compute Spot Risk Parameters & Strike Selection
        risk_params = self.risk_engine.calculate_levels(
            direction=direction_candidate,
            current_price=current_price,
            atr_value=atr_val,
            volatility_adjustment=vol_state.risk_adjustment_factor
        )

        strike_info = select_optimal_strike(
            spot_price=current_price,
            signal_type=direction_candidate
        )
        opt_levels = translate_spot_to_option_levels(
            spot_entry=risk_params.entry_price,
            spot_sl=risk_params.stop_loss,
            spot_target=risk_params.target_1,
            option_strike_info=strike_info
        )

        self.risk_engine.register_signal(direction_candidate, now)

        reasons.append(f"High-probability {direction_candidate} setup confirmed (Score {breakdown.total_score}/100)")
        reasons.append(f"Calibrated Win Prob: {prob_calibration.calibrated_win_prob:.1%} | Net Expectancy: +₹{prob_calibration.expected_value_rupees:.2f}/lot")
        reasons.append(f"Option Strike: {strike_info['symbol']} | Premium Entry ₹{opt_levels['option_entry']:.1f} (SL ₹{opt_levels['option_sl']:.1f} / Target ₹{opt_levels['option_target']:.1f})")
        reasons.append(f"Delta: {strike_info['delta']} | Theta: ₹{strike_info['theta_day']}/day | Spot R:R 1:{risk_params.risk_reward_ratio}")

        # Log decision to research ledger
        audit_ledger.log_decision(
            signal_id=sig_id,
            symbol=symbol,
            direction=direction_candidate,
            score=breakdown.total_score,
            calibrated_prob=prob_calibration.calibrated_win_prob,
            expected_value_rupees=prob_calibration.expected_value_rupees,
            market_regime=mtf_state.overall_regime,
            entry_price=risk_params.entry_price,
            stop_loss=risk_params.stop_loss,
            target_1=risk_params.target_1,
            option_symbol=strike_info["symbol"],
            option_entry=opt_levels["option_entry"],
            option_sl=opt_levels["option_sl"],
            option_target=opt_levels["option_target"],
            decision_type="SIGNAL_GENERATED",
            reasons=reasons
        )

        return MasterSignalResult(
            signal_id=sig_id,
            symbol=symbol,
            timestamp=now,
            direction=direction_candidate,
            entry_price=risk_params.entry_price,
            stop_loss=risk_params.stop_loss,
            target_1=risk_params.target_1,
            target_2=risk_params.target_2,
            score=breakdown.total_score,
            quality=breakdown.quality,
            market_regime=mtf_state.overall_regime,
            timeframe_states=tf_states_str,
            reasons=reasons,
            scoring_breakdown=breakdown,
            calibrated_win_prob=prob_calibration.calibrated_win_prob,
            expected_value_rupees=prob_calibration.expected_value_rupees,
            meta_label_verdict=prob_calibration.meta_label_verdict,
            option_strike=strike_info["strike"],
            option_type=strike_info["option_type"],
            option_symbol=strike_info["symbol"],
            option_entry=opt_levels["option_entry"],
            option_sl=opt_levels["option_sl"],
            option_target=opt_levels["option_target"],
            delta=strike_info["delta"],
            theta=strike_info["theta_day"],
            iv=strike_info["iv"],
            status="ACTIVE"
        )

    def _build_wait(
        self,
        sig_id: str,
        symbol: str,
        now: datetime,
        regime: str,
        reasons: list[str],
        tf_states: Optional[Dict[str, str]] = None,
        breakdown: Optional[ScoringBreakdown] = None,
        decision_type: str = "WAIT"
    ) -> MasterSignalResult:
        default_breakdown = breakdown or ScoringBreakdown(0, 0, 0, 0, 0, "NO_TRADE", {})
        
        # Log wait/veto decision to research ledger
        audit_ledger.log_decision(
            signal_id=sig_id,
            symbol=symbol,
            direction="WAIT",
            score=default_breakdown.total_score,
            calibrated_prob=0.0,
            expected_value_rupees=0.0,
            market_regime=regime,
            entry_price=None,
            stop_loss=None,
            target_1=None,
            option_symbol=None,
            option_entry=None,
            option_sl=None,
            option_target=None,
            decision_type=decision_type,
            reasons=reasons
        )

        return MasterSignalResult(
            signal_id=sig_id,
            symbol=symbol,
            timestamp=now,
            direction="WAIT",
            entry_price=None,
            stop_loss=None,
            target_1=None,
            target_2=None,
            score=default_breakdown.total_score,
            quality=default_breakdown.quality,
            market_regime=regime,
            timeframe_states=tf_states or {"15m": "NEUTRAL", "10m": "NEUTRAL", "5m": "NEUTRAL", "3m": "NEUTRAL", "1m": "NEUTRAL"},
            reasons=reasons,
            scoring_breakdown=default_breakdown,
            calibrated_win_prob=0.0,
            expected_value_rupees=0.0,
            meta_label_verdict="REJECT",
            status="ACTIVE"
        )
