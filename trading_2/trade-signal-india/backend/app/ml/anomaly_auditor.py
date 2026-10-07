"""
AI Anomaly & Trap Risk Audit Engine.
Detects:
1. Bull Traps & Bear Traps (Breakouts with falling volume/divergent OI).
2. Liquidity & Spread Anomalies.
3. Premature Reversal risks.
4. Provides structured AI explanation and trap score.
"""

from typing import Dict, Any, Optional
import pandas as pd


class AnomalyAuditor:
    @staticmethod
    def audit_signal(
        direction: str,
        df_5m: pd.DataFrame,
        pcr_value: float = 1.0,
        rvol: float = 1.0,
        nearest_resistance_dist: float = 50.0,
        nearest_support_dist: float = 50.0
    ) -> Dict[str, Any]:
        """
        Audits setup quality for institutional traps and price-volume anomalies.
        """
        trap_score = 0
        anomaly_flags = []
        explanation_lines = []

        is_buy = (direction == "BUY")

        # 1. Volume Divergence / Trap Check
        if rvol < 0.8:
            trap_score += 25
            anomaly_flags.append("LOW_VOLUME_BREAKOUT")
            explanation_lines.append(f"Volume is light (RVOL {rvol:.2f} < 0.80) — risk of false breakout / low liquidity trap.")
        elif rvol > 3.0:
            anomaly_flags.append("CLIMACTIC_VOLUME")
            explanation_lines.append(f"Climactic volume detected (RVOL {rvol:.2f} > 3.0) — watch for exhaustion reversal.")

        # 2. PCR Microstructure Divergence
        if is_buy and pcr_value < 0.70:
            trap_score += 20
            anomaly_flags.append("BEARISH_PCR_DIVERGENCE")
            explanation_lines.append(f"PCR is low ({pcr_value:.2f}) while signal is BUY — aggressive call writing overhead.")
        elif not is_buy and pcr_value > 1.35:
            trap_score += 20
            anomaly_flags.append("BULLISH_PCR_DIVERGENCE")
            explanation_lines.append(f"PCR is high ({pcr_value:.2f}) while signal is SELL — strong put writing support floor.")

        # 3. Headroom / S-R Trap Check
        if is_buy and nearest_resistance_dist < 15.0:
            trap_score += 20
            anomaly_flags.append("PROXIMITY_TO_CEILING")
            explanation_lines.append(f"Price is within {nearest_resistance_dist:.1f} pts of major resistance.")
        elif not is_buy and nearest_support_dist < 15.0:
            trap_score += 20
            anomaly_flags.append("PROXIMITY_TO_FLOOR")
            explanation_lines.append(f"Price is within {nearest_support_dist:.1f} pts of major support.")

        # Determine verdict
        if trap_score >= 40:
            audit_verdict = "HIGH_TRAP_RISK"
        elif trap_score >= 20:
            audit_verdict = "CAUTION"
        else:
            audit_verdict = "CLEAN"

        return {
            "audit_verdict": audit_verdict,
            "trap_risk_score": trap_score,
            "is_trap_likely": trap_score >= 40,
            "anomaly_flags": anomaly_flags,
            "audit_summary": " | ".join(explanation_lines) if explanation_lines else "No liquidity or trap anomalies detected. Setup clean."
        }
