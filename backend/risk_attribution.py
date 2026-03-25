# ============================================================
# FIL: backend/risk_attribution.py
# Identifierar vilken position som bidrar mest till portföljrisk
# ============================================================

import numpy as np
import pandas as pd
from typing import Dict, List


class RiskAttribution:
    """
    Dekomponerar portföljens totala risk till bidrag per position.
    Svarar på: "Vilken position är det som GÖR min portfölj riskabel?"
    """

    def __init__(self, returns: pd.DataFrame, weights: Dict[str, float]):
        self.returns = returns
        self.assets = [a for a in weights.keys() if a in returns.columns]
        self.weights = np.array([weights.get(a, 0) / 100 for a in self.assets])
        if len(self.assets) > 0:
            self.cov = returns[self.assets].cov().values * 252
        else:
            self.cov = np.array([[]])

    def compute(self) -> Dict:
        """
        Marginal risk contribution (MRC) per position.
        MRC_i = w_i * (Σ @ w)_i / σ_p
        """
        if len(self.assets) == 0:
            return {"error": "Inga matchande tillgångar"}

        port_var = self.weights @ self.cov @ self.weights
        port_vol = np.sqrt(port_var)

        if port_vol < 1e-8:
            return {"error": "Portföljvolatilitet för låg"}

        # Marginal contribution
        marginal = self.cov @ self.weights
        risk_contribution = self.weights * marginal / port_vol
        pct_contribution = risk_contribution / port_vol * 100

        results = []
        for i, asset in enumerate(self.assets):
            weight_pct = float(self.weights[i]) * 100
            risk_pct = float(pct_contribution[i])
            results.append({
                "asset": asset,
                "weight_pct": round(weight_pct, 2),
                "risk_contribution_pct": round(risk_pct, 2),
                "risk_contribution_abs": round(float(risk_contribution[i]) * 100, 3),
                "is_diversifying": risk_pct < weight_pct,
                "efficiency": round(risk_pct / (weight_pct + 1e-8), 2)
            })

        # Sortera: störst riskbidrag först
        results.sort(key=lambda x: x["risk_contribution_pct"], reverse=True)

        # Identifiera problem
        problems = [r for r in results if r["efficiency"] > 1.5 and r["weight_pct"] > 3]
        diversifiers = [r for r in results if r["is_diversifying"] and r["weight_pct"] > 2]

        return {
            "portfolio_volatility_pct": round(float(port_vol) * 100, 2),
            "positions": results,
            "top_risk_contributor": results[0] if results else None,
            "best_diversifier": min(results, key=lambda x: x["efficiency"]) if results else None,
            "problems": [{
                "asset": p["asset"],
                "message": f"{p['asset']} bidrar {p['risk_contribution_pct']:.0f}% av risken men är bara {p['weight_pct']:.0f}% av portföljen"
            } for p in problems],
            "diversifiers": [{
                "asset": d["asset"],
                "message": f"{d['asset']} är {d['weight_pct']:.0f}% av portföljen men bidrar bara {d['risk_contribution_pct']:.0f}% av risken"
            } for d in diversifiers]
        }
