# ============================================================
# FIL: backend/predictive/orchestrator.py
#
# DIRIGENTEN: Kopplar ihop ALLA prediktiva moduler till
# en enda pipeline som körs automatiskt.
#
# EventDetector → CausalChainEngine → EventTreeEngine
#              → LeadLagDetector → NarrativeTracker
#                      ↓
#              → Portföljrekommendation
#
# Anropas dagligen av main.py scheduling
# ============================================================

import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import asdict

from .event_detector import EventDetector
from .causal_engine import CausalChainEngine
from .event_tree import EventTreeEngine
from .lead_lag import LeadLagDetector
from .narrative_tracker import NarrativeTracker

logger = logging.getLogger(__name__)


class PredictiveOrchestrator:
    """
    Dirigerar hela prediktionssystemet.
    EN metod: run_daily_pipeline()

    Sekvens:
    1. EventDetector identifierar händelser
    2. AI analyserar händelserna
    3. CausalChainEngine bygger kedjor för CRITICAL/HIGH
    4. EventTreeEngine bygger träd för CRITICAL
    5. LeadLagDetector kollar aktiva signaler
    6. NarrativeTracker uppdaterar narrativ
    7. Allt aggregeras till portföljrekommendationer
    """

    def __init__(self):
        self.event_detector = EventDetector()
        self.causal_engine = CausalChainEngine()
        self.event_tree = EventTreeEngine()
        self.lead_lag = LeadLagDetector()
        self.narrative = NarrativeTracker()

    def run_daily_pipeline(
        self,
        news_summary: str,
        agent_outputs: Dict[str, str],
        agent_scores: Dict[str, Dict[str, float]],
        previous_agent_scores: Dict[str, Dict[str, float]],
        recent_prices: Dict[str, float],
        daily_returns: Dict[str, float],
        historical_std: Dict[str, float],
        returns_df=None,
    ) -> Dict:
        """
        HUVUDMETOD: Körs dagligen.
        Returnerar allt som behövs + prompts för AI-anrop.
        """
        pipeline_start = datetime.now()
        results = {"timestamp": pipeline_start.isoformat(), "steps": []}

        # ---- STEG 1: Detektera händelser ----
        existing_chains = [c.trigger_event for c in self.causal_engine.active_chains]

        detection = self.event_detector.run_full_detection(
            news_summary=news_summary,
            agent_outputs=agent_outputs,
            recent_prices=recent_prices,
            daily_returns=daily_returns,
            historical_std=historical_std,
            current_agent_scores=agent_scores,
            previous_agent_scores=previous_agent_scores,
            existing_chain_titles=existing_chains
        )

        results["step_1_detection"] = {
            "events_detected": detection["total_detected"],
            "critical": detection["critical_count"],
            "high": detection["high_count"],
            "ai_prompt": detection["ai_detection_prompt"],
            "needs_ai_response": True,
            "chains_to_build": detection["trigger_causal_chains"],
            "trees_to_build": detection["trigger_event_trees"],
            "auto_detected": detection["auto_detected_events"][:5],
        }
        results["steps"].append("detection_complete")

        # ---- STEG 3: Lead-lag-signaler ----
        lead_lag_signals = []
        if returns_df is not None:
            try:
                lead_lag_signals = self.lead_lag.get_actionable_signals(returns_df)
            except Exception as e:
                logger.error(f"Lead-lag error: {e}")

        results["step_3_lead_lag"] = {
            "signals": lead_lag_signals,
            "actionable_count": len(lead_lag_signals)
        }
        results["steps"].append("lead_lag_complete")

        # ---- STEG 4: Narrativ-uppdatering ----
        narrative_prompt = self.narrative.build_narrative_prompt(news_summary[:1000])
        narrative_signals = self.narrative.get_trading_signals()
        narrative_dashboard = self.narrative.get_dashboard()

        results["step_4_narratives"] = {
            "update_prompt": narrative_prompt,
            "needs_ai_response": True,
            "current_signals": narrative_signals,
            "dashboard": narrative_dashboard
        }
        results["steps"].append("narratives_complete")

        # ---- STEG 5: Aggregera portföljimplikationer ----
        chain_implications = self.causal_engine.get_portfolio_implications()
        convex_positions = self.event_tree.get_all_convex_positions()

        expired = self.causal_engine.expire_old_chains()
        if expired > 0:
            logger.info(f"Expired {expired} old causal chains")

        results["step_5_aggregation"] = {
            "causal_implications": chain_implications,
            "convex_positions": convex_positions[:5],
            "lead_lag_signals": lead_lag_signals[:5],
            "narrative_signals": narrative_signals[:3],
            "expired_chains": expired
        }
        results["steps"].append("aggregation_complete")

        # ---- STEG 6: Generera portföljrekommendation ----
        portfolio_rec = self._generate_portfolio_recommendation(
            chain_implications, convex_positions, lead_lag_signals, narrative_signals
        )

        results["step_6_recommendation"] = portfolio_rec
        results["steps"].append("recommendation_complete")

        duration = (datetime.now() - pipeline_start).total_seconds()
        results["duration_seconds"] = round(duration, 1)
        results["status"] = "COMPLETE_NEEDS_AI" if detection["total_detected"] > 0 else "COMPLETE"

        return results

    def process_ai_detection_response(self, ai_response: Dict) -> Dict:
        """Anropas efter att AI svarat på detection-prompten."""
        new_events = self.event_detector.parse_detection_response(ai_response)

        chains_built = []
        trees_built = []

        for event in new_events:
            if event.requires_causal_chain:
                chain_prompt = self.causal_engine.build_chain_prompt(
                    event.title, event.description
                )
                chains_built.append({
                    "event_id": event.id,
                    "event_title": event.title,
                    "chain_prompt": chain_prompt,
                    "needs_ai_response": True
                })

            if event.requires_event_tree:
                tree_prompt = self.event_tree.build_tree_prompt(
                    event.title, event.description
                )
                trees_built.append({
                    "event_id": event.id,
                    "event_title": event.title,
                    "tree_prompt": tree_prompt,
                    "needs_ai_response": True
                })

        return {
            "new_events": len(new_events),
            "events": [asdict(e) for e in new_events[:5]],
            "chains_to_build": chains_built,
            "trees_to_build": trees_built,
        }

    def process_ai_chain_response(self, event_id: str, ai_response: Dict):
        """Parsa AI-svar för kausal kedja och koppla till händelse"""
        event_title = ""
        for e in self.event_detector.detected_events:
            if e.id == event_id:
                event_title = e.title
                break

        chain = self.causal_engine.parse_chain_response(ai_response, event_title)
        self.event_detector.mark_processed(event_id, chain_id=chain.id)
        return chain

    def process_ai_tree_response(self, event_id: str, ai_response: Dict):
        """Parsa AI-svar för event tree och koppla till händelse"""
        tree = self.event_tree.parse_tree_response(ai_response)
        self.event_detector.mark_processed(event_id, tree_id=tree.id)
        return tree

    def process_ai_narrative_response(self, ai_response: Dict):
        """Parsa AI-svar för narrativ-uppdatering"""
        self.narrative.update_narratives(ai_response)

    def _generate_portfolio_recommendation(
        self,
        chain_impl: Dict,
        convex: List[Dict],
        lead_lag: List[Dict],
        narrative: List[Dict]
    ) -> Dict:
        """
        Aggregerar alla prediktiva signaler till portföljrekommendation.
        Vikter: kausal 35%, konvexitet 30%, lead-lag 20%, narrativ 15%
        """
        asset_signals = {}

        # Från kausala kedjor
        for asset, data in chain_impl.get("assets", {}).items():
            if asset not in asset_signals:
                asset_signals[asset] = {"causal": 0, "convex": 0, "lead_lag": 0, "narrative": 0}
            asset_signals[asset]["causal"] = data.get("total_expected_impact_pct", 0)

        # Från konvexa positioner
        for pos in convex:
            asset = pos.get("asset", "")
            if asset not in asset_signals:
                asset_signals[asset] = {"causal": 0, "convex": 0, "lead_lag": 0, "narrative": 0}
            direction = 1 if pos.get("direction") == "LONG" else -1
            asset_signals[asset]["convex"] = pos.get("expected_impact", 0) * direction

        # Från lead-lag
        for sig in lead_lag:
            asset = sig.get("follower", "")
            if asset not in asset_signals:
                asset_signals[asset] = {"causal": 0, "convex": 0, "lead_lag": 0, "narrative": 0}
            direction = 1 if sig.get("action") == "KÖP" else -1
            asset_signals[asset]["lead_lag"] = sig.get("confidence", 0) * 10 * direction

        # Från narrativ
        for sig in narrative:
            for asset in sig.get("assets", []):
                if asset not in asset_signals:
                    asset_signals[asset] = {"causal": 0, "convex": 0, "lead_lag": 0, "narrative": 0}
                direction = 1 if sig.get("direction") in ("BULLISH", "TRENDFÖLJNING") else -1
                strength = {"STARK": 3, "MEDEL": 2, "LÅG": 1}.get(sig.get("strength", ""), 1)
                asset_signals[asset]["narrative"] = strength * direction

        SIGNAL_WEIGHTS = {"causal": 0.35, "convex": 0.30, "lead_lag": 0.20, "narrative": 0.15}

        recommendations = []
        for asset, signals in asset_signals.items():
            weighted_score = sum(
                signals[source] * weight
                for source, weight in SIGNAL_WEIGHTS.items()
            )

            if abs(weighted_score) < 0.5:
                continue

            action = "ÖKA" if weighted_score > 0 else "MINSKA"
            strength = "STARK" if abs(weighted_score) > 3 else "MEDEL" if abs(weighted_score) > 1.5 else "SVAG"

            recommendations.append({
                "asset": asset,
                "action": action,
                "weighted_score": round(weighted_score, 2),
                "strength": strength,
                "signal_breakdown": {
                    source: round(signals[source], 2)
                    for source in SIGNAL_WEIGHTS
                    if abs(signals.get(source, 0)) > 0.1
                },
                "confidence": round(min(
                    sum(1 for s in signals.values() if (s > 0) == (weighted_score > 0)) / 4,
                    1.0
                ), 2)
            })

        recommendations.sort(key=lambda x: abs(x["weighted_score"]), reverse=True)

        return {
            "recommendations": recommendations[:10],
            "signal_weights_used": SIGNAL_WEIGHTS,
            "strongest_bull": max(recommendations, key=lambda x: x["weighted_score"]) if recommendations else None,
            "strongest_bear": min(recommendations, key=lambda x: x["weighted_score"]) if recommendations else None,
        }
