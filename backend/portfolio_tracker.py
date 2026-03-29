# ============================================================
# PORTFOLIO TRACKER — Alpha vs Omega Head-to-Head
#
# Tracks daily performance of both portfolios.
# Alpha = existing L7 pipeline portfolio
# Omega = scenario-based minimum-regret portfolio
# ============================================================

import json
import os
import logging
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("aether.portfolio_tracker")

DATA_FILE = "data/portfolio_tracker.json"


class PortfolioTracker:
    """Tracks Alpha and Omega portfolios with daily snapshots."""

    def __init__(self):
        self.alpha_weights: Dict[str, float] = {}       # Current Alpha weights
        self.omega_weights: Dict[str, float] = {}       # Current Omega weights
        self.alpha_history: List[Dict] = []             # Daily snapshots
        self.omega_history: List[Dict] = []             # Daily snapshots
        self.start_date: Optional[str] = None
        self._load()

    def _load(self):
        """Load from KV store or file."""
        data = None
        try:
            from db import kv_get
            data = kv_get("portfolio_tracker")
        except Exception:
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass

        if data and isinstance(data, dict):
            self.alpha_weights = data.get("alpha_weights", {})
            self.omega_weights = data.get("omega_weights", {})
            self.alpha_history = data.get("alpha_history", [])[-365:]
            self.omega_history = data.get("omega_history", [])[-365:]
            self.start_date = data.get("start_date")

    def _save(self):
        """Save to KV store or file."""
        data = {
            "alpha_weights": self.alpha_weights,
            "omega_weights": self.omega_weights,
            "alpha_history": self.alpha_history[-365:],
            "omega_history": self.omega_history[-365:],
            "start_date": self.start_date,
        }
        try:
            from db import kv_set
            kv_set("portfolio_tracker", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, default=str)

    def update_alpha(self, weights: Dict[str, float]):
        """Update Alpha portfolio weights from L7 pipeline output."""
        self.alpha_weights = weights
        if not self.start_date:
            self.start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def update_omega(self, weights: Dict[str, float]):
        """Update Omega portfolio weights from scenario engine."""
        self.omega_weights = weights
        if not self.start_date:
            self.start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def snapshot_daily(self, prices: Dict) -> Dict:
        """
        Take daily snapshot of both portfolios.
        Prices format: {"sp500": {"price": 5800}, "gold": {"price": 2300}, ...}
        OR simple: {"sp500": 5800, "gold": 2300, ...}
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Don't duplicate today
        if self.alpha_history and self.alpha_history[-1].get("date") == today:
            return {"status": "already_snapped"}

        # Calculate daily returns from price changes
        def calc_daily_return(weights, prices_dict):
            if not weights:
                return 0.0

            # Get price for each asset
            total_return = 0.0
            total_weight = 0.0

            for asset, weight in weights.items():
                price_data = prices_dict.get(asset, prices_dict.get(asset.lower()))
                if price_data is None:
                    continue

                price = price_data.get("price", price_data) if isinstance(price_data, dict) else price_data
                if not isinstance(price, (int, float)) or price <= 0:
                    continue

                change = price_data.get("change_24h", 0) if isinstance(price_data, dict) else 0
                if isinstance(change, (int, float)):
                    daily_ret = change / 100.0  # Convert percentage
                else:
                    daily_ret = 0.0

                total_return += weight * daily_ret
                total_weight += weight

            return total_return if total_weight > 0 else 0.0

        alpha_return = calc_daily_return(self.alpha_weights, prices)
        omega_return = calc_daily_return(self.omega_weights, prices)

        # Cumulative value (starting at 1.0)
        alpha_prev = self.alpha_history[-1]["cumulative"] if self.alpha_history else 1.0
        omega_prev = self.omega_history[-1]["cumulative"] if self.omega_history else 1.0

        alpha_cum = alpha_prev * (1 + alpha_return)
        omega_cum = omega_prev * (1 + omega_return)

        alpha_snap = {
            "date": today,
            "daily_return": round(alpha_return, 6),
            "cumulative": round(alpha_cum, 6),
        }
        omega_snap = {
            "date": today,
            "daily_return": round(omega_return, 6),
            "cumulative": round(omega_cum, 6),
        }

        self.alpha_history.append(alpha_snap)
        self.omega_history.append(omega_snap)
        self._save()

        logger.info(
            f"Tracker: Alpha={alpha_return:+.2%} (cum={alpha_cum:.4f}), "
            f"Omega={omega_return:+.2%} (cum={omega_cum:.4f})"
        )

        return {"alpha": alpha_snap, "omega": omega_snap}

    def get_comparison(self, days: int = 30) -> Dict:
        """Head-to-head comparison over N days."""
        alpha = self.alpha_history[-days:] if self.alpha_history else []
        omega = self.omega_history[-days:] if self.omega_history else []

        def compute_stats(history):
            if len(history) < 2:
                return {"cum_return": 0, "sharpe": 0, "max_drawdown": 0, "days_tracked": len(history)}

            returns = [h["daily_return"] for h in history]
            cum = history[-1]["cumulative"] / history[0]["cumulative"] - 1 if history[0]["cumulative"] > 0 else 0

            # Sharpe (annualized)
            avg = np.mean(returns)
            std = np.std(returns) if len(returns) > 1 else 0.01
            sharpe = (avg * 252) / (std * np.sqrt(252)) if std > 0 else 0

            # Max drawdown
            cums = [h["cumulative"] for h in history]
            peak = cums[0]
            max_dd = 0
            for c in cums:
                if c > peak:
                    peak = c
                dd = (peak - c) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)

            return {
                "cum_return": round(cum, 4),
                "sharpe": round(float(sharpe), 2),
                "max_drawdown": round(max_dd, 4),
                "days_tracked": len(history),
                "best_day": round(max(returns), 4) if returns else 0,
                "worst_day": round(min(returns), 4) if returns else 0,
            }

        alpha_stats = compute_stats(alpha)
        omega_stats = compute_stats(omega)

        # Determine winner
        if alpha_stats["days_tracked"] < 5 or omega_stats["days_tracked"] < 5:
            winner = "too_early"
            margin = 0
        elif omega_stats["sharpe"] > alpha_stats["sharpe"]:
            winner = "omega"
            margin = omega_stats["sharpe"] - alpha_stats["sharpe"]
        else:
            winner = "alpha"
            margin = alpha_stats["sharpe"] - omega_stats["sharpe"]

        return {
            "alpha": {
                **alpha_stats,
                "weights": self.alpha_weights,
                "name": "Alpha (Pipeline L7)",
            },
            "omega": {
                **omega_stats,
                "weights": self.omega_weights,
                "name": "Omega (Scenario Min-Regret)",
            },
            "winner": winner,
            "margin": round(margin, 2),
            "days_compared": min(len(alpha), len(omega)),
            "start_date": self.start_date,
        }

    def get_history_chart(self, days: int = 90) -> Dict:
        """Return chart data for frontend visualization."""
        alpha = self.alpha_history[-days:]
        omega = self.omega_history[-days:]

        return {
            "alpha": [{"date": h["date"], "value": h["cumulative"]} for h in alpha],
            "omega": [{"date": h["date"], "value": h["cumulative"]} for h in omega],
            "labels": {
                "alpha": "Alpha (Pipeline)",
                "omega": "Omega (Scenarios)",
            },
        }


# Singleton
tracker = PortfolioTracker()
