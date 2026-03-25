# ============================================================
# FIL: backend/rebalance_scheduler.py
# Smart rebalansering: kalender vs tröskel vs signal
# ============================================================

from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class RebalanceConfig:
    # Kalenderbaserad
    calendar_interval_days: int = 30

    # Tröskelbaserad
    drift_threshold_pct: float = 5.0
    total_drift_threshold_pct: float = 10.0

    # Signalbaserad
    regime_change_triggers: bool = True
    high_conviction_threshold: float = 8.0

    # Kostnadsbegränsning
    min_trade_value_sek: float = 5000
    max_trades_per_rebalance: int = 5


class RebalanceScheduler:
    def __init__(self, config: RebalanceConfig = None):
        self.config = config or RebalanceConfig()
        self.last_rebalance: Optional[datetime] = None
        self.rebalance_history: list = []

    def should_rebalance(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        regime_changed: bool = False,
        max_conviction_score: float = 0,
        portfolio_value: float = 0
    ) -> Dict:
        """
        Avgör om rebalansering ska ske och varför.
        Returns: {"rebalance": True/False, "reason": "...", "urgency": "..."}
        """
        now = datetime.now()
        reasons = []
        urgency = "LÅG"

        # 1. Kalenderbaserad
        if self.last_rebalance:
            days_since = (now - self.last_rebalance).days
            if days_since >= self.config.calendar_interval_days:
                reasons.append(f"Kalender: {days_since} dagar sedan senaste ({self.config.calendar_interval_days}d intervall)")
                urgency = "MEDEL"
        else:
            reasons.append("Första rebalansering")
            urgency = "HÖG"

        # 2. Tröskelbaserad (drift)
        max_drift = 0
        total_drift = 0
        drifted_positions = []

        for asset in set(list(current_weights.keys()) + list(target_weights.keys())):
            current = current_weights.get(asset, 0)
            target = target_weights.get(asset, 0)
            drift = abs(current - target)
            total_drift += drift
            if drift > max_drift:
                max_drift = drift

            if drift > self.config.drift_threshold_pct:
                drifted_positions.append({"asset": asset, "drift_pct": round(drift, 1)})

        if max_drift > self.config.drift_threshold_pct:
            reasons.append(f"Drift: {len(drifted_positions)} positioner driftat > {self.config.drift_threshold_pct}%")
            urgency = "HÖG" if max_drift > self.config.drift_threshold_pct * 1.5 else "MEDEL"

        if total_drift > self.config.total_drift_threshold_pct:
            reasons.append(f"Total drift {total_drift:.1f}% > {self.config.total_drift_threshold_pct}%")

        # 3. Signalbaserad
        if regime_changed and self.config.regime_change_triggers:
            reasons.append("Regimskifte detekterat")
            urgency = "HÖG"

        if max_conviction_score >= self.config.high_conviction_threshold:
            reasons.append(f"Hög conviction-signal ({max_conviction_score:.1f})")
            urgency = "HÖG"

        should = len(reasons) > 0

        # Kolla om trades är tillräckligt stora
        if should and portfolio_value > 0:
            min_meaningful = self.config.min_trade_value_sek / portfolio_value * 100
            meaningful_drifts = [d for d in drifted_positions if d["drift_pct"] > min_meaningful]
            if not meaningful_drifts and not regime_changed:
                should = False
                reasons = ["Drift för liten för meningsfull trade"]

        return {
            "rebalance": should,
            "reasons": reasons,
            "urgency": urgency,
            "days_since_last": (now - self.last_rebalance).days if self.last_rebalance else None,
            "max_drift_pct": round(max_drift, 1),
            "total_drift_pct": round(total_drift, 1),
            "drifted_positions": drifted_positions,
            "recommended_trades": min(len(drifted_positions), self.config.max_trades_per_rebalance)
        }

    def record_rebalance(self, trades_executed: int, reason: str):
        self.last_rebalance = datetime.now()
        self.rebalance_history.append({
            "date": self.last_rebalance.isoformat(),
            "trades": trades_executed,
            "reason": reason
        })
