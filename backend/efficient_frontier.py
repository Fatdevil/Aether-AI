# ============================================================
# FIL: backend/efficient_frontier.py
# Beräknar effektiva fronten + plottar användarens portfölj
# ============================================================

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List


class EfficientFrontierAnalyzer:
    """
    Beräknar den effektiva fronten för givna tillgångar.
    Visar var användarens portfölj ligger relativt optimalt.
    """

    def __init__(self, returns: pd.DataFrame, risk_free_rate: float = 0.035):
        self.returns = returns
        self.mu = returns.mean().values * 252
        self.cov = returns.cov().values * 252
        self.assets = returns.columns.tolist()
        self.n = len(self.assets)
        self.rf = risk_free_rate

    def compute_frontier(self, n_points: int = 20) -> List[Dict]:
        """Generera punkter på den effektiva fronten"""
        min_vol_w = self._optimize_min_vol()
        max_ret_w = self._optimize_max_return()

        min_ret = float(min_vol_w @ self.mu)
        max_ret = float(max_ret_w @ self.mu)

        frontier = []
        for target_return in np.linspace(min_ret, max_ret, n_points):
            w = self._optimize_for_return(target_return)
            if w is not None:
                port_vol = float(np.sqrt(w @ self.cov @ w))
                port_ret = float(w @ self.mu)
                frontier.append({
                    "risk": round(port_vol * 100, 2),
                    "return": round(port_ret * 100, 2),
                    "weights": {self.assets[i]: round(float(w[i]) * 100, 2) for i in range(self.n)}
                })

        return frontier

    def analyze_portfolio(self, user_weights: Dict[str, float]) -> Dict:
        """Analysera portfölj relativt den effektiva fronten."""
        w = np.array([user_weights.get(a, 0) / 100 for a in self.assets])
        user_ret = float(w @ self.mu)
        user_vol = float(np.sqrt(w @ self.cov @ w))
        user_sharpe = (user_ret - self.rf) / (user_vol + 1e-8)

        # Optimal: samma risk, max avkastning
        opt_same_risk = self._optimize_for_vol(user_vol)
        opt_sr_ret = float(opt_same_risk @ self.mu) if opt_same_risk is not None else user_ret
        opt_sr_vol = float(np.sqrt(opt_same_risk @ self.cov @ opt_same_risk)) if opt_same_risk is not None else user_vol

        # Optimal: samma avkastning, min risk
        opt_same_ret = self._optimize_for_return(user_ret)
        opt_sret_ret = float(opt_same_ret @ self.mu) if opt_same_ret is not None else user_ret
        opt_sret_vol = float(np.sqrt(opt_same_ret @ self.cov @ opt_same_ret)) if opt_same_ret is not None else user_vol

        # Max Sharpe
        max_sharpe_w = self._optimize_max_sharpe()
        ms_ret = float(max_sharpe_w @ self.mu)
        ms_vol = float(np.sqrt(max_sharpe_w @ self.cov @ max_sharpe_w))
        ms_sharpe = (ms_ret - self.rf) / (ms_vol + 1e-8)

        # Inefficiency
        return_gap = opt_sr_ret - user_ret
        risk_gap = user_vol - opt_sret_vol

        frontier = self.compute_frontier(15)

        return {
            "user_portfolio": {
                "expected_return": round(user_ret * 100, 2),
                "volatility": round(user_vol * 100, 2),
                "sharpe": round(float(user_sharpe), 3)
            },
            "optimal_same_risk": {
                "expected_return": round(opt_sr_ret * 100, 2),
                "volatility": round(opt_sr_vol * 100, 2),
                "sharpe": round((opt_sr_ret - self.rf) / (opt_sr_vol + 1e-8), 3),
                "weights": {self.assets[i]: round(float(opt_same_risk[i]) * 100, 2) for i in range(self.n)} if opt_same_risk is not None else {},
                "return_improvement": round(return_gap * 100, 2)
            },
            "optimal_same_return": {
                "expected_return": round(opt_sret_ret * 100, 2),
                "volatility": round(opt_sret_vol * 100, 2),
                "sharpe": round((opt_sret_ret - self.rf) / (opt_sret_vol + 1e-8), 3),
                "weights": {self.assets[i]: round(float(opt_same_ret[i]) * 100, 2) for i in range(self.n)} if opt_same_ret is not None else {},
                "risk_reduction": round(risk_gap * 100, 2)
            },
            "max_sharpe": {
                "expected_return": round(ms_ret * 100, 2),
                "volatility": round(ms_vol * 100, 2),
                "sharpe": round(float(ms_sharpe), 3),
                "weights": {self.assets[i]: round(float(max_sharpe_w[i]) * 100, 2) for i in range(self.n)}
            },
            "frontier": frontier,
            "inefficiency_score": round((return_gap + risk_gap) * 50, 1),
            "top_moves": self._suggest_moves(w, max_sharpe_w)
        }

    def _optimize_min_vol(self):
        def obj(w): return np.sqrt(w @ self.cov @ w)
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 0.25)] * self.n
        r = minimize(obj, np.ones(self.n)/self.n, method="SLSQP", bounds=bounds, constraints=cons)
        return r.x

    def _optimize_max_return(self):
        def obj(w): return -w @ self.mu
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 0.25)] * self.n
        r = minimize(obj, np.ones(self.n)/self.n, method="SLSQP", bounds=bounds, constraints=cons)
        return r.x

    def _optimize_for_return(self, target_return):
        def obj(w): return np.sqrt(w @ self.cov @ w)
        cons = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w: w @ self.mu - target_return}
        ]
        bounds = [(0, 0.25)] * self.n
        r = minimize(obj, np.ones(self.n)/self.n, method="SLSQP", bounds=bounds, constraints=cons)
        return r.x if r.success else None

    def _optimize_for_vol(self, target_vol):
        def obj(w): return -(w @ self.mu)
        cons = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "ineq", "fun": lambda w: target_vol - np.sqrt(w @ self.cov @ w)}
        ]
        bounds = [(0, 0.25)] * self.n
        r = minimize(obj, np.ones(self.n)/self.n, method="SLSQP", bounds=bounds, constraints=cons)
        return r.x if r.success else None

    def _optimize_max_sharpe(self):
        def neg_sharpe(w):
            ret = w @ self.mu
            vol = np.sqrt(w @ self.cov @ w)
            return -(ret - self.rf) / (vol + 1e-8)
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 0.25)] * self.n
        r = minimize(neg_sharpe, np.ones(self.n)/self.n, method="SLSQP", bounds=bounds, constraints=cons)
        return r.x

    def _suggest_moves(self, current_w, optimal_w, top_n=5):
        diffs = optimal_w - current_w
        moves = []
        for i in np.argsort(np.abs(diffs))[::-1][:top_n]:
            if abs(diffs[i]) > 0.02:
                moves.append({
                    "asset": self.assets[i],
                    "action": "ÖKA" if diffs[i] > 0 else "MINSKA",
                    "current_pct": round(float(current_w[i]) * 100, 1),
                    "target_pct": round(float(optimal_w[i]) * 100, 1),
                    "change_pct": round(float(diffs[i]) * 100, 1)
                })
        return moves
