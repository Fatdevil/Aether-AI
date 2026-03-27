# ============================================================
# FIL: backend/api_cost_tracker.py
# Spårar API-kostnader och sätter budgetar
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

COST_FILE = "data/api_costs.json"

# Uppskattade kostnader per API-anrop
API_COSTS = {
    "gemini_flash": 0.0001,
    "gemini_pro": 0.001,
    "claude_sonnet": 0.003,
    "claude_opus": 0.015,
    "marketaux_news": 0.001,
    "yahoo_finance": 0.0,
}


class APICostTracker:
    def __init__(self, monthly_budget_usd: float = 50.0):
        self.budget = monthly_budget_usd
        self.calls: List[Dict] = []
        self._load()

    def _load(self):
        try:
            from db import kv_get
            data = kv_get("api_costs")
            if data:
                self.calls = data
                return
        except Exception:
            pass
        # Fallback to file
        if os.path.exists(COST_FILE):
            try:
                with open(COST_FILE, "r") as f:
                    self.calls = json.load(f)
            except (json.JSONDecodeError, TypeError):
                self.calls = []

    def _save(self):
        data = self.calls[-10000:]  # Keep last 10k
        try:
            from db import kv_set
            kv_set("api_costs", data)
        except Exception:
            os.makedirs(os.path.dirname(COST_FILE), exist_ok=True)
            with open(COST_FILE, "w") as f:
                json.dump(data, f)

    def log_call(self, api: str, endpoint: str = "", tokens_in: int = 0, tokens_out: int = 0):
        cost = API_COSTS.get(api, 0.001)
        # Mer exakt: basera på tokens
        if "claude" in api or "gemini" in api:
            cost = (tokens_in * 0.000003 + tokens_out * 0.000015)
            if "opus" in api:
                cost *= 5

        self.calls.append({
            "timestamp": datetime.now().isoformat(),
            "api": api,
            "endpoint": endpoint,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 6)
        })
        self._save()

    def get_summary(self) -> Dict:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        month_str = month_start.isoformat()

        monthly = [c for c in self.calls if c["timestamp"] >= month_str]
        today_str = now.strftime("%Y-%m-%d")
        daily = [c for c in self.calls if c["timestamp"].startswith(today_str)]

        monthly_cost = sum(c["cost_usd"] for c in monthly)
        daily_cost = sum(c["cost_usd"] for c in daily)
        budget_remaining = self.budget - monthly_cost
        budget_pct = monthly_cost / self.budget * 100 if self.budget > 0 else 0

        # Per-API breakdown
        api_costs = {}
        for c in monthly:
            api = c["api"]
            api_costs[api] = api_costs.get(api, 0) + c["cost_usd"]

        # Prognos
        days_in_month = 30
        days_elapsed = now.day
        projected = (monthly_cost / max(days_elapsed, 1)) * days_in_month

        return {
            "today_cost_usd": round(daily_cost, 4),
            "today_calls": len(daily),
            "month_cost_usd": round(monthly_cost, 4),
            "month_calls": len(monthly),
            "budget_usd": self.budget,
            "budget_remaining_usd": round(budget_remaining, 2),
            "budget_used_pct": round(budget_pct, 1),
            "projected_month_usd": round(projected, 2),
            "over_budget": projected > self.budget,
            "per_api": {api: round(cost, 4) for api, cost in sorted(api_costs.items(), key=lambda x: x[1], reverse=True)},
            "avg_cost_per_analysis": round(monthly_cost / max(len(monthly), 1), 4),
            "warning": "BUDGET-VARNING: Projicerad kostnad överstiger budget" if projected > self.budget * 0.9 else None
        }
