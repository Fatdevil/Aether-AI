# ============================================================
# FIL: backend/multi_timeframe.py
# Signalbekräftelse över flera tidsramar
# ============================================================

from typing import Dict, List


class MultiTimeframeConfirmation:
    """
    En signal som är stark på ALLA tidsramar är mycket mer tillförlitlig
    än en som bara syns på en tidsram.

    Daily + Weekly + Monthly alignment = STARK signal
    Daily only = SVAG signal (kan vara brus)
    """

    def __init__(self):
        self.timeframes = ["daily", "weekly", "monthly"]

    def analyze(
        self,
        daily_signals: Dict[str, float],
        weekly_signals: Dict[str, float],
        monthly_signals: Dict[str, float]
    ) -> Dict[str, Dict]:
        """
        Alla inputs: {"SP500": 7.5, "GOLD": -2.0, ...}
        Scores -10 till +10 per tidsram.
        """
        assets = set(list(daily_signals.keys()) + list(weekly_signals.keys()) + list(monthly_signals.keys()))
        results = {}

        for asset in assets:
            d = daily_signals.get(asset, 0)
            w = weekly_signals.get(asset, 0)
            m = monthly_signals.get(asset, 0)

            # Alignment: alla i samma riktning?
            signs = [1 if x > 1 else -1 if x < -1 else 0 for x in [d, w, m]]
            positive = sum(1 for s in signs if s > 0)
            negative = sum(1 for s in signs if s < 0)

            if positive == 3:
                alignment = "STARK_BULL"
                confidence_mult = 1.3
            elif negative == 3:
                alignment = "STARK_BEAR"
                confidence_mult = 1.3
            elif positive >= 2 and negative == 0:
                alignment = "BULL"
                confidence_mult = 1.1
            elif negative >= 2 and positive == 0:
                alignment = "BEAR"
                confidence_mult = 1.1
            elif positive >= 1 and negative >= 1:
                alignment = "DIVERGENT"
                confidence_mult = 0.7
            else:
                alignment = "NEUTRAL"
                confidence_mult = 0.9

            # Viktat score (monthly väger mest, daily minst)
            weighted_score = d * 0.2 + w * 0.3 + m * 0.5
            adjusted_score = weighted_score * confidence_mult

            results[asset] = {
                "daily": round(d, 1),
                "weekly": round(w, 1),
                "monthly": round(m, 1),
                "alignment": alignment,
                "confidence_multiplier": confidence_mult,
                "weighted_score": round(weighted_score, 2),
                "adjusted_score": round(adjusted_score, 2),
                "recommendation": "STARK" if abs(adjusted_score) > 5 else "MEDEL" if abs(adjusted_score) > 2 else "SVAG"
            }

        return results
