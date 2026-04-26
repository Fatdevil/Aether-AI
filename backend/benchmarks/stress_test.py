# ============================================================
# FIL: backend/stress_test.py
# Monte Carlo stresstest + historiska scenarier
# ============================================================

import numpy as np
import pandas as pd
from typing import Dict, List
from scipy.stats import norm


class MonteCarloStressTest:
    """
    Forward-looking riskanalys via Monte Carlo-simulering.
    Genererar 10,000 scenarier för att uppskatta:
    - Sannolikhet för förlust > X%
    - Förväntat worst-case (CVaR)
    - Konfidensintervall för avkastning
    """

    def __init__(self, returns: pd.DataFrame, n_simulations: int = 10000, horizon_days: int = 21):
        self.returns = returns
        self.n_sim = n_simulations
        self.horizon = horizon_days

    def run(self, weights: Dict[str, float]) -> Dict:
        assets = [a for a in weights.keys() if a in self.returns.columns]
        if not assets:
            return {"error": "Inga matchande tillgångar i historisk data"}

        w = np.array([weights.get(a, 0) / 100 for a in assets])

        # Historiska parametrar
        mu = self.returns[assets].mean().values
        cov = self.returns[assets].cov().values

        # Cholesky-dekomposition för korrelerad simulering
        try:
            L = np.linalg.cholesky(cov)
        except np.linalg.LinAlgError:
            # Matris ej positivt definit — lägg till liten diagonal
            cov_adj = cov + np.eye(len(cov)) * 1e-6
            L = np.linalg.cholesky(cov_adj)

        # Simulera
        simulated_returns = np.zeros(self.n_sim)

        for sim in range(self.n_sim):
            cumulative = 0.0
            for day in range(self.horizon):
                z = np.random.standard_normal(len(assets))
                daily_returns = mu + L @ z
                portfolio_return = w @ daily_returns
                cumulative += portfolio_return
            simulated_returns[sim] = cumulative

        # Statistik
        sorted_returns = np.sort(simulated_returns)
        percentiles = {
            "p1": round(float(np.percentile(simulated_returns, 1)) * 100, 2),
            "p5": round(float(np.percentile(simulated_returns, 5)) * 100, 2),
            "p10": round(float(np.percentile(simulated_returns, 10)) * 100, 2),
            "p25": round(float(np.percentile(simulated_returns, 25)) * 100, 2),
            "p50": round(float(np.percentile(simulated_returns, 50)) * 100, 2),
            "p75": round(float(np.percentile(simulated_returns, 75)) * 100, 2),
            "p90": round(float(np.percentile(simulated_returns, 90)) * 100, 2),
            "p95": round(float(np.percentile(simulated_returns, 95)) * 100, 2),
            "p99": round(float(np.percentile(simulated_returns, 99)) * 100, 2),
        }

        # CVaR (5%)
        cutoff = int(0.05 * self.n_sim)
        cvar_5 = round(float(np.mean(sorted_returns[:cutoff])) * 100, 2)

        # Sannolikhet för förlust
        prob_loss = round(float(np.mean(simulated_returns < 0)) * 100, 1)
        prob_loss_5pct = round(float(np.mean(simulated_returns < -0.05)) * 100, 1)
        prob_loss_10pct = round(float(np.mean(simulated_returns < -0.10)) * 100, 1)
        prob_gain_10pct = round(float(np.mean(simulated_returns > 0.10)) * 100, 1)

        return {
            "horizon_days": self.horizon,
            "n_simulations": self.n_sim,
            "expected_return_pct": round(float(np.mean(simulated_returns)) * 100, 2),
            "volatility_pct": round(float(np.std(simulated_returns)) * 100, 2),
            "percentiles": percentiles,
            "cvar_5_pct": cvar_5,
            "probabilities": {
                "loss": prob_loss,
                "loss_gt_5pct": prob_loss_5pct,
                "loss_gt_10pct": prob_loss_10pct,
                "gain_gt_10pct": prob_gain_10pct
            },
            "interpretation": self._interpret(cvar_5, prob_loss_5pct, prob_loss_10pct)
        }

    def _interpret(self, cvar: float, p5: float, p10: float) -> str:
        if p10 > 15:
            return f"⚠️ HÖG RISK: {p10}% chans för >10% förlust. Överväg att minska risk."
        elif p5 > 20:
            return f"⚡ FÖRHÖJD RISK: {p5}% chans för >5% förlust. Bevaka noggrant."
        else:
            return f"✅ NORMAL RISK: CVaR {cvar}%. Risknivå inom ramar."

    def historical_scenarios(self, weights: Dict[str, float]) -> List[Dict]:
        """Testa portföljen mot historiska kriser"""
        assets = [a for a in weights.keys() if a in self.returns.columns]
        if not assets:
            return []

        w = np.array([weights.get(a, 0) / 100 for a in assets])

        scenarios = {
            "COVID Crash (Mar 2020)": ("2020-02-20", "2020-03-23"),
            "2022 Bear Market": ("2022-01-03", "2022-06-16"),
            "SVB Crisis (Mar 2023)": ("2023-03-08", "2023-03-15"),
            "Iran Crisis (Feb 2026)": ("2026-02-28", "2026-03-15"),
        }

        results = []
        for name, (start, end) in scenarios.items():
            try:
                period_returns = self.returns[assets].loc[start:end]
                if len(period_returns) < 2:
                    continue
                cumulative = (1 + period_returns).prod()
                port_return = float((cumulative.values ** w).prod() - 1)
                results.append({
                    "scenario": name,
                    "portfolio_return_pct": round(port_return * 100, 2),
                    "worst_asset": str(period_returns.columns[period_returns.sum().argmin()]),
                    "best_asset": str(period_returns.columns[period_returns.sum().argmax()]),
                    "days": len(period_returns)
                })
            except Exception:
                continue

        return results
