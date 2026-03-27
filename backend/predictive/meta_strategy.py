# ============================================================
# FIL: backend/predictive/meta_strategy.py
# Lär sig vilken prediktionsmetod som fungerar bäst per regim
#
# Metoder: causal_chain, event_tree, lead_lag, narrative, actor_sim
# Regimer: RISK_ON, NEUTRAL, RISK_OFF, CRISIS
# ============================================================

import numpy as np
from typing import Dict, List
from datetime import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

META_FILE = "data/meta_strategy.json"

METHODS = ["causal_chain", "event_tree", "lead_lag", "narrative", "actor_sim"]
REGIMES = ["RISK_ON", "NEUTRAL", "RISK_OFF", "CRISIS"]

DEFAULT_WEIGHTS = {
    "RISK_ON":   {"causal_chain": 0.15, "event_tree": 0.15, "lead_lag": 0.30, "narrative": 0.25, "actor_sim": 0.15},
    "NEUTRAL":   {"causal_chain": 0.20, "event_tree": 0.20, "lead_lag": 0.25, "narrative": 0.20, "actor_sim": 0.15},
    "RISK_OFF":  {"causal_chain": 0.30, "event_tree": 0.25, "lead_lag": 0.15, "narrative": 0.15, "actor_sim": 0.15},
    "CRISIS":    {"causal_chain": 0.35, "event_tree": 0.30, "lead_lag": 0.10, "narrative": 0.05, "actor_sim": 0.20},
}


class MetaStrategySelector:
    def __init__(self):
        self.records: List[Dict] = []
        self.current_weights = dict(DEFAULT_WEIGHTS)
        self._load()

    def _load(self):
        try:
            from db import kv_get
            data = kv_get("meta_strategy")
            if data:
                self.records = data.get("records", [])
                saved_weights = data.get("weights", {})
                if saved_weights:
                    self.current_weights = saved_weights
                return
        except Exception:
            pass
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, "r") as f:
                    data = json.load(f)
                    self.records = data.get("records", [])
                    saved_weights = data.get("weights", {})
                    if saved_weights:
                        self.current_weights = saved_weights
            except Exception:
                pass

    def _save(self):
        data = {"records": self.records[-2000:], "weights": self.current_weights}
        try:
            from db import kv_set
            kv_set("meta_strategy", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(META_FILE, "w") as f:
                json.dump(data, f)

    def log_method_performance(self, method: str, regime: str, quality: float):
        self.records.append({
            "method": method, "regime": regime,
            "quality": round(quality, 3),
            "timestamp": datetime.now().isoformat()
        })
        self._save()

    def update_weights(self, min_records_per_cell: int = 10) -> Dict:
        for regime in REGIMES:
            regime_records = [r for r in self.records if r["regime"] == regime]
            if len(regime_records) < min_records_per_cell * len(METHODS):
                continue

            method_scores = {}
            for method in METHODS:
                method_records = [r for r in regime_records if r["method"] == method]
                if len(method_records) < min_records_per_cell:
                    method_scores[method] = 0.5
                    continue

                decay = 0.95
                weighted_sum = 0
                weight_sum = 0
                for i, record in enumerate(reversed(method_records)):
                    w = decay ** i
                    weighted_sum += record["quality"] * w
                    weight_sum += w
                method_scores[method] = weighted_sum / weight_sum if weight_sum > 0 else 0.5

            total = sum(method_scores.values())
            if total > 0:
                self.current_weights[regime] = {
                    m: round(s / total, 3) for m, s in method_scores.items()
                }

        self._save()
        return self.current_weights

    def get_weights(self, regime: str) -> Dict[str, float]:
        return self.current_weights.get(regime, DEFAULT_WEIGHTS.get(regime, {}))

    def apply_weights(self, method_signals: Dict[str, float], regime: str) -> float:
        weights = self.get_weights(regime)
        total = sum(method_signals.get(m, 0) * weights.get(m, 0.2) for m in method_signals)
        return round(total, 2)

    def get_diagnostics(self) -> Dict:
        diagnostics = {"regimes": {}}
        for regime in REGIMES:
            regime_data = {"methods": {}, "total_records": 0}
            regime_records = [r for r in self.records if r["regime"] == regime]
            regime_data["total_records"] = len(regime_records)

            for method in METHODS:
                method_records = [r for r in regime_records if r["method"] == method]
                if not method_records:
                    continue
                avg_quality = float(np.mean([r["quality"] for r in method_records]))
                recent_5 = [r["quality"] for r in method_records[-5:]]
                older_5 = [r["quality"] for r in method_records[-10:-5]]
                regime_data["methods"][method] = {
                    "avg_quality": round(avg_quality, 3),
                    "n_records": len(method_records),
                    "current_weight": self.current_weights.get(regime, {}).get(method, 0),
                    "trend": "IMPROVING" if len(older_5) >= 3 and np.mean(recent_5) > np.mean(older_5) else "STABLE"
                }
            diagnostics["regimes"][regime] = regime_data

        total = len(self.records)
        if total < 50:
            diagnostics["recommendation"] = f"Samla mer data ({total}/50 minimum). Använder default-vikter."
        elif total < 200:
            diagnostics["recommendation"] = f"Tidig fas ({total} records). Vikterna börjar stabiliseras."
        else:
            diagnostics["recommendation"] = f"Mogen fas ({total} records). Vikterna är datadrivna."
        return diagnostics
