# ============================================================
# FIL: backend/drawdown_estimator.py
# Uppskattar återhämtningstid från drawdown
# ============================================================

import numpy as np
from typing import Dict


class DrawdownRecoveryEstimator:
    """
    När du är i en drawdown: hur lång tid tar det att komma tillbaka?
    Baserat på historiska återhämtningsmönster + Monte Carlo.
    """

    HISTORICAL_RECOVERIES = {
        "5%":  {"avg_days": 25,  "range": "2-8 veckor"},
        "10%": {"avg_days": 65,  "range": "1-4 månader"},
        "15%": {"avg_days": 120, "range": "2-8 månader"},
        "20%": {"avg_days": 200, "range": "4-14 månader"},
        "30%": {"avg_days": 400, "range": "8-24 månader"},
        "40%": {"avg_days": 700, "range": "1.5-4 år"},
    }

    def estimate(
        self,
        current_drawdown_pct: float,
        portfolio_annual_return: float = 0.08,
        portfolio_volatility: float = 0.12
    ) -> Dict:
        """Uppskatta återhämtningstid från aktuell drawdown."""
        if current_drawdown_pct <= 0:
            return {"status": "INGEN_DRAWDOWN", "message": "Portföljen är på eller nära sin topp."}

        dd = abs(current_drawdown_pct) / 100

        # Matematisk uppskattning
        if portfolio_annual_return > 0:
            daily_return = portfolio_annual_return / 252
            estimated_days = dd / daily_return
        else:
            estimated_days = 999

        # Historisk jämförelse
        historical = None
        for level, data in self.HISTORICAL_RECOVERIES.items():
            if current_drawdown_pct <= float(level.replace("%", "")):
                historical = data
                break
        if historical is None:
            historical = {"avg_days": 700, "range": "1.5-4 år"}

        # Monte Carlo-baserad uppskattning
        mc_days = self._monte_carlo_recovery(dd, portfolio_annual_return, portfolio_volatility)

        # Sannolikheter
        prob_30d = self._recovery_probability(dd, portfolio_annual_return, portfolio_volatility, 30)
        prob_90d = self._recovery_probability(dd, portfolio_annual_return, portfolio_volatility, 90)
        prob_180d = self._recovery_probability(dd, portfolio_annual_return, portfolio_volatility, 180)

        severity = "LÅG" if current_drawdown_pct < 5 else "MEDEL" if current_drawdown_pct < 10 else "HÖG" if current_drawdown_pct < 20 else "EXTREM"

        return {
            "current_drawdown_pct": round(current_drawdown_pct, 2),
            "severity": severity,
            "estimated_recovery_days": round(estimated_days),
            "monte_carlo_median_days": mc_days,
            "historical_avg_days": historical["avg_days"],
            "historical_range": historical["range"],
            "recovery_probability": {
                "within_30_days": round(prob_30d, 1),
                "within_90_days": round(prob_90d, 1),
                "within_180_days": round(prob_180d, 1)
            },
            "advice": self._advice(current_drawdown_pct, severity)
        }

    def _monte_carlo_recovery(self, dd, annual_ret, annual_vol, n_sims=5000):
        daily_ret = annual_ret / 252
        daily_vol = annual_vol / np.sqrt(252)
        recovery_days = []

        for _ in range(n_sims):
            cumulative = -dd
            days = 0
            while cumulative < 0 and days < 1000:
                daily = np.random.normal(daily_ret, daily_vol)
                cumulative += daily
                days += 1
            recovery_days.append(days)

        return int(np.median(recovery_days))

    def _recovery_probability(self, dd, annual_ret, annual_vol, horizon_days):
        daily_ret = annual_ret / 252
        daily_vol = annual_vol / np.sqrt(252)
        expected = daily_ret * horizon_days
        std = daily_vol * np.sqrt(horizon_days)

        if std < 1e-8:
            return 100.0 if expected > dd else 0.0

        from scipy.stats import norm
        prob = norm.cdf((expected - (-dd)) / std) * 100
        return min(prob, 99.9)

    def _advice(self, dd, severity):
        if severity == "LÅG":
            return "Normal marknadsrörlighet. Behåll strategi. Återhämtning sannolik inom veckor."
        elif severity == "MEDEL":
            return "Markant drawdown. Undvik panikförsäljning. Granska positioner men handla inte impulsivt."
        elif severity == "HÖG":
            return "Allvarlig drawdown. Granska: är detta en regimförändring eller temporär dipp? Överväg att minska risk om regimskifte konfirmerat."
        else:
            return "Extrem drawdown. Prioritera kapitalbevarande. Minska risk kraftigt. Återhämtning kan ta över ett år."
