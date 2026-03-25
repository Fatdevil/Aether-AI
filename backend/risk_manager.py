# ============================================================
# FIL: backend/risk_manager.py
# Portfolio-level trailing stop med gradvis reducering
# ============================================================

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskManagerConfig:
    """Konfiguration per riskprofil"""
    max_drawdown_pct: float = 8.0      # Trigger-nivå (% från topp)
    reduction_factor: float = 0.5       # Halvera risk vid trigger
    recovery_days: int = 5              # Dagar för gradvis återställning
    min_cash_pct: float = 15.0          # Minimum kassa oavsett
    cooldown_days: int = 10             # Min dagar mellan triggers


PROFILE_CONFIGS = {
    "conservative": RiskManagerConfig(max_drawdown_pct=5.0,  reduction_factor=0.6, min_cash_pct=30.0),
    "balanced":     RiskManagerConfig(max_drawdown_pct=8.0,  reduction_factor=0.5, min_cash_pct=15.0),
    "aggressive":   RiskManagerConfig(max_drawdown_pct=12.0, reduction_factor=0.4, min_cash_pct=5.0),
    "turbo":        RiskManagerConfig(max_drawdown_pct=15.0, reduction_factor=0.3, min_cash_pct=3.0),
}


class PortfolioRiskManager:
    def __init__(self):
        self.peak_value: float = 0.0
        self.current_drawdown: float = 0.0
        self.stop_triggered: bool = False
        self.trigger_date: Optional[datetime] = None
        self.recovery_progress: float = 0.0  # 0.0 = full reduction, 1.0 = recovered

    def update(self, portfolio_value: float, profile: str = "balanced") -> Dict:
        config = PROFILE_CONFIGS.get(profile, PROFILE_CONFIGS["balanced"])

        # Uppdatera peak
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
            self.stop_triggered = False
            self.recovery_progress = 1.0

        # Beräkna drawdown
        if self.peak_value > 0:
            self.current_drawdown = (self.peak_value - portfolio_value) / self.peak_value * 100

        # Kolla trigger
        result = {
            "drawdown_pct": round(self.current_drawdown, 2),
            "peak_value": round(self.peak_value, 2),
            "stop_triggered": self.stop_triggered,
            "risk_multiplier": 1.0,
            "action": "NORMAL",
            "message": ""
        }

        if self.current_drawdown >= config.max_drawdown_pct and not self.stop_triggered:
            self.stop_triggered = True
            self.trigger_date = datetime.now()
            self.recovery_progress = 0.0
            result["action"] = "REDUCE_RISK"
            result["risk_multiplier"] = config.reduction_factor
            result["message"] = (
                f"⚠️ TRAILING STOP: -{self.current_drawdown:.1f}% från topp. "
                f"Reducerar risk till {config.reduction_factor*100:.0f}%"
            )
            logger.warning(result["message"])

        elif self.stop_triggered:
            # Gradvis återställning
            if self.trigger_date:
                days_since = (datetime.now() - self.trigger_date).days
                self.recovery_progress = min(days_since / config.recovery_days, 1.0)

            risk_mult = config.reduction_factor + (1.0 - config.reduction_factor) * self.recovery_progress
            result["risk_multiplier"] = round(risk_mult, 3)
            result["action"] = "RECOVERING" if self.recovery_progress < 1.0 else "NORMAL"
            result["message"] = (
                f"Återhämtning {self.recovery_progress*100:.0f}%, "
                f"risk-multiplikator {risk_mult:.2f}"
            )

        return result

    def apply_to_weights(self, weights: Dict[str, float], risk_result: Dict) -> Dict[str, float]:
        """Applicera risk-multiplikator på vikter, flytta till kassa"""
        if risk_result["risk_multiplier"] >= 1.0:
            return weights

        multiplier = risk_result["risk_multiplier"]
        adjusted = {}
        freed_capital = 0.0

        for asset, weight in weights.items():
            if asset in ("kassa", "kort_ranta", "cash"):
                adjusted[asset] = weight
            else:
                new_weight = weight * multiplier
                freed_capital += weight - new_weight
                adjusted[asset] = round(new_weight, 2)

        # Lägg frigjort kapital i kassa
        adjusted["kassa"] = adjusted.get("kassa", 0) + round(freed_capital, 2)
        return adjusted


# ============================================================
# PositionStopLoss: Per-position trailing stop
# ============================================================

from typing import List


class PositionStopLoss:
    """
    Per-position trailing stop.
    Skyddar mot enskilda positioner som faller kraftigt
    medan portföljen totalt ser ok ut.
    """

    # Default stop-nivåer per tillgångstyp
    DEFAULT_STOPS = {
        "bitcoin": 0.20, "crypto": 0.25,
        "guld": 0.10, "gold": 0.10, "silver": 0.12,
        "ranta": 0.05, "us10y": 0.05,
        "energi": 0.18, "oil": 0.18,
        "tech": 0.15, "finans": 0.15, "forsvar": 0.15, "halsa": 0.15,
        "sp500": 0.12, "acwi": 0.12,
        "leveraged": 0.25, "sso": 0.25, "qld": 0.25,
    }

    def __init__(self):
        self.position_peaks: Dict[str, float] = {}

    def update_prices(self, current_prices: Dict[str, float]):
        """Uppdatera peak-priser per position"""
        for asset, price in current_prices.items():
            if asset not in self.position_peaks or price > self.position_peaks[asset]:
                self.position_peaks[asset] = price

    def check_stops(
        self,
        current_prices: Dict[str, float],
        stop_levels: Dict[str, float] = None
    ) -> List[Dict]:
        """
        Kolla om några positions-stops har triggats.
        Returns lista med triggade stops.
        """
        if stop_levels is None:
            stop_levels = self.DEFAULT_STOPS

        triggered = []
        for asset, price in current_prices.items():
            peak = self.position_peaks.get(asset, price)
            if peak <= 0:
                continue

            drawdown = (peak - price) / peak

            # Hitta relevant stop-nivå
            stop_pct = 0.15  # Default
            asset_lower = asset.lower()
            for cat, level in stop_levels.items():
                if cat.lower() in asset_lower:
                    stop_pct = level
                    break

            if drawdown >= stop_pct:
                triggered.append({
                    "asset": asset,
                    "peak_price": round(peak, 2),
                    "current_price": round(price, 2),
                    "drawdown_pct": round(drawdown * 100, 2),
                    "stop_level_pct": round(stop_pct * 100, 1),
                    "action": "SÄLJ_HALVA",
                    "message": (
                        f"⚠️ {asset}: -{drawdown*100:.1f}% från topp "
                        f"({peak:.2f} → {price:.2f}). Stop vid {stop_pct*100:.0f}%."
                    )
                })

        return triggered
