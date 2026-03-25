# ============================================================
# FIL: backend/agent_performance.py
# Trackar varje agents prestation över tid
# Identifierar vilken agent som är bäst per tillgång och regim
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import numpy as np

PERFORMANCE_FILE = "data/agent_performance_log.json"


@dataclass
class AgentPrediction:
    date: str
    agent: str
    asset: str
    score: float           # -10 till +10
    go: bool               # GO/NO-GO
    regime: str            # RISK_ON/NEUTRAL/RISK_OFF
    actual_return_1d: Optional[float] = None   # Faktisk avkastning nästa dag
    actual_return_5d: Optional[float] = None   # 5-dagars avkastning
    correct_direction: Optional[bool] = None


class AgentPerformanceTracker:
    def __init__(self):
        self.predictions: List[AgentPrediction] = []
        self._load()

    def _load(self):
        if os.path.exists(PERFORMANCE_FILE):
            try:
                with open(PERFORMANCE_FILE, "r") as f:
                    data = json.load(f)
                    self.predictions = [AgentPrediction(**p) for p in data]
            except (json.JSONDecodeError, TypeError):
                self.predictions = []

    def _save(self):
        os.makedirs(os.path.dirname(PERFORMANCE_FILE), exist_ok=True)
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump([asdict(p) for p in self.predictions], f, indent=2)

    def log_predictions(self, agent_scores: Dict[str, Dict[str, float]], regime: str):
        """Logga alla agenters scores för alla tillgångar"""
        date = datetime.now().strftime("%Y-%m-%d")
        for agent, scores in agent_scores.items():
            for asset, score in scores.items():
                pred = AgentPrediction(
                    date=date,
                    agent=agent,
                    asset=asset,
                    score=score,
                    go=score > 0,
                    regime=regime
                )
                self.predictions.append(pred)
        self._save()

    def update_actuals(self, asset_returns: Dict[str, Dict[str, float]]):
        """
        Uppdatera med faktiska avkastningar
        asset_returns: {"BTC": {"1d": 0.02, "5d": -0.05}, ...}
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        for pred in self.predictions:
            if pred.date == yesterday and pred.actual_return_1d is None:
                ret_data = asset_returns.get(pred.asset, {})
                if "1d" in ret_data:
                    pred.actual_return_1d = ret_data["1d"]
                    pred.correct_direction = (
                        (pred.score > 0 and ret_data["1d"] > 0) or
                        (pred.score < 0 and ret_data["1d"] < 0) or
                        (pred.score == 0 and abs(ret_data["1d"]) < 0.005)
                    )
                if "5d" in ret_data:
                    pred.actual_return_5d = ret_data["5d"]

        self._save()

    def get_agent_report(self, lookback_days: int = 90) -> Dict:
        """Generera prestandarapport per agent"""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        recent = [p for p in self.predictions if p.date >= cutoff and p.correct_direction is not None]

        if not recent:
            return {"error": "Ingen data ännu — kräver minst 20 prediktioner med utfall", "n_predictions": 0}

        agents = set(p.agent for p in recent)
        report = {}

        for agent in agents:
            agent_preds = [p for p in recent if p.agent == agent]
            correct = sum(1 for p in agent_preds if p.correct_direction)
            total = len(agent_preds)
            accuracy = correct / total if total > 0 else 0

            # Per-regime accuracy
            regime_acc = {}
            for regime in ["RISK_ON", "NEUTRAL", "RISK_OFF"]:
                rp = [p for p in agent_preds if p.regime == regime]
                if len(rp) >= 5:
                    rc = sum(1 for p in rp if p.correct_direction)
                    regime_acc[regime] = round(rc / len(rp), 3)

            # Per-asset accuracy
            assets = set(p.asset for p in agent_preds)
            asset_acc = {}
            for asset in assets:
                ap = [p for p in agent_preds if p.asset == asset]
                if len(ap) >= 3:
                    ac = sum(1 for p in ap if p.correct_direction)
                    asset_acc[asset] = round(ac / len(ap), 3)

            # Avg score när rätt vs fel
            correct_scores = [abs(p.score) for p in agent_preds if p.correct_direction]
            wrong_scores = [abs(p.score) for p in agent_preds if not p.correct_direction]

            report[agent] = {
                "accuracy": round(accuracy, 3),
                "total_predictions": total,
                "correct": correct,
                "regime_accuracy": regime_acc,
                "asset_accuracy": asset_acc,
                "avg_confidence_when_right": round(float(np.mean(correct_scores)), 2) if correct_scores else 0,
                "avg_confidence_when_wrong": round(float(np.mean(wrong_scores)), 2) if wrong_scores else 0,
                "best_assets": sorted(asset_acc.items(), key=lambda x: x[1], reverse=True)[:3],
                "worst_assets": sorted(asset_acc.items(), key=lambda x: x[1])[:3],
            }

        # Ranking
        ranked = sorted(report.items(), key=lambda x: x[1]["accuracy"], reverse=True)
        return {
            "period_days": lookback_days,
            "total_predictions": len(recent),
            "ranking": [{"agent": a, "accuracy": d["accuracy"]} for a, d in ranked],
            "agents": report,
            "recommendation": self._generate_weight_recommendation(report)
        }

    def _generate_weight_recommendation(self, report: Dict) -> Dict[str, float]:
        """Föreslagna vikter baserat på historisk precision"""
        if not report:
            return {}
        accuracies = {a: d["accuracy"] for a, d in report.items()}
        total = sum(accuracies.values())
        if total == 0:
            return {a: 1.0 / len(report) for a in report}
        return {a: round(acc / total, 3) for a, acc in accuracies.items()}
