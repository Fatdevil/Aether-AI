# ============================================================
# FIL: backend/daily_scheduler.py
# Daglig automatisk körning av hela systemet
#
# Körordning (08:30 varje dag):
# 1. Hämta data  2. AI-agenter  3. EventDetector
# 4. CausalChain/EventTree  5. LeadLag  6. Narrativ
# 7. ActorSimulation  8. Confidence  9. MetaStrategy
# 10. Adversarial  11. Convexity  12. Slutlig rekommendation
# ============================================================

import asyncio
from datetime import datetime, time
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class DailyScheduler:
    """
    Orchestrerar hela systemets dagliga körning.
    Designad för att köras som bakgrundsprocess i FastAPI.
    """

    def __init__(self, orchestrator, actor_sim, convexity_opt,
                 confidence_cal, meta_strategy, adversarial,
                 health_check):
        self.orchestrator = orchestrator
        self.actor_sim = actor_sim
        self.convexity = convexity_opt
        self.confidence = confidence_cal
        self.meta = meta_strategy
        self.adversarial = adversarial
        self.health = health_check
        self.last_run: Optional[datetime] = None
        self.run_count: int = 0
        self.last_result: Optional[Dict] = None

    async def run_daily(self, data_fetcher: Callable, ai_caller: Callable) -> Dict:
        """
        HUVUDMETOD: Kör hela systemet.

        data_fetcher: async function → dict med all data
        ai_caller: async function(prompt) → dict (parsed JSON)
        """
        start = datetime.now()
        log = {"start": start.isoformat(), "steps": [], "errors": []}

        try:
            # ---- STEG 1: DATA ----
            data = await data_fetcher()
            log["steps"].append({"step": "data_fetch", "status": "OK"})

            # ---- STEG 2-6: PREDICTIVE PIPELINE ----
            pipeline_result = self.orchestrator.run_daily_pipeline(
                news_summary=data.get("news", ""),
                agent_outputs=data.get("agent_outputs", {}),
                agent_scores=data.get("agent_scores", {}),
                previous_agent_scores=data.get("previous_scores", {}),
                recent_prices=data.get("prices", {}),
                daily_returns=data.get("returns", {}),
                historical_std=data.get("hist_std", {}),
                returns_df=data.get("returns_df", None),
            )

            # AI detection
            if pipeline_result.get("step_1_detection", {}).get("needs_ai_response"):
                ai_prompt = pipeline_result["step_1_detection"]["ai_prompt"]
                ai_resp = await ai_caller(ai_prompt)
                if ai_resp:
                    processed = self.orchestrator.process_ai_detection_response(ai_resp)

                    for chain_req in processed.get("chains_to_build", [])[:3]:
                        chain_resp = await ai_caller(chain_req["chain_prompt"])
                        if chain_resp:
                            self.orchestrator.process_ai_chain_response(chain_req["event_id"], chain_resp)

                    for tree_req in processed.get("trees_to_build", [])[:2]:
                        tree_resp = await ai_caller(tree_req["tree_prompt"])
                        if tree_resp:
                            self.orchestrator.process_ai_tree_response(tree_req["event_id"], tree_resp)

            log["steps"].append({"step": "predictive_pipeline", "status": "OK"})

            # ---- STEG 7: ACTOR SIMULATION (CRITICAL only) ----
            critical_events = [e for e in pipeline_result.get("step_1_detection", {}).get("chains_to_build", [])
                              if e.get("severity") == "CRITICAL"]
            if critical_events:
                for event in critical_events[:1]:
                    sim_prompt = self.actor_sim.build_simulation_prompt(event["title"])
                    sim_resp = await ai_caller(sim_prompt)
                    if sim_resp:
                        self.actor_sim.parse_simulation(sim_resp, event["title"])
                log["steps"].append({"step": "actor_simulation", "status": "OK"})

            # ---- STEG 8: CONFIDENCE (Mondays) ----
            if start.weekday() == 0:
                cal = self.confidence.compute_calibration()
                log["steps"].append({"step": "confidence_calibration", "status": "OK",
                                     "brier": cal.get("brier_score")})

            # ---- STEG 9: META-STRATEGY (1st of month) ----
            if start.day == 1:
                self.meta.update_weights()
                log["steps"].append({"step": "meta_strategy_update", "status": "OK"})

            # ---- STEG 10: ADVERSARIAL on strong recs ----
            recommendations = pipeline_result.get("step_6_recommendation", {}).get("recommendations", [])
            strong_recs = [r for r in recommendations if abs(r.get("weighted_score", 0)) > 2]

            if strong_recs:
                for rec in strong_recs[:3]:
                    challenge_prompt = self.adversarial.build_challenge_prompt(rec)
                    challenge_resp = await ai_caller(challenge_prompt)
                    if challenge_resp:
                        challenge = self.adversarial.parse_challenge(challenge_resp, rec)
                        rec["adversarial"] = {
                            "adjusted_conviction": challenge.adjusted_conviction,
                            "should_proceed": challenge.should_proceed,
                            "red_flags": challenge.red_flags,
                            "verdict": "PROCEED" if challenge.should_proceed else "BLOCKED"
                        }
                log["steps"].append({"step": "adversarial", "status": "OK"})

            # ---- STEG 12: FINAL RECOMMENDATION ----
            regime = data.get("regime", "NEUTRAL")
            meta_weights = self.meta.get_weights(regime)

            final = {
                "timestamp": datetime.now().isoformat(),
                "regime": regime,
                "meta_weights": meta_weights,
                "recommendations": [r for r in strong_recs if r.get("adversarial", {}).get("should_proceed", True)],
                "blocked": [r for r in strong_recs if not r.get("adversarial", {}).get("should_proceed", True)],
                "pipeline_summary": pipeline_result.get("step_5_aggregation", {}),
            }

            # ---- STEG 13: HEALTH CHECK ----
            health = self.health.run_checks()
            log["steps"].append({"step": "health_check", "status": "OK", "health": health.get("status")})

            self.last_run = datetime.now()
            self.run_count += 1

            log["status"] = "SUCCESS"
            log["duration_seconds"] = round((datetime.now() - start).total_seconds(), 1)
            log["final_recommendation"] = final
            self.last_result = log

            return log

        except Exception as e:
            log["status"] = "ERROR"
            log["errors"].append(str(e))
            log["duration_seconds"] = round((datetime.now() - start).total_seconds(), 1)
            logger.error(f"Daily run failed: {e}", exc_info=True)
            self.last_result = log
            return log

    def get_status(self) -> Dict:
        return {
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "last_status": self.last_result.get("status") if self.last_result else None,
            "last_duration": self.last_result.get("duration_seconds") if self.last_result else None,
            "steps_completed": len(self.last_result.get("steps", [])) if self.last_result else 0,
        }
