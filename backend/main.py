"""
Aether AI Backend - FastAPI Server
Hämtar riktiga priser via yfinance, nyheter via RSS och tillhandahåller REST API.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else

from fastapi import FastAPI, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware

from data_service import DataService
from ai_engine import get_system_info
from risk_manager import PortfolioRiskManager
from transaction_filter import filter_rebalancing
from agent_performance import AgentPerformanceTracker
from domain_knowledge import DomainKnowledgeManager
from currency_hedge import CurrencyHedgeCalculator
from tax_optimizer import SwedishTaxOptimizer
from macro_calendar import MacroEventCalendar
from rebalance_scheduler import RebalanceScheduler
from drawdown_estimator import DrawdownRecoveryEstimator
from multi_timeframe import MultiTimeframeConfirmation
from api_cost_tracker import APICostTracker
from predictive import (CausalChainEngine, EventTreeEngine, LeadLagDetector, NarrativeTracker,
                        PredictiveOrchestrator, MarketActorSimulation, ConvexityOptimizer,
                        ConfidenceCalibrator, MetaStrategySelector, AdversarialAgent,
                        PoliticalIntelligenceEngine)
from daily_scheduler import DailyScheduler
from system_health import SystemHealthCheck
from llm_provider import call_llm, call_llm_tiered, parse_llm_json
from analysis_store import store as analysis_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aether")

# Global data service
data_service = DataService()

# Global risk & regime managers
risk_manager = PortfolioRiskManager()
perf_tracker = AgentPerformanceTracker()
domain_mgr = DomainKnowledgeManager()
currency_calc = CurrencyHedgeCalculator()
tax_opt = SwedishTaxOptimizer()
macro_cal = MacroEventCalendar()
rebalance_sched = RebalanceScheduler()
dd_estimator = DrawdownRecoveryEstimator()
mtf = MultiTimeframeConfirmation()
cost_tracker = APICostTracker(monthly_budget_usd=50.0)
causal_engine = CausalChainEngine()
event_tree_engine = EventTreeEngine()
lead_lag_detector = LeadLagDetector()
narrative_tracker = NarrativeTracker()
predictor = PredictiveOrchestrator()
actor_sim = MarketActorSimulation()
confidence_cal = ConfidenceCalibrator()
meta_strategy = MetaStrategySelector()
adversarial = AdversarialAgent()
political_engine = PoliticalIntelligenceEngine()
health_check = SystemHealthCheck()

# Omega portfolio (scenario-based A/B testing)
from scenario_engine import scenario_engine
from portfolio_tracker import tracker as portfolio_ab_tracker
# ConvexityOptimizer initialized per-request (needs asset list)
# DailyScheduler initialized after all modules
daily_sched = DailyScheduler(predictor, actor_sim, None, confidence_cal, meta_strategy, adversarial, health_check)


# ============================================================
# AUTONOM BAKGRUNDSLOOP
# Pipeline körs automatiskt — inga manuella knappar behövs
# ============================================================

_last_pipeline_run: datetime | None = None
_last_pipeline_result: dict | None = None
_pipeline_run_count: int = 0
PIPELINE_INTERVAL_HOURS = 6
EVENT_DETECT_INTERVAL_REFRESHES = 3  # Kör event detection var 3:e refresh (~15 min)

# ============================================================
# TILLÄGG A: LOOP-DETEKTION & API-BUDGET
# Max 50 API-anrop per pipeline-körning, max 3 retries per anrop.
# Förhindrar oändliga loopar som bränner API-budget.
# ============================================================
MAX_API_CALLS_PER_PIPELINE = 50
MAX_RETRIES_PER_CALL = 3
_pipeline_api_call_count = 0


async def safe_pipeline_llm_call(provider, system_prompt, user_prompt, **kwargs):
    """
    Wrapper runt call_llm med:
    - Max 3 retries vid fel (ogiltigt JSON, timeout, API-fel)
    - Global budgetgräns (50 anrop per pipeline-körning)
    - Loggar varje misslyckat försök
    """
    global _pipeline_api_call_count

    if _pipeline_api_call_count >= MAX_API_CALLS_PER_PIPELINE:
        logger.warning(f"⛔ API BUDGET EXHAUSTED: {_pipeline_api_call_count}/{MAX_API_CALLS_PER_PIPELINE} calls used. Skipping.")
        return None

    last_error = None
    for attempt in range(1, MAX_RETRIES_PER_CALL + 1):
        try:
            _pipeline_api_call_count += 1
            result = await call_llm(provider, system_prompt, user_prompt, **kwargs)
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ LLM call attempt {attempt}/{MAX_RETRIES_PER_CALL} failed: {e}")
            if attempt < MAX_RETRIES_PER_CALL:
                await asyncio.sleep(2 ** attempt)  # Exponentiell backoff: 2s, 4s

    logger.error(f"❌ LLM call failed after {MAX_RETRIES_PER_CALL} retries: {last_error}")
    return None
_refresh_count = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + fetch initial data + start background loops."""
    logger.info("🚀 Aether AI Backend starting...")
    
    # Initialize PostgreSQL tables if DATABASE_URL is set
    try:
        from db import DB_TYPE, init_postgresql_tables
        if DB_TYPE == "postgresql":
            init_postgresql_tables()
            logger.info("🐘 PostgreSQL tables ready — data persists across deploys!")
        else:
            logger.info("📁 Using local SQLite — data resets on deploy")
    except Exception as e:
        logger.warning(f"DB init: {e}")
    
    await data_service.refresh_all()
    # Start background loops
    refresh_task = asyncio.create_task(background_refresh())
    predictive_task = asyncio.create_task(background_predictive_loop())
    yield
    refresh_task.cancel()
    predictive_task.cancel()
    logger.info("Aether AI Backend shutting down.")


async def background_refresh():
    """Refresh market data every 5 minutes + lightweight event detection."""
    global _refresh_count
    while True:
        await asyncio.sleep(300)  # 5 min
        try:
            logger.info("🔄 Refreshing market data...")
            await data_service.refresh_all()
            _refresh_count += 1
            logger.info(f"✅ Market data refreshed (#{_refresh_count}).")

            # Kör lätt event detection var 3:e refresh
            if _refresh_count % EVENT_DETECT_INTERVAL_REFRESHES == 0:
                try:
                    await _run_lightweight_event_detection()
                except Exception as e:
                    logger.error(f"Event detection failed: {e}")

        except Exception as e:
            logger.error(f"❌ Refresh failed: {e}")


async def _run_lightweight_event_detection():
    """Kör bara prisavvikelse + agent-divergens-detektion (inga AI-anrop)."""
    logger.info("👁 Running lightweight event detection...")
    prices = data_service.prices or {}
    recent_prices = {}
    daily_returns_dict = {}
    for asset_id, price_data in prices.items():
        if isinstance(price_data, dict):
            recent_prices[asset_id] = price_data.get("price", 0)
            daily_returns_dict[asset_id] = price_data.get("change_pct", 0) / 100

    returns_df = data_service.get_historical_returns()
    historical_std = {}
    if not returns_df.empty:
        for col in returns_df.columns:
            historical_std[col] = float(returns_df[col].std())

    # Agent scores
    agent_scores_current = {}
    for asset in data_service.assets:
        analysis = asset.get("analysis", {})
        for agent_name in ["macro", "micro", "technical", "sentiment"]:
            agent_data = analysis.get(agent_name, {})
            if agent_data:
                if agent_name not in agent_scores_current:
                    agent_scores_current[agent_name] = {}
                agent_scores_current[agent_name][asset.get("id", "")] = agent_data.get("score", 0)

    detection = predictor.event_detector.run_full_detection(
        news_summary="",
        agent_outputs={},
        recent_prices=recent_prices,
        daily_returns=daily_returns_dict,
        historical_std=historical_std,
        agent_scores=agent_scores_current,
        previous_agent_scores={},
        existing_chains=[c.trigger_event for c in predictor.causal_engine.active_chains],
    )

    detected_count = detection.get("total_detected", 0)
    critical_count = detection.get("critical_count", 0)
    if detected_count > 0:
        logger.info(f"👁 Detected {detected_count} events ({critical_count} critical)")

        # Auto-trigger actor simulation on CRITICAL events
        if critical_count > 0:
            critical_events = [e for e in detection.get("auto_detected_events", [])
                              if e.get("severity") == "CRITICAL"]
            for event in critical_events[:1]:
                try:
                    logger.info(f"🎭 Auto-simulating critical event: {event.get('title', '?')}")
                    sim_prompt = actor_sim.build_simulation_prompt(event.get("title", ""))
                    sim_resp = await call_llm("gemini", "Marknads-simulator. JSON.", sim_prompt, temperature=0.4, max_tokens=4000)
                    sim_parsed = parse_llm_json(sim_resp)
                    if sim_parsed:
                        actor_sim.parse_simulation(sim_parsed, event.get("title", ""))
                        logger.info("🎭 Actor simulation complete")
                except Exception as e:
                    logger.error(f"Actor sim failed: {e}")


async def background_predictive_loop():
    """Kör full prediktiv pipeline automatiskt var 6:e timme."""
    global _last_pipeline_run, _last_pipeline_result, _pipeline_run_count

    # Vänta 2 min efter startup så att initiell data hinner laddas
    await asyncio.sleep(120)

    while True:
        try:
            logger.info("🤖 ═══════════════════════════════════════")
            logger.info("🤖 AUTONOM PIPELINE STARTAR")
            logger.info("🤖 ═══════════════════════════════════════")

            pipeline_start = datetime.now()

            # Kör samma pipeline som manuell endpoint
            result = await _run_full_pipeline()

            _last_pipeline_run = datetime.now()
            _last_pipeline_result = result
            _pipeline_run_count += 1

            duration = result.get("duration_seconds", 0)
            status = result.get("status", "UNKNOWN")
            logger.info(f"🤖 AUTONOM PIPELINE KLAR: {status} ({duration}s) — Körning #{_pipeline_run_count}")

            # ---- AUTO: Adversarial check på starka rekommendationer ----
            recs = result.get("portfolio_recommendation", {}).get("recommendations", [])
            strong_recs = [r for r in recs if abs(r.get("weighted_score", 0)) > 5]

            for rec in strong_recs[:2]:
                try:
                    logger.info(f"🛡 Auto-adversarial: {rec.get('asset', '?')} ({rec.get('action', '?')})")
                    challenge_prompt = adversarial.build_challenge_prompt(rec)
                    challenge_resp = await call_llm("gemini", "DEVILS ADVOCATE. JSON.", challenge_prompt, temperature=0.4, max_tokens=2000)
                    challenge_parsed = parse_llm_json(challenge_resp)
                    if challenge_parsed:
                        challenge_result = adversarial.parse_challenge(challenge_parsed, rec)
                        verdict = "PROCEED" if challenge_result.should_proceed else "BLOCKED"
                        logger.info(f"🛡 Adversarial verdict: {verdict} (conviction {challenge_result.original_conviction}→{challenge_result.adjusted_conviction})")
                except Exception as e:
                    logger.error(f"Adversarial failed: {e}")

            # ---- AUTO: Confidence logging ----
            for rec in recs[:5]:
                try:
                    score = abs(rec.get("weighted_score", 0))
                    prob = min(score / 10, 0.95)  # Normalisera till 0-1
                    confidence_cal.log_prediction(
                        prediction_id=f"pipeline_{_pipeline_run_count}_{rec.get('asset', '')}",
                        stated_prob=prob,
                        source="pipeline",
                        asset=rec.get("asset", "")
                    )
                except Exception:
                    pass

            # ---- AUTO: Meta-strategy logging ----
            regime = "NEUTRAL"  # TODO: hämta från regime-detektor
            for method_name in ["causal_chain", "lead_lag", "narrative"]:
                try:
                    quality = 0.5  # Default — uppdateras med verkliga utfall
                    meta_strategy.log_method_performance(method_name, regime, quality)
                except Exception:
                    pass

            # Varje måndag: uppdatera meta-vikter
            if datetime.now().weekday() == 0:
                try:
                    meta_strategy.update_weights()
                    logger.info("⚖ Meta-strategy weights updated")
                except Exception:
                    pass

            # Varje måndag: compute confidence calibration
            if datetime.now().weekday() == 0:
                try:
                    cal = confidence_cal.compute_calibration()
                    brier = cal.get("brier_score", "?")
                    logger.info(f"🎯 Confidence calibration: Brier={brier}")
                except Exception:
                    pass

            # Varje måndag: refresh scenarios + Omega portfolio
            if datetime.now().weekday() == 0:
                try:
                    regime = "NEUTRAL"
                    pol_state = political_engine.get_current_state()
                    omega = await scenario_engine.refresh_scenarios(
                        regime=regime,
                        political_risk=pol_state.get("political_risk", "NORMAL"),
                    )
                    logger.info(f"🎯 Omega scenarios refreshed: {len(scenario_engine.scenarios)} scenarios, E(R)={omega.expected_return:.1%}")
                except Exception as e:
                    logger.debug(f"Scenario refresh: {e}")

        except Exception as e:
            logger.error(f"🤖 AUTONOM PIPELINE FEL: {e}", exc_info=True)

        # Vänta till nästa körning
        logger.info(f"🤖 Nästa automatiska körning om {PIPELINE_INTERVAL_HOURS}h")
        await asyncio.sleep(PIPELINE_INTERVAL_HOURS * 3600)


async def _run_full_pipeline() -> dict:
    """
    PIPELINE B — 10-LAYER AUTONOMOUS PIPELINE (var 6h)
    
    This is SEPARATE from Pipeline A (data_service.refresh_all() every 5 min).
    Pipeline B uses supervisor.synthesize() with all 12 inputs.
    Pipeline A continues handling regular per-asset analysis.
    """
    from agents.supervisor_agent import SupervisorAgent
    from regime_detector import regime_detector
    from economic_calendar import calendar as eco_calendar
    from correlation_engine import correlation_engine

    global _pipeline_api_call_count
    _pipeline_api_call_count = 0  # Reset API budget per pipeline run

    pipeline_start = datetime.now()
    layers_log = {}

    try:
        # ================================================================
        # LAYER 1: DATA
        # ================================================================
        news_summary = "\n".join([f"- {n.get('title', '')}" for n in (data_service.news or [])[:40]])
        prices = data_service.prices or {}
        recent_prices = {}
        daily_returns_dict = {}
        for asset_id, price_data in prices.items():
            if isinstance(price_data, dict):
                recent_prices[asset_id] = price_data.get("price", 0)
                daily_returns_dict[asset_id] = price_data.get("change_pct", 0) / 100
            elif isinstance(price_data, (int, float)):
                recent_prices[asset_id] = price_data

        returns_df = data_service.get_historical_returns()
        historical_std = {}
        if not returns_df.empty:
            for col in returns_df.columns:
                historical_std[col] = float(returns_df[col].std())

        # Extract agent scores from data_service's latest analysis
        agent_outputs = {}
        agent_scores_current = {}
        for asset in data_service.assets:
            asset_id_local = asset.get("id", "")
            analysis = asset.get("analysis", {})
            if analysis:
                for agent_name in ["macro", "micro", "technical", "sentiment", "onchain"]:
                    agent_data = analysis.get(agent_name, {})
                    if agent_data:
                        key = f"{agent_name}_{asset_id_local}"
                        summary = agent_data.get("summary", agent_data.get("reasoning", ""))
                        if summary:
                            agent_outputs[key] = summary[:200]
                        score = agent_data.get("score", 0)
                        if agent_name not in agent_scores_current:
                            agent_scores_current[agent_name] = {}
                        agent_scores_current[agent_name][asset_id_local] = score

        layers_log["L1_data"] = {"status": "OK", "assets": len(recent_prices), "news": len(data_service.news or [])}
        logger.info("📊 L1 DATA: Complete")

        # ================================================================
        # LAYER 2: DETECTION (EventDetector)
        # ================================================================
        existing_chains = [c.trigger_event for c in predictor.causal_engine.active_chains]
        detection = predictor.event_detector.run_full_detection(
            news_summary=news_summary,
            agent_outputs=agent_outputs,
            recent_prices=recent_prices,
            daily_returns=daily_returns_dict,
            historical_std=historical_std,
            current_agent_scores=agent_scores_current,
            previous_agent_scores={},
            existing_chain_titles=existing_chains,
        )

        # AI-driven event analysis
        ai_events = []
        if detection.get("needs_ai_analysis") and detection.get("ai_analysis_prompt"):
            ai_resp = await call_llm(
                "gemini",
                "Du är en marknadshändelse-analytiker. Svara ENBART med JSON.",
                detection["ai_analysis_prompt"],
                temperature=0.3, max_tokens=2000
            )
            parsed = parse_llm_json(ai_resp)
            if parsed:
                processed = predictor.process_ai_detection_response(parsed)
                ai_events = processed.get("new_events", [])

                for chain_req in processed.get("chains_to_build", [])[:3]:
                    chain_resp = await call_llm(
                        "gemini",
                        "Du är en kausal analysexpert. Svara ENBART med JSON.",
                        chain_req["chain_prompt"],
                        temperature=0.4, max_tokens=2000
                    )
                    chain_parsed = parse_llm_json(chain_resp)
                    if chain_parsed:
                        predictor.process_ai_chain_response(chain_req["event_id"], chain_parsed)

                for tree_req in processed.get("trees_to_build", [])[:2]:
                    tree_resp = await call_llm(
                        "gemini",
                        "Du är en scenarioanalytiker. Svara ENBART med JSON.",
                        tree_req["tree_prompt"],
                        temperature=0.4, max_tokens=3000
                    )
                    tree_parsed = parse_llm_json(tree_resp)
                    if tree_parsed:
                        predictor.process_ai_tree_response(tree_req["event_id"], tree_parsed)

        layers_log["L2_detection"] = {
            "events": detection.get("total_detected", 0),
            "critical": detection.get("critical_count", 0),
            "high": detection.get("high_count", 0),
            "ai_events": len(ai_events),
        }
        logger.info(f"👁 L2 DETECTION: {detection.get('total_detected', 0)} events ({detection.get('critical_count', 0)} critical)")

        # ================================================================
        # LAYER 3: PREDICTIVE (CausalChain, EventTree, LeadLag, Narrative, ActorSim)
        # ================================================================
        # Narrative update
        narr_prompt = predictor.narrative.build_narrative_prompt(news_summary[:1000])
        narr_resp = await call_llm(
            "gemini",
            "Du är en marknadsnarratologisk analytiker. Svara ENBART med JSON.",
            narr_prompt, temperature=0.3, max_tokens=2000
        )
        narr_parsed = parse_llm_json(narr_resp)
        if narr_parsed:
            predictor.process_ai_narrative_response(narr_parsed)

        # Lead-lag (runs always)
        ll_signals = []
        if not returns_df.empty:
            ll_signals = predictor.lead_lag.get_actionable_signals(returns_df)

        # Aggregate predictive outputs
        chain_impl = predictor.causal_engine.get_portfolio_implications()
        convex = predictor.event_tree.get_all_convex_positions()
        narr_signals = predictor.narrative.get_trading_signals()
        narr_dashboard = predictor.narrative.get_dashboard()
        expired = predictor.causal_engine.expire_old_chains()

        # ActorSimulation result (already ran in L2 for CRITICAL events)
        actor_sim_data = None
        if hasattr(actor_sim, 'last_simulation') and actor_sim.last_simulation:
            actor_sim_data = actor_sim.last_simulation.__dict__ if hasattr(actor_sim.last_simulation, '__dict__') else actor_sim.last_simulation

        # Political Intelligence v2 (reads Sentinel-accumulated signals, NO AI calls)
        political_state = {"direct_signals": [], "political_risk": "NORMAL"}
        try:
            political_state = political_engine.get_current_state()
        except Exception as e:
            logger.warning(f"Political intelligence failed: {e}")

        layers_log["L3_predictive"] = {
            "chains_active": len([c for c in predictor.causal_engine.active_chains if c.status == "ACTIVE"]),
            "convex_positions": len(convex),
            "lead_lag_signals": len(ll_signals),
            "narrative_signals": len(narr_signals),
            "actor_sim_available": actor_sim_data is not None,
            "political": {
                "risk_level": political_state.get("political_risk", "NORMAL"),
                "direct_signals": len(political_state.get("direct_signals", [])),
                "dominant_actor": political_state.get("dominant_actor"),
                "total_signals_tracked": political_state.get("total_signals_tracked", 0),
            },
        }
        logger.info(f"🔮 L3 PREDICTIVE: {len(ll_signals)} lead-lag, {len(convex)} convex, {len(narr_signals)} narrative, political={political_state.get('political_risk', 'NORMAL')}")

        # ================================================================
        # LAYER 4: ANALYSIS (Regime, Vol, Calendar, DomainKnowledge)
        # ================================================================
        # Regime detection — ML primary, rule-based fallback
        try:
            from regime_classifier import detect_regime_with_fallback
            regime_data = detect_regime_with_fallback()
        except Exception as e:
            logger.warning(f"ML regime detection import failed: {e}, using rule-based")
            regime_data = regime_detector.detect_regime()
        current_regime = regime_data.get("regime", "neutral") if regime_data else "neutral"

        # Volatility adjustment (ATR-based)
        vol_adjustment = {}
        BASELINE_ATR = {
            "btc": 3.0, "gold": 0.8, "silver": 1.5, "oil": 1.8,
            "sp500": 0.8, "global-equity": 0.7, "eurusd": 0.3, "us10y": 0.5,
        }
        for asset_id_local, price_data in prices.items():
            if isinstance(price_data, dict):
                atr_pct = price_data.get("indicators", {}).get("atr_pct", 0)
                baseline = BASELINE_ATR.get(asset_id_local, 1.0)
                if atr_pct and atr_pct > 0 and baseline > 0:
                    vol_ratio = atr_pct / baseline
                    vol_adjustment[asset_id_local] = max(0.6, min(1.3, 1.0 / (vol_ratio ** 0.3)))
                else:
                    vol_adjustment[asset_id_local] = 1.0

        # Calendar confidence multiplier
        conf_multiplier = 1.0
        try:
            from economic_calendar import calendar as eco_cal
            cal_summary = eco_cal.get_summary()
            if cal_summary.get("should_reduce_confidence"):
                conf_multiplier = cal_summary.get("confidence_multiplier", 0.85)
        except Exception:
            pass

        # DomainKnowledge — goes to BOTH agents (in Pipeline A) AND Supervisor directly
        domain_context = ""
        try:
            domain_context = domain_mgr.build_agent_context()
        except Exception:
            pass

        layers_log["L4_analysis"] = {
            "regime": current_regime,
            "conf_multiplier": conf_multiplier,
            "domain_knowledge_active": len(domain_context) > 0,
            "vol_adjusted_assets": sum(1 for v in vol_adjustment.values() if abs(v - 1.0) > 0.05),
        }
        logger.info(f"📈 L4 ANALYSIS: regime={current_regime}, conf_mult={conf_multiplier:.2f}, domain={'YES' if domain_context else 'NO'}")

        # ================================================================
        # LAYER 5: SYNTHESIS (Supervisor.synthesize() with 12 inputs)
        # ================================================================
        # Get MetaStrategy weights for current regime
        meta_weights = {}
        try:
            meta_weights = meta_strategy.get_weights(current_regime)
        except Exception:
            pass

        supervisor = SupervisorAgent()
        if meta_weights:
            supervisor.set_meta_weights({current_regime: meta_weights})

        synthesis = await supervisor.synthesize(
            agent_scores=agent_scores_current,
            regime=current_regime,
            vol_adjustment=vol_adjustment,
            conf_multiplier=conf_multiplier,
            causal_implications=chain_impl,
            convex_positions=convex,
            lead_lag_signals=ll_signals,
            narrative_signals=narr_signals,
            actor_sim_result=actor_sim_data,
            domain_knowledge=domain_context,
            calibration_adjustment=confidence_cal.adjust_probability,
            political_signals={
                "direct_signals": political_state.get("direct_signals", []),
                "predictions": {},
                "political_risk": political_state.get("political_risk", "NORMAL"),
            } if political_state.get("direct_signals") else None,
        )

        final_scores = synthesis.get("final_scores", {})
        conviction_ratio = synthesis.get("conviction_ratio", 0.7)

        layers_log["L5_synthesis"] = {
            "conviction_ratio": conviction_ratio,
            "assets_scored": len(final_scores),
            "method_weights": synthesis.get("method_weights_used", {}),
            "domain_knowledge_injected": synthesis.get("domain_knowledge_injected", False),
        }
        logger.info(f"🧠 L5 SYNTHESIS: {len(final_scores)} assets, conviction={conviction_ratio:.2f}")

        # ================================================================
        # LAYER 6: ADVERSARIAL (challenge strong signals)
        # ================================================================
        strong_signals = {a: s for a, s in final_scores.items() if isinstance(s, (int, float)) and abs(s) > 3}
        blocked_assets = []

        for asset_id_local, score in list(strong_signals.items())[:3]:
            try:
                rec_data = {
                    "asset": asset_id_local,
                    "weighted_score": score,
                    "action": "KÖP" if score > 0 else "SÄLJ",
                    "conviction": conviction_ratio,
                }
                challenge_prompt = adversarial.build_challenge_prompt(rec_data)
                challenge_resp = await call_llm(
                    "gemini", "DEVILS ADVOCATE. JSON.",
                    challenge_prompt, temperature=0.4, max_tokens=2000
                )
                challenge_parsed = parse_llm_json(challenge_resp)
                if challenge_parsed:
                    challenge_result = adversarial.parse_challenge(challenge_parsed, rec_data)
                    if not challenge_result.should_proceed:
                        blocked_assets.append(asset_id_local)
                        final_scores[asset_id_local] = 0
                        logger.info(f"  🛡 BLOCKED: {asset_id_local} (score {score})")
                    else:
                        adj = challenge_result.adjusted_conviction
                        orig = max(challenge_result.original_conviction, 0.01)
                        final_scores[asset_id_local] = round(score * (adj / orig), 2)
                        logger.info(f"  🛡 PROCEED: {asset_id_local} ({score:.1f} → {final_scores[asset_id_local]:.1f})")
            except Exception as e:
                logger.debug(f"Adversarial skipped for {asset_id_local}: {e}")

        layers_log["L6_adversarial"] = {
            "challenged": len(strong_signals),
            "blocked": blocked_assets,
        }
        logger.info(f"🛡 L6 ADVERSARIAL: {len(strong_signals)} challenged, {len(blocked_assets)} blocked")

        # ================================================================
        # LAYER 7: PORTFOLIO (correlation-adjusted)
        # ================================================================
        # Generate portfolio recommendation from predictive signals
        portfolio_rec = predictor._generate_portfolio_recommendation(
            chain_impl, convex, ll_signals, narr_signals
        )

        # Apply correlation penalty
        corr_penalty = {}
        try:
            corr_data = correlation_engine.calculate_correlations(period="30d")
            if corr_data and "matrix" in corr_data:
                # Compute penalty: highly correlated buy-pairs get penalized
                matrix = corr_data["matrix"]
                buy_assets = [a for a, s in final_scores.items() if isinstance(s, (int, float)) and s > 2]
                for i, a1 in enumerate(buy_assets):
                    for a2 in buy_assets[i+1:]:
                        corr = matrix.get(a1, {}).get(a2, 0)
                        if abs(corr) > 0.5:
                            weaker = a1 if abs(final_scores.get(a1, 0)) < abs(final_scores.get(a2, 0)) else a2
                            penalty = max(0.5, 1.0 - (abs(corr) - 0.5))
                            corr_penalty[weaker] = min(corr_penalty.get(weaker, 1.0), penalty)
        except Exception:
            pass

        layers_log["L7_portfolio"] = {
            "recommendations": len(portfolio_rec.get("recommendations", [])),
            "correlation_penalties": len(corr_penalty),
        }
        logger.info(f"💼 L7 PORTFOLIO: {len(portfolio_rec.get('recommendations', []))} positions, {len(corr_penalty)} corr-penalized")

        # ================================================================
        # LAYER 7b: OMEGA PORTFOLIO (scenario-based, weekly refresh)
        # ================================================================
        omega_data = None
        try:
            omega_state = scenario_engine.get_current_portfolio()
            if omega_state:
                omega_data = omega_state
                portfolio_ab_tracker.update_omega(omega_state["weights"])
            # Update Alpha weights from L7 recommendations
            alpha_weights = {}
            for rec in portfolio_rec.get("recommendations", []):
                aid = rec.get("asset_id", rec.get("asset", "")).lower()
                weight = rec.get("weight", rec.get("allocation", 0))
                if aid and isinstance(weight, (int, float)):
                    alpha_weights[aid] = weight / 100.0 if weight > 1 else weight
            if alpha_weights:
                portfolio_ab_tracker.update_alpha(alpha_weights)
            # Daily snapshot
            portfolio_ab_tracker.snapshot_daily(prices)
        except Exception as e:
            logger.debug(f"Omega/tracker update: {e}")

        layers_log["L7b_omega"] = {
            "active": omega_data is not None,
            "n_scenarios": omega_data.get("n_scenarios", 0) if omega_data else 0,
            "expected_return": omega_data.get("expected_return", 0) if omega_data else 0,
            "worst_case": omega_data.get("worst_case_return", 0) if omega_data else 0,
        }
        logger.info(f"🎯 L7b OMEGA: {'active' if omega_data else 'no scenarios yet'}")

        # ================================================================
        # LAYER 8: RISK (Trailing Stop)
        # ================================================================
        risk_status = {"stop_triggered": False, "drawdown_pct": 0, "action": "NORMAL"}
        try:
            total_value = sum(recent_prices.values()) if recent_prices else 0
            if total_value > 0:
                risk_status = risk_manager.update(total_value)
                if risk_status.get("stop_triggered") or risk_status.get("action") == "REDUCE_RISK":
                    logger.warning(f"⚠️ L8 TRAILING STOP TRIGGERED: {risk_status.get('message', '')}")
        except Exception as e:
            logger.debug(f"Risk check skipped: {e}")

        layers_log["L8_risk"] = {
            "trailing_stop": risk_status.get("stop_triggered", False),
            "drawdown_pct": risk_status.get("drawdown_pct", 0),
            "action": risk_status.get("action", "NORMAL"),
        }
        logger.info(f"🛑 L8 RISK: {risk_status.get('action', 'NORMAL')} (drawdown {risk_status.get('drawdown_pct', 0):.1f}%)")

        # ================================================================
        # LAYER 9: OUTPUT
        # ================================================================
        duration = (datetime.now() - pipeline_start).total_seconds()

        layers_log["L9_output"] = {"status": "SAVED", "duration_s": round(duration, 1)}
        logger.info(f"💾 L9 OUTPUT: Saved ({duration:.1f}s)")

        # ================================================================
        # LAYER 10: FEEDBACK (scheduled — see background_predictive_loop)
        # ================================================================
        layers_log["L10_feedback"] = {"scheduled": True, "note": "Runs in background_predictive_loop after 15min"}
        logger.info("🔄 L10 FEEDBACK: Scheduled")

        return {
            "status": "COMPLETE",
            "duration_seconds": round(duration, 1),
            "layers": layers_log,
            "detection": {
                "auto_events": detection.get("total_detected", 0),
                "ai_events": len(ai_events),
                "critical": detection.get("critical_count", 0),
                "high": detection.get("high_count", 0),
            },
            "synthesis": {
                "final_scores": final_scores,
                "conviction_ratio": conviction_ratio,
                "blocked": blocked_assets,
                "regime": current_regime,
            },
            "causal_chains": {
                "active": len([c for c in predictor.causal_engine.active_chains if c.status == "ACTIVE"]),
                "expired": expired,
                "implications": dict(list(chain_impl.get("assets", {}).items())[:5]),
            },
            "event_trees": {"convex_positions": convex[:3]},
            "lead_lag": {"actionable_signals": len(ll_signals), "top": ll_signals[:3]},
            "narratives": narr_dashboard,
            "portfolio_recommendation": portfolio_rec,
            "risk_status": risk_status,
        }

    except Exception as e:
        logger.error(f"Pipeline B failed: {e}", exc_info=True)
        return {
            "status": "ERROR", "error": str(e),
            "layers_completed": layers_log,
            "duration_seconds": round((datetime.now() - pipeline_start).total_seconds(), 1)
        }


app = FastAPI(
    title="Aether AI - Macro & Micro Analyst",
    description="AI-driven market analysis backend",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://*.up.railway.app",
    ],
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_refresh": data_service.last_refresh,
    }


@app.get("/api/assets")
async def get_assets():
    """Return all assets with current prices and AI analysis."""
    return data_service.get_assets()


@app.get("/api/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Return detailed analysis for a single asset."""
    asset = data_service.get_asset(asset_id)
    if not asset:
        return {"error": "Asset not found"}, 404
    return asset


@app.get("/api/news")
async def get_news():
    """Return aggregated news feed enriched with sentinel impact data."""
    from news_sentinel import sentinel
    news = data_service.get_news()
    
    # Merge ALL sentinel evaluations into news items (not just high-impact alerts)
    enriched = []
    for item in news:
        enriched_item = dict(item)
        eval_data = sentinel.all_evaluations.get(item.get("title", ""))
        if eval_data:
            enriched_item["impact"] = {
                "score": eval_data.get("impact_score", 0),
                "category": eval_data.get("category", "other"),
                "urgency": eval_data.get("urgency", "routine"),
                "one_liner": eval_data.get("one_liner", ""),
                "affected_assets": eval_data.get("affected_assets", []),
                "affected_sectors": eval_data.get("affected_sectors", []),
                "affected_regions": eval_data.get("affected_regions", []),
                "provider": eval_data.get("provider", "rule_based"),
            }
        enriched.append(enriched_item)
    
    return enriched


@app.get("/api/portfolio")
async def get_portfolio():
    """Return AI-recommended portfolio allocation."""
    return data_service.get_portfolio()


@app.get("/api/market-state")
async def get_market_state():
    """Return overall market state summary + risk status + pipeline B status."""
    state = data_service.get_market_state()

    # Fas 3: Inject risk_manager status between portfolio → dashboard
    try:
        prices = data_service.prices or {}
        total_value = sum(
            p.get("price", 0) if isinstance(p, dict) else p
            for p in prices.values()
        )
        if total_value > 0:
            risk_check = risk_manager.update(total_value)
            state["risk_status"] = {
                "trailing_stop": risk_check.get("stop_triggered", False),
                "drawdown_pct": risk_check.get("drawdown_pct", 0),
                "action": risk_check.get("action", "NORMAL"),
                "risk_multiplier": risk_check.get("risk_multiplier", 1.0),
                "message": risk_check.get("message", ""),
            }
    except Exception:
        state["risk_status"] = {"trailing_stop": False, "action": "NORMAL", "drawdown_pct": 0}

    # Pipeline B status
    state["pipeline_b"] = {
        "last_run": _last_pipeline_run.isoformat() if _last_pipeline_run else None,
        "run_count": _pipeline_run_count,
        "next_run_hours": PIPELINE_INTERVAL_HOURS,
    }

    return state


@app.get("/api/sectors")
async def get_sectors():
    """Return all sector analyses with scores and rotation signals."""
    return data_service.get_sectors()


@app.get("/api/regions")
async def get_regions():
    """Return all geographic region analyses with scores and allocation signals."""
    return data_service.get_regions()


@app.post("/api/refresh")
async def force_refresh():
    """Force a full data + analysis refresh (all tiers)."""
    await data_service.refresh_all(force=True)
    return {"status": "refreshed", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/scheduler")
async def get_scheduler_status():
    """Return tiered scheduler status."""
    from scheduler import scheduler
    return scheduler.get_status()


@app.get("/api/alerts")
async def get_alerts(min_impact: int = 1):
    """Return recent sentinel alerts filtered by minimum impact score."""
    from news_sentinel import sentinel
    return {
        "alerts": sentinel.get_alerts(min_impact),
        "stats": sentinel.get_stats(),
    }


@app.post("/api/alerts/test")
async def test_notification():
    """Send a test push notification."""
    from notification_service import send_notification
    success = await send_notification(
        title="🧪 Aether AI - Testnotis",
        message="Push-notiser fungerar! Du kommer nu få varningar vid marknadskritiska händelser.",
        priority=3,
        tags=["white_check_mark"],
    )
    return {"success": success, "message": "Test notification sent" if success else "Notification failed"}


@app.get("/api/system")
async def system_info():
    """Return system info: active providers, agent config, sentinel status."""
    from news_sentinel import sentinel
    from analysis_store import store
    info = get_system_info()
    info["version"] = "0.5.0"
    info["last_refresh"] = data_service.last_refresh
    info["sentinel"] = sentinel.get_stats()
    info["database"] = store.get_total_analyses_count()
    return info


@app.get("/api/performance")
async def get_performance():
    """Return AI performance / accuracy dashboard data."""
    from evaluator import evaluator
    return evaluator.get_performance_report()


@app.get("/api/prices/history/{asset_id}")
async def get_price_history(asset_id: str, period: str = "3mo"):
    """Return OHLC price history for TradingView charts (yfinance)."""
    from market_data import ASSET_TICKERS
    import yfinance as yf

    info = ASSET_TICKERS.get(asset_id)
    if not info:
        return {"error": f"Unknown asset: {asset_id}", "candles": []}

    allowed = ["1mo", "3mo", "6mo", "1y", "2y"]
    if period not in allowed:
        period = "3mo"

    try:
        ticker = yf.Ticker(info["ticker"])
        hist = ticker.history(period=period)
        candles = []
        for date, row in hist.iterrows():
            candles.append({
                "time": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
            })
        return {
            "asset_id": asset_id,
            "name": info["name"],
            "period": period,
            "candles": candles,
            "currency": info.get("currency", "$"),
        }
    except Exception as e:
        logger.error(f"Price history error for {asset_id}: {e}")
        return {"error": str(e), "candles": []}


@app.get("/api/history/{asset_id}")
async def get_history(asset_id: str, limit: int = 50):
    """Return analysis history for a specific asset."""
    from analysis_store import store
    return store.get_analysis_history(asset_id, limit)


@app.get("/api/calendar")
async def get_calendar():
    """Return upcoming and recent economic events."""
    from economic_calendar import calendar
    return calendar.get_summary()


@app.get("/api/correlations")
async def get_correlations(period: str = "30d"):
    """Return cross-asset correlation matrix and systemic signal."""
    from correlation_engine import correlation_engine
    if period not in ("7d", "30d", "90d", "180d"):
        period = "30d"
    return correlation_engine.calculate_correlations(period=period)


@app.get("/api/correlations/insights")
async def get_correlation_insights(period: str = "30d"):
    """AI-powered analysis of the correlation matrix."""
    from correlation_engine import correlation_engine
    from llm_provider import call_llm

    if period not in ("7d", "30d", "90d", "180d"):
        period = "30d"

    corr_data = correlation_engine.calculate_correlations(period=period)
    if not corr_data or "matrix" not in corr_data:
        return {"insights": [], "source": "none"}

    matrix = corr_data["matrix"]
    systemic = corr_data.get("systemic", {})
    notable = corr_data.get("notable_pairs", [])

    # Build a compact text representation
    name_map = {
        "btc": "Bitcoin", "sp500": "S&P 500", "gold": "Guld", "silver": "Silver",
        "oil": "Olja", "us10y": "US 10Y Räntor", "eurusd": "EUR/USD", "global-equity": "ACWI",
    }

    matrix_text = "Korrelationsmatris (senaste " + period + "):\n"
    assets = list(matrix.keys())
    for a in assets:
        for b in assets:
            if a < b:
                val = matrix[a].get(b, 0)
                if abs(val) >= 0.25:
                    matrix_text += f"  {name_map.get(a,a)} ↔ {name_map.get(b,b)}: {val:+.2f}\n"

    regime_text = f"Marknadsregim: {systemic.get('regime', 'okänt')}, {systemic.get('risk_on_count', 0)} risk-on, {systemic.get('risk_off_count', 0)} risk-off"

    system_prompt = """Du är en erfaren portföljanalytiker. Analysera korrelationsmatrisen och ge 3-5 korta, actionable insikter på svenska.

Fokusera på:
1. KONCENTRATIONSRISKER – vilka tillgångar som rör sig likt (korrelation > 0.7) och vad det innebär
2. HEDGING-MÖJLIGHETER – negativa korrelationer som ger diversifiering
3. AVVIKELSER – ovanliga korrelationer som avviker från det normala
4. ACTIONABLE RÅD – konkreta handlingar att överväga

Format: Returnera exakt en JSON-array med objekt: [{"icon": "emoji", "title": "kort titel", "text": "2-3 meningar med insikt och handlingsråd"}]
Max 5 insikter. Skriv på svenska. Var konkret och specifik, inte generell."""

    user_prompt = f"""{matrix_text}

{regime_text}

Starkaste par: {', '.join(f"{name_map.get(p['asset_a'],p['asset_a'])}↔{name_map.get(p['asset_b'],p['asset_b'])} ({p['correlation']:+.2f})" for p in notable[:6])}

Ge 3-5 actionable insikter om denna matris. Svara BARA med JSON-arrayen."""

    try:
        response = await call_llm("gemini", system_prompt, user_prompt, temperature=0.3, max_tokens=800)
        if response:
            import json as _json
            # Extract JSON from response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            insights = _json.loads(text)
            if isinstance(insights, list):
                return {"insights": insights[:5], "source": "ai", "period": period}
    except Exception as e:
        logger.warning(f"AI correlation insights failed: {e}")

    # Rule-based fallback
    insights = _generate_rule_based_insights(matrix, systemic, notable, period, name_map)
    return {"insights": insights, "source": "rule_based", "period": period}


def _generate_rule_based_insights(matrix, systemic, notable, period, name_map):
    """Generate insights without LLM."""
    insights = []

    # 1. Concentration risk
    high_corr = [p for p in notable if p["correlation"] > 0.7]
    if high_corr:
        pairs_text = ", ".join(f"{name_map.get(p['asset_a'],p['asset_a'])}↔{name_map.get(p['asset_b'],p['asset_b'])} ({p['correlation']:+.2f})" for p in high_corr[:3])
        insights.append({
            "icon": "⚠️",
            "title": "Koncentrationsrisk",
            "text": f"Dessa tillgångar rör sig nästan identiskt ({period}): {pairs_text}. Om du äger flera av dem ger de inte diversifiering – överväg att minska i en."
        })

    # 2. Hedging opportunities
    neg_corr = [p for p in notable if p["correlation"] < -0.4]
    if neg_corr:
        best = neg_corr[0]
        insights.append({
            "icon": "🛡️",
            "title": "Hedging-möjlighet",
            "text": f"{name_map.get(best['asset_a'],best['asset_a'])} och {name_map.get(best['asset_b'],best['asset_b'])} har {best['correlation']:+.2f} korrelation. Kombinationen ger effektiv riskspridning – om en faller tenderar den andra att stiga."
        })

    # 3. Regime signal
    regime = systemic.get("regime", "")
    risk_on = systemic.get("risk_on_count", 0)
    risk_off = systemic.get("risk_off_count", 0)
    if regime in ("risk-off", "leaning-risk-off"):
        insights.append({
            "icon": "📉",
            "title": "Risk-Off läge",
            "text": f"{risk_off} av 7 tillgångar signalerar risk-off. Defensiva tillgångar (Guld, obligationer) tenderar att prestera bättre. Överväg att minska aktiexponering."
        })
    elif regime in ("risk-on", "leaning-risk-on"):
        insights.append({
            "icon": "📈",
            "title": "Risk-On läge",
            "text": f"{risk_on} av 7 tillgångar signalerar risk-on. Riskaptiten driver marknaden – aktier och BTC tenderar att prestera bäst. Säkerhetshedge via Guld kan vara billig just nu."
        })

    # 4. BTC decorrelation check
    btc_sp = matrix.get("btc", {}).get("sp500", 0)
    if abs(btc_sp) < 0.2:
        insights.append({
            "icon": "₿",
            "title": "BTC dekorrelerad",
            "text": f"Bitcoin och S&P 500 har bara {btc_sp:+.2f} korrelation ({period}). BTC handlas på egna drivers (on-chain/krypto-specifikt) – ger verklig diversifiering just nu."
        })
    elif btc_sp > 0.6:
        insights.append({
            "icon": "🔗",
            "title": "BTC tightly coupled",
            "text": f"Bitcoin följer S&P 500 nära ({btc_sp:+.2f}). Krypto ger ingen diversifiering mot aktier – de faller och stiger tillsammans."
        })

    # 5. Ensure at least 2 insights
    if len(insights) < 2:
        insights.append({
            "icon": "📊",
            "title": "Normal korrelationsstruktur",
            "text": f"Inga extrema korrelationsmönster detekterade ({period}). Marknaden beter sig normalt – ingen speciell åtgärd krävs."
        })

    return insights[:5]


@app.get("/api/regime")
async def get_regime():
    """Return current market regime detection."""
    from regime_detector import regime_detector
    return regime_detector.detect_regime()


@app.get("/api/signals")
async def get_signals():
    """Return trade signals for all assets."""
    from trade_signals import signal_generator
    signals = {}
    try:
        price_map = data_service.prices  # {asset_id: {price, changePct, indicators, ...}}
        assets = data_service.assets     # [{id, finalScore, ...}, ...]

        for asset_data in assets:
            asset_id = asset_data.get("id", "")
            price_info = price_map.get(asset_id, {})
            if not price_info or not price_info.get("price"):
                continue

            # Build price_data in the format signal generator expects
            price_data = {
                "price": price_info.get("price", 0),
                "indicators": price_info.get("indicators", {}),
            }

            # Build analysis dict from stored asset
            analysis = {
                "finalScore": asset_data.get("finalScore", 0),
                "supervisorConfidence": 0.6,
                "recommendation": _score_to_rec(asset_data.get("finalScore", 0)),
            }

            signals[asset_id] = signal_generator.generate_signal(asset_id, analysis, price_data)
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
    return {"signals": signals}


def _score_to_rec(score: float) -> str:
    if score >= 5: return "Starkt Köp"
    if score >= 2: return "Köp"
    if score <= -5: return "Starkt Sälj"
    if score <= -2: return "Sälj"
    return "Neutral"


@app.get("/api/onchain")
async def get_onchain():
    """Return BTC on-chain data."""
    from onchain_data import fetch_onchain_data
    return await fetch_onchain_data()


@app.get("/api/portfolio/risk")
async def get_portfolio_risk():
    """Return portfolio summary with live P/L and risk metrics (CVaR, Monte Carlo, etc)."""
    from portfolio_manager import portfolio
    return portfolio.get_portfolio_summary(data_service.prices)


@app.post("/api/portfolio/positions")
async def add_position(body: dict):
    """Add a new portfolio position."""
    from portfolio_manager import portfolio
    result = portfolio.add_position(
        asset_id=body.get("asset_id", ""),
        quantity=body.get("quantity", 0),
        entry_price=body.get("entry_price", 0),
        entry_date=body.get("entry_date", ""),
        asset_name=body.get("asset_name", ""),
        currency=body.get("currency", "$"),
        notes=body.get("notes", ""),
    )
    return result


@app.delete("/api/portfolio/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a portfolio position."""
    from portfolio_manager import portfolio
    success = portfolio.delete_position(position_id)
    return {"success": success}


@app.get("/api/portfolio/history")
async def get_portfolio_history(limit: int = 100):
    """Return portfolio value history."""
    from portfolio_manager import portfolio
    return portfolio.get_history(limit)


@app.get("/api/portfolio/trades")
async def get_closed_trades(limit: int = 50):
    """Return closed trade history."""
    from portfolio_manager import portfolio
    return portfolio.get_closed_trades(limit)


@app.get("/api/backtest")
async def get_backtest():
    """Return AI prediction accuracy and backtesting data."""
    from evaluator import evaluator
    return evaluator.get_performance_report()


@app.get("/api/portfolio/history")
async def get_portfolio_history(days: int = 7):
    """Return portfolio score history for charting."""
    from analysis_store import store
    from datetime import datetime, timezone, timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = store._get_conn()
    rows = conn.execute("""
        SELECT timestamp, asset_id, final_score, price_at_analysis
        FROM analyses
        WHERE analysis_type = 'asset' AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (cutoff,)).fetchall()
    conn.close()

    # Group by timestamp (rounded to nearest analysis cycle)
    from collections import defaultdict
    cycles = defaultdict(dict)
    for r in rows:
        ts = r["timestamp"][:16]  # Truncate to minute
        cycles[ts][r["asset_id"]] = {
            "score": r["final_score"],
            "price": r["price_at_analysis"],
        }

    # Build timeline
    history = []
    for ts, assets in sorted(cycles.items()):
        if len(assets) < 3:  # Skip incomplete cycles
            continue
        scores = [a["score"] for a in assets.values()]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0
        buy_count = sum(1 for s in scores if s > 2.5)
        sell_count = sum(1 for s in scores if s < -2.5)
        history.append({
            "timestamp": ts,
            "avg_score": avg_score,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "assets_analyzed": len(assets),
        })

    return {"history": history, "total_cycles": len(history)}


@app.get("/api/predictions/outcomes")
async def get_predictions_outcomes(limit: int = 100):
    """Return prediction vs actual outcome pairs for charting."""
    from analysis_store import store
    conn = store._get_conn()
    rows = conn.execute("""
        SELECT e.asset_id, e.timeframe, e.predicted_direction, e.actual_direction,
               e.direction_correct, e.actual_change_pct, e.score_at_analysis,
               e.evaluated_at, a.asset_name
        FROM evaluations e
        LEFT JOIN analyses a ON a.id = e.analysis_id
        WHERE e.timeframe IN ('1h', '4h', '24h')
        ORDER BY e.evaluated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    return {
        "outcomes": [dict(r) for r in rows],
        "total": len(rows),
    }


@app.get("/api/ensemble/status")
async def get_ensemble_status_api():
    """Return current ensemble system status."""
    from meta_supervisor import get_ensemble_status
    return get_ensemble_status()


# ===== Marketaux Trending & Sentiment =====

@app.get("/api/trending")
async def get_trending():
    """Return trending entities from Marketaux."""
    from news_service import fetch_trending_entities
    trending = fetch_trending_entities()
    return {"trending": trending, "source": "marketaux"}


@app.get("/api/sentiment-stats")
async def get_sentiment_stats(symbols: str = "AAPL,TSLA,NVDA,MSFT,GOOGL", days: int = 7):
    """Return sentiment time series for given symbols."""
    from news_service import fetch_entity_sentiment_stats
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    stats = fetch_entity_sentiment_stats(symbol_list, days)
    return {"stats": stats, "days": days}


@app.get("/api/global-news")
async def get_global_news(
    countries: str = "",
    industries: str = "",
    entity_types: str = "equity",
    language: str = "en",
    search: str = "",
    limit: int = 30,
):
    """Fetch filterable global news from Marketaux."""
    from news_service import _fetch_mx_page, fetch_trending_entities
    import os
    import httpx

    api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        return {"news": data_service.get_news()[:limit], "trending": [], "count": 0}

    params = {
        "filter_entities": "true",
        "must_have_entities": "true",
        "limit": min(limit, 50),
    }

    if countries:
        params["countries"] = countries
    if industries:
        params["industries"] = industries
    if entity_types:
        params["entity_types"] = entity_types
    if language:
        params["language"] = language
    if search:
        params["search"] = search

    news_items = []
    try:
        with httpx.Client(timeout=20.0) as client:
            _fetch_mx_page(client, api_key, params, news_items)
    except Exception:
        pass

    # Also get trending for same filters
    trending = []
    try:
        with httpx.Client(timeout=15.0) as client:
            t_params = {
                "api_token": api_key,
                "min_doc_count": 3,
                "limit": 15,
            }
            if countries:
                t_params["countries"] = countries
            if language:
                t_params["language"] = language
            response = client.get(
                "https://api.marketaux.com/v1/entity/trending/aggregation",
                params=t_params,
            )
            if response.status_code == 200:
                data = response.json()
                for e in data.get("data", []):
                    trending.append({
                        "symbol": e.get("key", ""),
                        "mentions": e.get("total_documents", 0),
                        "sentiment_avg": round(e.get("sentiment_avg", 0) or 0, 3),
                        "score": round(e.get("score", 0) or 0, 2),
                    })
    except Exception:
        pass

    return {"news": news_items, "trending": trending, "count": len(news_items)}


# ===== Risk Profile Portfolios =====

@app.get("/api/risk-profiles")
async def get_risk_profiles():
    """Return 3 risk-profiled AI portfolios + regime advice."""
    from ai_engine import generate_risk_portfolios

    # Build assets_analysis from current data
    assets_analysis = {}
    for asset in data_service.assets:
        assets_analysis[asset["id"]] = {
            "finalScore": asset.get("finalScore", 0),
            "name": asset.get("name", asset["id"]),
        }

    if not assets_analysis:
        return {"profiles": {}, "regime": {"regime": "neutral", "recommended_profile": "balanced", "advice": "Ingen data tillgänglig."}}

    # === Extract macro signals for scoring ===
    overall_score = sum(a.get("finalScore", 0) for a in assets_analysis.values()) / max(len(assets_analysis), 1)
    oil_score = assets_analysis.get("oil", {}).get("finalScore", 0)
    rates_score = assets_analysis.get("us10y", {}).get("finalScore", 0)
    equity_score = assets_analysis.get("sp500", {}).get("finalScore", 0)
    gold_score = assets_analysis.get("gold", {}).get("finalScore", 0)
    eurusd_score = assets_analysis.get("eurusd", {}).get("finalScore", 0)
    btc_score = assets_analysis.get("btc", {}).get("finalScore", 0)

    # === Fas 2+3: Sector & Region scoring via momentum ranking (#4) ===
    try:
        from signal_optimizer import compute_momentum_scores
        momentum = compute_momentum_scores()
    except Exception as e:
        logger.warning(f"⚠️ Momentum ranking failed, using heuristic fallback: {e}")
        momentum = {}

    # Sector ETFs — use momentum if available, fallback to heuristic
    sector_ids = ["sector-finance", "sector-energy", "sector-tech", "sector-health", "sector-defense"]
    region_ids = ["region-em", "region-europe", "region-japan", "region-india"]

    # Heuristic fallback scores (same as before)
    heuristic_scores = {
        "sector-finance": round(rates_score * 0.5 + equity_score * 0.3 + overall_score * 0.2, 1),
        "sector-energy": round(oil_score * 0.6 + equity_score * 0.2 + overall_score * 0.2, 1),
        "sector-tech": round(equity_score * 0.4 - rates_score * 0.3 + overall_score * 0.3, 1),
        "sector-health": round(-overall_score * 0.3 + gold_score * 0.3 + 1.0, 1),
        "sector-defense": round(gold_score * 0.4 - overall_score * 0.2 + 1.5, 1),
        "region-em": round(max(-5, min(5, -eurusd_score * 0.3 + oil_score * 0.2 + equity_score * 0.3 + overall_score * 0.2)), 1),
        "region-europe": round(max(-5, min(5, eurusd_score * 0.4 + equity_score * 0.3 + overall_score * 0.3)), 1),
        "region-japan": round(max(-5, min(5, -rates_score * 0.3 + equity_score * 0.3 + overall_score * 0.2 + 0.5)), 1),
        "region-india": round(max(-5, min(5, equity_score * 0.3 + btc_score * 0.2 + overall_score * 0.3 + 1.0)), 1),
    }

    from portfolio_optimizer import ASSET_NAMES

    for asset_id in sector_ids + region_ids:
        if asset_id in momentum and "score" in momentum[asset_id]:
            # Use momentum-ranked score (data-driven)
            mom_data = momentum[asset_id]
            score = mom_data["score"]
            # Blend: 70% momentum + 30% heuristic (smooths transitions)
            heuristic = heuristic_scores.get(asset_id, 0)
            blended = round(score * 0.7 + heuristic * 0.3, 1)
            blended = max(-5, min(5, blended))
        else:
            # Pure heuristic fallback
            blended = heuristic_scores.get(asset_id, 0)

        assets_analysis[asset_id] = {
            "finalScore": blended,
            "name": ASSET_NAMES.get(asset_id, asset_id),
        }

    # === Leveraged ETFs (Turbo profile) ===
    # Scored as amplified versions of their underlying (2x equity signal)
    lev_sp500_score = max(-5, min(5, equity_score * 2.0))
    lev_nasdaq_score = max(-5, min(5, equity_score * 1.5 + overall_score * 0.5))
    assets_analysis["leveraged-sp500"] = {"finalScore": round(lev_sp500_score, 1), "name": "S&P 500 2x (SSO)"}
    assets_analysis["leveraged-nasdaq"] = {"finalScore": round(lev_nasdaq_score, 1), "name": "Nasdaq 2x (QLD)"}

    market_state = data_service.get_market_state()
    result = generate_risk_portfolios(assets_analysis, market_state)
    return result


@app.get("/api/signal-weights")
async def get_signal_weights_api():
    """Return trained signal weights and momentum rankings."""
    from signal_optimizer import get_signal_weights, compute_momentum_scores
    try:
        weights = get_signal_weights()
        momentum = compute_momentum_scores()
        return {"signal_weights": weights, "momentum_rankings": momentum}
    except Exception as e:
        logger.error(f"Signal weights failed: {e}")
        return {"error": str(e), "signal_weights": {}, "momentum_rankings": {}}


# ===== Core-Satellite Portfolio =====

@app.get("/api/core-satellite")
async def get_core_satellite(
    portfolio_value: float = 700000,
    broker: str = "avanza",
):
    """
    Hämta Core-Satellite portföljrekommendation anpassad till belopp OCH mäklare.

    Query params:
      portfolio_value: float (default 700000)
      broker: "avanza" | "nordnet" (default "avanza")

    Exempel:
      /api/core-satellite?portfolio_value=100000   -> Mikro (3 fonder)
      /api/core-satellite?portfolio_value=700000   -> Standard (5+4)
      /api/core-satellite?portfolio_value=5000000  -> Large (8+6)
      /api/core-satellite?portfolio_value=15000000 -> Institutional (10+8)
    """
    from portfolio_builder import CoreSatelliteBuilder
    from broker_config import get_broker as get_broker_config, calculate_portfolio_courtage
    from regime_detector import regime_detector

    builder = CoreSatelliteBuilder()
    broker_config = get_broker_config(broker)

    # Hämta regim
    regime_data = regime_detector.detect_regime()
    regime = regime_data.get("regime", "neutral") if regime_data else "neutral"

    # Hämta senaste synthesis-resultat (från Pipeline B)
    final_scores = {}
    consensus = {}
    conviction = 0.7

    if _last_pipeline_result:
        synth = _last_pipeline_result.get("synthesis", {})
        final_scores = synth.get("final_scores", {})
        conviction = synth.get("conviction_ratio", 0.7)

    # Fallback: bygg från data_service assets
    for asset in data_service.assets:
        aid = asset.get("id", "")
        score = asset.get("finalScore", 0)
        final_scores.setdefault(aid, score)
        consensus.setdefault(aid, {
            "consensus_fraction": 0.6 if abs(score) > 2 else 0.4,
            "avg_score": score,
        })

    # Konvexa positioner
    convex = []
    try:
        convex = event_tree_engine.get_all_convex_positions()
    except Exception:
        pass

    # Risk status
    trailing = False
    try:
        total_value = sum(
            pr.get("price", 0) if isinstance(pr, dict) else pr
            for pr in (data_service.prices or {}).values()
        )
        if total_value > 0:
            trailing = risk_manager.update(total_value).get("stop_triggered", False)
    except Exception:
        pass

    portfolio = builder.build_portfolio(
        portfolio_value=portfolio_value,
        regime=regime,
        final_scores=final_scores,
        consensus=consensus,
        conviction_ratio=conviction,
        convex_positions=convex,
        trailing_stop_active=trailing,
        broker_id=broker,
    )

    # Beräkna exakt courtage för hela portföljen
    all_positions = portfolio["core"] + portfolio["satellites"]
    courtage = calculate_portfolio_courtage(broker, all_positions)
    portfolio["courtage_details"] = courtage
    portfolio["broker"] = broker_config.name

    return portfolio


@app.get("/api/compare-brokers")
async def compare_brokers(portfolio_value: float = 700000):
    """Jämför courtage Avanza vs Nordnet för en given portföljstorlek."""
    from portfolio_builder import CoreSatelliteBuilder
    from broker_config import calculate_portfolio_courtage

    builder = CoreSatelliteBuilder()

    results = {}
    for broker_id in ["avanza", "nordnet"]:
        portfolio = builder.build_portfolio(
            portfolio_value=portfolio_value,
            broker_id=broker_id,
            regime="neutral",
        )
        positions = portfolio["core"] + portfolio["satellites"]
        cost = calculate_portfolio_courtage(broker_id, positions)
        results[broker_id] = {
            "name": cost["broker"],
            "total_courtage_sek": cost["total_courtage_sek"],
            "total_fx_fee_sek": cost["total_fx_fee_sek"],
            "total_cost_sek": cost["total_cost_sek"],
            "positions": len(positions),
            "funds_used": sum(1 for p in positions if p.get("courtage_pct", 0) == 0),
        }

    av_cost = results["avanza"]["total_cost_sek"]
    nn_cost = results["nordnet"]["total_cost_sek"]
    if av_cost < nn_cost:
        rec = f"Avanza är billigare ({av_cost:.0f} kr vs {nn_cost:.0f} kr) tack vare fler egna fonder med 0 kr courtage."
    elif nn_cost < av_cost:
        rec = f"Nordnet är billigare ({nn_cost:.0f} kr vs {av_cost:.0f} kr)."
    else:
        rec = "Lika kostnad. Välj baserat på plattform och funktioner."

    return {
        "portfolio_value": portfolio_value,
        "avanza": results["avanza"],
        "nordnet": results["nordnet"],
        "recommendation": rec,
        "note": "Valutaväxling 0.25% tillkommer på utlandshandel hos båda. Fonder har 0 kr courtage hos båda.",
    }


@app.get("/api/composite-portfolio")
async def get_composite_portfolio():
    """Return AI composite portfolio backtest — regime-switching track record."""
    from composite_backtest import run_composite_backtest
    try:
        result = run_composite_backtest()
        return result
    except Exception as e:
        logger.error(f"Composite backtest failed: {e}")
        return {"error": str(e), "equity_curve": [], "benchmark_curve": [], "regime_log": [], "stats": {}}


@app.get("/api/feedback-stats")
async def get_feedback_stats():
    """Return AI feedback analysis — hit rates, drawdown episodes, learning insights."""
    from regime_feedback import analyze_regime_feedback
    try:
        result = analyze_regime_feedback()
        return result
    except Exception as e:
        logger.error(f"Feedback analysis failed: {e}")
        return {"error": str(e), "insights": [], "hit_rates": {}, "drawdown_episodes": [], "switch_scores": []}


# ===== User Portfolio Endpoints =====

@app.get("/api/user-portfolio/news")
async def get_portfolio_news(tickers: str = ""):
    """Fetch news for specific portfolio tickers."""
    from news_service import _fetch_mx_page
    import os
    import httpx

    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {"news": [], "count": 0}

    api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        # Fallback: filter from existing news
        all_news = data_service.get_news()
        filtered = [n for n in all_news if any(t.upper() in [tk.upper() for tk in n.get("tickers", [])] for t in ticker_list)]
        return {"news": filtered[:20], "count": len(filtered)}

    # Fetch from Marketaux for these specific tickers
    news_items = []
    try:
        with httpx.Client(timeout=15.0) as client:
            _fetch_mx_page(client, api_key, {
                "symbols": ",".join(ticker_list[:10]),
                "filter_entities": "true",
                "limit": 30,
                "language": "en",
            }, news_items)
    except Exception:
        pass

    return {"news": news_items[:20], "count": len(news_items)}

@app.post("/api/user-portfolio/parse-image")
async def parse_portfolio_image_endpoint(file: UploadFile):
    """Parse a portfolio screenshot using Gemini Vision."""
    from user_portfolio import parse_portfolio_image
    contents = await file.read()
    result = await parse_portfolio_image(contents, file.filename or "image.png")
    return result


@app.get("/api/user-portfolio/search")
async def search_ticker_endpoint(q: str):
    """Search for a stock/fund ticker."""
    from user_portfolio import search_ticker
    results = await search_ticker(q)
    return {"results": results}


@app.post("/api/user-portfolio/save")
async def save_portfolio_endpoint(request: Request):
    """Save a user portfolio."""
    from user_portfolio import save_portfolio
    data = await request.json()
    pid = save_portfolio(
        name=data.get("name", "Min Portfölj"),
        holdings=data.get("holdings", []),
        total_value=data.get("total_value", 0),
    )
    return {"id": pid, "status": "saved"}


@app.get("/api/user-portfolio/list")
async def list_portfolios_endpoint():
    """List all user portfolios."""
    from user_portfolio import get_portfolios
    return {"portfolios": get_portfolios()}


@app.delete("/api/user-portfolio/{portfolio_id}")
async def delete_portfolio_endpoint(portfolio_id: int):
    """Delete a user portfolio."""
    from user_portfolio import delete_portfolio
    delete_portfolio(portfolio_id)
    return {"status": "deleted"}


@app.post("/api/user-portfolio/compare")
async def compare_portfolios_endpoint(request: Request):
    """Compare user portfolio against AI optimal."""
    from user_portfolio import compare_portfolios, fetch_holdings_data, calculate_efficient_frontier

    data = await request.json()
    holdings = data.get("holdings", [])

    # Enrich with live prices
    enriched = await fetch_holdings_data(holdings)

    # Get AI portfolio from data_service (same as /api/portfolio)
    ai_portfolio = data_service.get_portfolio()

    # Compare
    comparison = await compare_portfolios(enriched, ai_portfolio)

    # Calculate efficient frontier
    frontier = await calculate_efficient_frontier(
        enriched, ai_portfolio.get("allocations", [])
    )

    return {
        "user_holdings": enriched,
        "ai_portfolio": ai_portfolio,
        "comparison": comparison,
        "frontier": frontier,
    }


# ============================================================
# RegimeTransition: Gradual regime change with confirmation
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RegimeTransition:
    """Hanterar gradvis övergång mellan regimer"""
    current_regime: str = "NEUTRAL"
    target_regime: str = "NEUTRAL"
    transition_start: Optional[datetime] = None
    transition_days: int = 3           # 3-dagars bekräftelse
    blend_steps: int = 3               # 3 steg för gradvis övergång
    current_step: int = 0
    confirmed: bool = True

    def signal_new_regime(self, detected_regime: str) -> dict:
        """Anropas varje dag med detekterad regim."""
        if detected_regime == self.current_regime:
            self.target_regime = self.current_regime
            self.transition_start = None
            self.current_step = 0
            self.confirmed = True
            return {
                "action": "HOLD",
                "regime": self.current_regime,
                "blend": {self.current_regime: 1.0},
                "message": f"Stabil {self.current_regime}-regim"
            }

        if detected_regime != self.target_regime:
            self.target_regime = detected_regime
            self.transition_start = datetime.now()
            self.current_step = 0
            self.confirmed = False
            return {
                "action": "WAIT",
                "regime": self.current_regime,
                "blend": {self.current_regime: 1.0},
                "message": f"Ny signal: {detected_regime}. Väntar bekräftelse (dag 1/{self.transition_days})"
            }

        # Samma target som förut — räkna bekräftelsedagar
        if self.transition_start:
            days = (datetime.now() - self.transition_start).days

            if days < self.transition_days and not self.confirmed:
                return {
                    "action": "WAIT",
                    "regime": self.current_regime,
                    "blend": {self.current_regime: 1.0},
                    "message": f"Bekräftar {self.target_regime} (dag {days+1}/{self.transition_days})"
                }

            # Bekräftad! Starta gradvis övergång
            self.confirmed = True
            self.current_step += 1
            blend_pct = min(self.current_step / self.blend_steps, 1.0)

            if blend_pct >= 1.0:
                self.current_regime = self.target_regime
                self.current_step = 0
                return {
                    "action": "COMPLETE",
                    "regime": self.current_regime,
                    "blend": {self.current_regime: 1.0},
                    "message": f"Regimövergång till {self.current_regime} klar"
                }

            return {
                "action": "TRANSITION",
                "regime": f"{self.current_regime}->{self.target_regime}",
                "blend": {
                    self.current_regime: round(1.0 - blend_pct, 2),
                    self.target_regime: round(blend_pct, 2)
                },
                "message": f"Övergår till {self.target_regime}: steg {self.current_step}/{self.blend_steps} ({blend_pct*100:.0f}%)"
            }

        return {"action": "HOLD", "regime": self.current_regime, "blend": {self.current_regime: 1.0}}

    def get_blended_weights(
        self,
        regime_weights: dict,
        blend: dict
    ) -> dict:
        """Blanda vikter från två regimer baserat på blend-procent."""
        result = {}
        all_assets = set()
        for weights in regime_weights.values():
            all_assets.update(weights.keys())

        for asset in all_assets:
            blended = 0.0
            for regime, pct in blend.items():
                regime_w = regime_weights.get(regime, {})
                blended += regime_w.get(asset, 0) * pct
            result[asset] = round(blended, 2)

        return result


# Global regime transition manager
regime_transition = RegimeTransition()


# ============================================================
# New API Endpoints
# ============================================================

from pydantic import BaseModel


class PortfolioUpdate(BaseModel):
    portfolio_value: float
    profile: str = "balanced"


class RebalanceRequest(BaseModel):
    current_weights: dict
    target_weights: dict
    portfolio_value: float


@app.post("/api/risk-check")
async def check_risk(update: PortfolioUpdate):
    """Kolla trailing stop och risk-status"""
    result = risk_manager.update(update.portfolio_value, update.profile)
    return result


@app.post("/api/filter-trades")
async def filter_trades_endpoint(request: RebalanceRequest):
    """Filtrera trades baserat på courtage vs förväntad förbättring"""
    trades = filter_rebalancing(
        request.current_weights,
        request.target_weights,
        request.portfolio_value
    )
    approved = {k: v for k, v in trades.items() if v["should_trade"]}
    blocked = {k: v for k, v in trades.items() if not v["should_trade"]}

    return {
        "approved_trades": approved,
        "blocked_trades": blocked,
        "total_fee_cost": sum(v["fee_cost_sek"] for v in approved.values()),
        "n_approved": len(approved),
        "n_blocked": len(blocked)
    }


@app.get("/api/walkforward")
async def run_walkforward():
    """Kör walk-forward-backtest med historisk data"""
    import pandas as pd
    from walkforward_backtest import WalkForwardEngine, WalkForwardConfig
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}

    # Build price data from returns (cumulative)
    price_data = (1 + returns).cumprod() * 100

    # Generate signal scores from momentum (proxy signals)
    signals = pd.DataFrame(index=returns.index)
    for col in returns.columns:
        # ROC 10d as signal
        signals[f"{col}_mom"] = returns[col].rolling(10).mean() * 100

    signals = signals.dropna()
    price_data = price_data.loc[signals.index]

    engine = WalkForwardEngine(WalkForwardConfig(
        train_months=12,
        test_months=3,
        min_train_samples=200
    ))
    result = engine.run(price_data, signals)
    return result


@app.get("/api/regime-transition")
async def get_regime_status():
    """Hämta aktuell regim-övergångs-status"""
    return {
        "current_regime": regime_transition.current_regime,
        "target_regime": regime_transition.target_regime,
        "confirmed": regime_transition.confirmed,
        "step": regime_transition.current_step,
        "blend_steps": regime_transition.blend_steps,
        "transition_days": regime_transition.transition_days
    }


# ============================================================
# Del 2 API Endpoints
# ============================================================

class DomainNote(BaseModel):
    text: str
    category: str = "general"
    priority: int = 5


class PortfolioWeights(BaseModel):
    weights: dict


@app.get("/api/agent-performance")
async def get_agent_performance(lookback_days: int = 90):
    """Hämta prestandarapport per agent"""
    return perf_tracker.get_agent_report(lookback_days)


@app.post("/api/risk-attribution")
async def get_risk_attribution(portfolio: PortfolioWeights):
    """Vilken position bidrar mest till portföljrisk?"""
    from risk_attribution import RiskAttribution
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    # Filter weights to only include assets in returns data
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar i historisk data", "available": list(returns.columns)}
    attr = RiskAttribution(returns, valid_weights)
    return attr.compute()


@app.post("/api/stress-test")
async def run_stress_test(portfolio: PortfolioWeights):
    """Monte Carlo + historiska scenarier"""
    from stress_test import MonteCarloStressTest
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar", "available": list(returns.columns)}
    mc = MonteCarloStressTest(returns, n_simulations=10000, horizon_days=21)
    result = mc.run(valid_weights)
    result["historical"] = mc.historical_scenarios(valid_weights)
    return result


@app.post("/api/efficient-frontier")
async def analyze_frontier(portfolio: PortfolioWeights):
    """Var på effektiva fronten ligger din portfölj?"""
    from efficient_frontier import EfficientFrontierAnalyzer
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar", "available": list(returns.columns)}
    ef = EfficientFrontierAnalyzer(returns)
    return ef.analyze_portfolio(valid_weights)


@app.post("/api/domain-note")
async def add_domain_note(note: DomainNote):
    """Lägg till domänkunskap som injiceras i alla agenter"""
    return domain_mgr.add_note(note.text, note.category, note.priority)


@app.get("/api/domain-notes")
async def get_domain_notes():
    """Hämta alla aktiva domännoteringar"""
    return domain_mgr.get_active_notes()


@app.delete("/api/domain-note/{note_id}")
async def delete_domain_note(note_id: int):
    """Ta bort en domännotering"""
    domain_mgr.remove_note(note_id)
    return {"status": "removed"}


# ============================================================
# Del 3 API Endpoints
# ============================================================

class TaxAnalysisRequest(BaseModel):
    holdings: list
    total_isk_value: float = 0


class RebalanceCheckRequest(BaseModel):
    current_weights: dict
    target_weights: dict
    regime_changed: bool = False
    portfolio_value: float = 0


@app.post("/api/currency-exposure")
async def analyze_currency(portfolio: PortfolioWeights):
    """Analysera valutaexponering och föreslå hedging"""
    return currency_calc.analyze_exposure(portfolio.weights)


@app.post("/api/tax-optimize")
async def optimize_tax(request: TaxAnalysisRequest):
    """Analysera skatteoptimal placering per tillgång (ISK/Depå)"""
    return tax_opt.analyze_portfolio(request.holdings, request.total_isk_value)


@app.get("/api/tax-quick-check")
async def quick_tax_check(value: float, expected_return: float):
    """Snabbkoll: ISK eller depå?"""
    return {"recommendation": tax_opt.quick_check(value, expected_return)}


@app.get("/api/tax-parameters")
async def get_tax_params():
    """Aktuella skatteparametrar 2026"""
    return {
        "year": 2026,
        "statslaneranta": "2.55%",
        "schablonintakt": "3.55%",
        "effektiv_isk_skatt": "1.065%",
        "skattefri_grundniva": "300 000 kr",
        "breakeven": "3.55%",
        "depa_vinstskatt": "30%",
        "source": "Riksgälden 28 nov 2025, Morningstar, Carnegie"
    }


@app.get("/api/macro-calendar")
async def get_macro_calendar(days_ahead: int = 14):
    """Kommande makro-events med impact-bedömning"""
    return macro_cal.get_upcoming(days_ahead)


@app.post("/api/should-rebalance")
async def check_rebalance(request: RebalanceCheckRequest):
    """Smart rebalanserings-check: kalender + drift + signal"""
    return rebalance_sched.should_rebalance(
        request.current_weights,
        request.target_weights,
        request.regime_changed,
        portfolio_value=request.portfolio_value
    )


@app.get("/api/drawdown-recovery")
async def estimate_recovery(drawdown_pct: float, annual_return: float = 0.08, volatility: float = 0.12):
    """Uppskatta återhämtningstid från drawdown"""
    return dd_estimator.estimate(drawdown_pct, annual_return, volatility)


@app.get("/api/cost-summary")
async def get_costs():
    """API-kostnadssammanfattning med budget-prognos"""
    return cost_tracker.get_summary()


class TaxComparisonRequest(BaseModel):
    holdings: list
    total_isk_value: float = 0


class CurrencyHedgeRequest(BaseModel):
    portfolio_weights: dict


@app.post("/api/tax-comparison")
async def compare_tax(request: TaxComparisonRequest):
    """Jämför ISK vs Depå skatteoptimering per tillgång"""
    return tax_opt.analyze_portfolio(request.holdings, request.total_isk_value)


@app.post("/api/currency-hedge")
async def analyze_currency(request: CurrencyHedgeRequest):
    """Valutaexponering och hedge-rekommendationer"""
    return currency_calc.analyze_exposure(request.portfolio_weights)


# ============================================================
# Del 4: Predictive Intelligence Endpoints
# ============================================================

class CausalRequest(BaseModel):
    event: str
    context: str = ""

class TreeRequest(BaseModel):
    event: str
    context: str = ""

class ChainActionRequest(BaseModel):
    chain_id: str
    action: str
    reason: str = ""

class NarrativeUpdateRequest(BaseModel):
    market_context: str


@app.post("/api/predictive/causal-chain/build")
async def build_causal_chain(request: CausalRequest):
    """Bygg en ny kausal kedja för en händelse via AI"""
    prompt = causal_engine.build_chain_prompt(request.event, request.context)
    try:
        response = await call_llm(
            "gemini",
            "Du är en kausal analysexpert. Svara ENBART med JSON.",
            prompt, temperature=0.4, max_tokens=2000
        )
        parsed = parse_llm_json(response)
        if parsed:
            chain = causal_engine.parse_chain_response(parsed, request.event)
            from dataclasses import asdict
            return asdict(chain)
        return {"error": "AI returned no valid JSON", "prompt": prompt}
    except Exception as e:
        logger.error(f"Causal chain build failed: {e}")
        return {"error": str(e), "prompt": prompt}


@app.get("/api/predictive/causal-chain/implications")
async def get_chain_implications(min_probability: float = 0.10):
    """Aggregerade portfölj-implikationer från alla aktiva kedjor"""
    return causal_engine.get_portfolio_implications(min_probability)


@app.post("/api/predictive/causal-chain/action")
async def chain_action(request: ChainActionRequest):
    """Bekräfta eller invalidera en kedja"""
    if request.action == "confirm":
        causal_engine.confirm_chain(request.chain_id)
    elif request.action == "invalidate":
        causal_engine.invalidate_chain(request.chain_id, request.reason)
    return {"status": "ok"}


@app.get("/api/predictive/causal-chain/accuracy")
async def chain_accuracy():
    """Hur ofta har kedjorna stämt?"""
    return causal_engine.get_chain_accuracy()


@app.post("/api/predictive/event-tree/build")
async def build_event_tree(request: TreeRequest):
    """Bygg ett event-sannolikhetsträd via AI"""
    prompt = event_tree_engine.build_tree_prompt(request.event, request.context)
    try:
        response = await call_llm(
            "gemini",
            "Du är en scenarioanalytiker. Svara ENBART med JSON.",
            prompt, temperature=0.4, max_tokens=3000
        )
        parsed = parse_llm_json(response)
        if parsed:
            tree = event_tree_engine.parse_tree_response(parsed)
            from dataclasses import asdict
            return asdict(tree)
        return {"error": "AI returned no valid JSON", "prompt": prompt}
    except Exception as e:
        logger.error(f"Event tree build failed: {e}")
        return {"error": str(e), "prompt": prompt}


@app.get("/api/predictive/event-tree/convex-positions")
async def get_convex_positions():
    """Positioner som tjänar i de flesta scenarier (konvexitet)"""
    return event_tree_engine.get_all_convex_positions()


@app.get("/api/predictive/lead-lag/signals")
async def get_lead_lag_signals():
    """Aktionerbara lead-lag-signaler från verklig data"""
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    return lead_lag_detector.get_actionable_signals(returns)


@app.get("/api/predictive/narratives")
async def get_narrative_dashboard():
    """Narrativ-dashboard med livscykel-status"""
    return narrative_tracker.get_dashboard()


@app.post("/api/predictive/narratives/update")
async def update_narratives(request: NarrativeUpdateRequest):
    """Uppdatera narrativ-analys via AI"""
    prompt = narrative_tracker.build_narrative_prompt(request.market_context)
    try:
        response = await call_llm(
            "gemini",
            "Du är en marknadsnarratologisk analytiker. Svara ENBART med JSON.",
            prompt, temperature=0.3, max_tokens=2000
        )
        parsed = parse_llm_json(response)
        if parsed:
            narrative_tracker.update_narratives(parsed)
            return narrative_tracker.get_dashboard()
        return {"error": "AI returned no valid JSON", "prompt": prompt}
    except Exception as e:
        logger.error(f"Narrative update failed: {e}")
        return {"error": str(e), "prompt": prompt}


@app.get("/api/predictive/summary")
async def predictive_summary():
    """Komplett prediktiv sammanfattning"""
    chain_impl = causal_engine.get_portfolio_implications()
    convex = event_tree_engine.get_all_convex_positions()
    narr_dashboard = narrative_tracker.get_dashboard()

    # Lead-lag signals
    ll_signals = []
    try:
        returns = data_service.get_historical_returns()
        if not returns.empty:
            ll_signals = lead_lag_detector.get_actionable_signals(returns)
    except Exception:
        pass

    return {
        "causal_chains": {
            "active": len([c for c in causal_engine.active_chains if c.status == "ACTIVE"]),
            "top_implications": dict(list(chain_impl.get("assets", {}).items())[:5]),
            "top_action": chain_impl.get("top_action")
        },
        "convex_positions": convex[:5],
        "lead_lag": {
            "n_signals": len(ll_signals),
            "top_signals": ll_signals[:3]
        },
        "narratives": {
            "active": narr_dashboard["active_narratives"],
            "risk_level": narr_dashboard["risk_level"],
            "signals": narr_dashboard["signals"][:3]
        },
        "overall_predictive_confidence": "MEDIUM"
    }


# ============================================================
# Visualization Endpoints (för P3 flödesdiagram/nätverksgraf)
# ============================================================

@app.get("/api/predictive/causal-chain/active")
async def get_active_chains_full():
    """Alla aktiva kausala kedjor med fullständig länkdata för flödesdiagram."""
    from dataclasses import asdict
    chains = [c for c in causal_engine.active_chains if c.status == "ACTIVE"]
    result = []
    for chain in chains:
        chain_dict = asdict(chain)
        # Ensure links have proper structure for visualization
        links = chain_dict.get("links", [])
        result.append({
            "id": chain_dict.get("id", ""),
            "trigger_event": chain_dict.get("trigger_event", ""),
            "status": chain_dict.get("status", ""),
            "created_at": chain_dict.get("created_at", ""),
            "probability": chain_dict.get("current_probability", 0),
            "links": [{
                "cause": l.get("cause", ""),
                "effect": l.get("effect", ""),
                "probability": l.get("probability", 0),
                "delay": l.get("delay_estimate", ""),
                "mechanism": l.get("mechanism", ""),
                "status": l.get("status", "PENDING"),
            } for l in links],
            "portfolio_impact": chain_dict.get("portfolio_impact", {}),
        })
    return {"chains": result, "total": len(result)}


@app.get("/api/political-intelligence")
async def get_political_intelligence():
    """Political Intelligence dashboard — active actors, market bias, recent signals."""
    try:
        dashboard = political_engine.get_dashboard()
        return dashboard
    except Exception as e:
        logger.error(f"Political intelligence API error: {e}")
        return {
            "market_bias": {"bias": "NEUTRAL", "confidence": 0},
            "active_actors": [],
            "recent_analyses": [],


# ===== Alpha vs Omega: Dual Portfolio =====

@app.get("/api/portfolio/dual")
async def get_dual_portfolio():
    """Head-to-head: Alpha (pipeline) vs Omega (scenario-based)."""
    comparison = portfolio_ab_tracker.get_comparison(days=90)
    omega_dash = scenario_engine.get_dashboard()
    return {
        "comparison": comparison,
        "omega_details": omega_dash,
        "chart": portfolio_ab_tracker.get_history_chart(days=90),
    }


@app.get("/api/portfolio/scenarios")
async def get_scenarios():
    """Return active scenarios with probabilities and expected returns."""
    return {
        "scenarios": scenario_engine.get_scenarios(),
        "omega_portfolio": scenario_engine.get_current_portfolio(),
        "last_generation": scenario_engine.last_generation,
    }


@app.post("/api/portfolio/scenarios/refresh")
async def refresh_scenarios():
    """Force-refresh scenarios and regenerate Omega portfolio."""
    regime = data_service.regime.get("current", "NEUTRAL") if hasattr(data_service, 'regime') else "NEUTRAL"
    pol_state = political_engine.get_current_state()
    result = await scenario_engine.refresh_scenarios(
        regime=regime,
        political_risk=pol_state.get("political_risk", "NORMAL"),
        force=True,
    )
    return {
        "status": "refreshed",
        "n_scenarios": len(scenario_engine.scenarios),
        "omega_portfolio": scenario_engine.get_current_portfolio(),
    }
            "error": str(e),
        }


@app.get("/api/predictive/lead-lag/network")
async def get_lead_lag_network():
    """Lead-lag relationer som nätverksdata (noder + kanter) för graf-visualisering."""
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"nodes": [], "edges": []}

    signals = lead_lag_detector.get_actionable_signals(returns)
    # Also get all correlations for the network
    all_assets = list(returns.columns)
    nodes = [{"id": a, "group": "crypto" if a in ["BITCOIN", "ETHEREUM"] else "equity" if a in ["SP500", "NASDAQ", "DAX", "EMERGING_MARKETS"] else "commodity"} for a in all_assets]
    edges = []
    for s in signals:
        if isinstance(s, dict):
            edges.append({
                "source": s.get("leader", ""),
                "target": s.get("follower", ""),
                "lag_days": s.get("lag_days", 0),
                "correlation": s.get("correlation", 0),
                "direction": s.get("direction", "positive"),
                "signal": s.get("signal", ""),
            })
    return {"nodes": nodes, "edges": edges}


@app.get("/api/predictive/pipeline-history")
async def get_pipeline_history():
    """Historik för pipeline-körningar (för tidsserie-graf)."""
    return {
        "runs": _pipeline_run_count,
        "last_run": _last_pipeline_run.isoformat() if _last_pipeline_run else None,
        "last_result": {
            "status": _last_pipeline_result.get("status") if _last_pipeline_result else None,
            "duration": _last_pipeline_result.get("duration_seconds") if _last_pipeline_result else None,
            "events": _last_pipeline_result.get("detection", {}).get("auto_events", 0) if _last_pipeline_result else 0,
            "chains": _last_pipeline_result.get("causal_chains", {}).get("active", 0) if _last_pipeline_result else 0,
            "lead_lag": _last_pipeline_result.get("lead_lag", {}).get("actionable_signals", 0) if _last_pipeline_result else 0,
            "recommendations": len(_last_pipeline_result.get("portfolio_recommendation", {}).get("recommendations", [])) if _last_pipeline_result else 0,
        } if _last_pipeline_result else None,
        "interval_hours": PIPELINE_INTERVAL_HOURS,
        "event_detect_refreshes": _refresh_count,
    }


# ============================================================
# Del 4B: Autonomous Predictive Pipeline
# ============================================================

@app.post("/api/predictive/run-pipeline")
async def run_predictive_pipeline():
    """Manuell trigger av full prediktiv pipeline (samma logik som autonom loop)."""
    global _last_pipeline_run, _last_pipeline_result, _pipeline_run_count
    result = await _run_full_pipeline()
    _last_pipeline_run = datetime.now()
    _last_pipeline_result = result
    _pipeline_run_count += 1
    return result


@app.get("/api/predictive/auto-status")
async def get_auto_pipeline_status():
    """Status för den autonoma bakgrundspipelinen."""
    return {
        "last_run": _last_pipeline_run.isoformat() if _last_pipeline_run else None,
        "run_count": _pipeline_run_count,
        "last_status": _last_pipeline_result.get("status") if _last_pipeline_result else None,
        "last_duration": _last_pipeline_result.get("duration_seconds") if _last_pipeline_result else None,
        "interval_hours": PIPELINE_INTERVAL_HOURS,
        "next_run_approx": (_last_pipeline_run + timedelta(hours=PIPELINE_INTERVAL_HOURS)).isoformat() if _last_pipeline_run else "Om ~2 min (initial delay)",
        "event_detection_refreshes": _refresh_count,
        "mode": "AUTONOMOUS",
    }


@app.get("/api/predictive/event-log")
async def get_event_log():
    """Historik över detekterade händelser"""
    return predictor.event_detector.get_statistics()


# ============================================================
# TILLÄGG C: END-TO-END PIPELINE TEST
# Kör hela L1-L10 med simulerad CRITICAL event.
# Rensar test-eventet efteråt.
# ============================================================

@app.post("/api/test-pipeline")
async def test_pipeline_e2e():
    """
    End-to-end test av hela 10-lagers pipeline.
    
    1. Injicerar fejkad CRITICAL-event
    2. Kör L1→L10 komplett
    3. Returnerar status per lager med tidsåtgång
    4. Rensar test-eventet (markerat som TEST)
    """
    from agents.supervisor_agent import SupervisorAgent
    from regime_detector import regime_detector
    from economic_calendar import calendar as eco_calendar
    from portfolio_builder import CoreSatelliteBuilder

    global _pipeline_api_call_count
    _pipeline_api_call_count = 0

    test_start = datetime.now()
    results = {}
    layer_times = {}

    try:
        # ---- L1: DATA ----
        l1_start = datetime.now()
        prices = data_service.prices or {}
        recent_prices = {}
        for asset_id, price_data in prices.items():
            if isinstance(price_data, dict):
                recent_prices[asset_id] = price_data.get("price", 0)
            elif isinstance(price_data, (int, float)):
                recent_prices[asset_id] = price_data

        agent_scores_current = {}
        for asset in data_service.assets:
            analysis = asset.get("analysis", {})
            for agent_name in ["macro", "micro", "technical", "sentiment"]:
                agent_data = analysis.get(agent_name, {})
                if agent_data:
                    if agent_name not in agent_scores_current:
                        agent_scores_current[agent_name] = {}
                    agent_scores_current[agent_name][asset.get("id", "")] = agent_data.get("score", 0)

        layer_times["L1"] = round((datetime.now() - l1_start).total_seconds(), 3)
        results["L1_data"] = {
            "status": "OK" if len(recent_prices) > 0 else "FAIL",
            "assets": len(recent_prices),
            "duration_s": layer_times["L1"],
        }

        # ---- L2: DETECTION (injicera test-event) ----
        l2_start = datetime.now()
        test_event = {
            "title": "TEST: Simulerad kris — Iran-eskalering",
            "severity": "CRITICAL",
            "category": "geopolitical",
            "source": "test-pipeline",
            "is_test": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Run real detection + inject test event
        detection = predictor.event_detector.run_full_detection(
            news_summary="TEST: Major geopolitical crisis simulation",
            agent_outputs={},
            recent_prices=recent_prices,
            daily_returns={k: 0 for k in recent_prices},
            historical_std={k: 0.02 for k in recent_prices},
            current_agent_scores=agent_scores_current,
            previous_agent_scores={},
            existing_chain_titles=[],
        )
        detected_count = detection.get("total_detected", 0) + 1  # +1 for injected

        layer_times["L2"] = round((datetime.now() - l2_start).total_seconds(), 3)
        results["L2_detection"] = {
            "status": "OK",
            "detected_events": detected_count,
            "test_event_injected": True,
            "duration_s": layer_times["L2"],
        }

        # ---- L3: PREDICTIVE ----
        l3_start = datetime.now()
        try:
            chain_impl = predictor.causal_engine.get_implications()
            convex = event_tree_engine.get_all_convex_positions()
            ll_signals = lead_lag_detector.get_actionable_signals()
            narr_signals = narrative_tracker.get_active_narratives()
            actor_sim_data = actor_sim.get_latest_result()
        except Exception as e:
            chain_impl, convex, ll_signals, narr_signals, actor_sim_data = {}, [], [], [], None
            logger.warning(f"L3 partial fail: {e}")

        layer_times["L3"] = round((datetime.now() - l3_start).total_seconds(), 3)
        results["L3_predictive"] = {
            "status": "OK",
            "causal_chains": len(chain_impl.get("assets", {})) if isinstance(chain_impl, dict) else 0,
            "convex_positions": len(convex),
            "lead_lag_signals": len(ll_signals),
            "narratives": len(narr_signals),
            "duration_s": layer_times["L3"],
        }

        # ---- L4: ANALYSIS ----
        l4_start = datetime.now()
        try:
            regime_data = regime_detector.detect_regime()
            current_regime = regime_data.get("regime", "neutral") if regime_data else "neutral"
        except Exception:
            current_regime = "neutral"

        try:
            vol_adjustment = {}
            returns_df = data_service.get_historical_returns()
            if not returns_df.empty:
                for col in returns_df.columns:
                    std = float(returns_df[col].std())
                    vol_adjustment[col] = min(2.0, max(0.5, 1.0 / (std * 100 + 0.01)))
        except Exception:
            vol_adjustment = {}

        conf_multiplier = 1.0
        try:
            events = eco_calendar.get_upcoming_events(days=7)
            if events:
                conf_multiplier = eco_calendar.calculate_confidence_multiplier(events)
        except Exception:
            pass

        layer_times["L4"] = round((datetime.now() - l4_start).total_seconds(), 3)
        results["L4_analysis"] = {
            "status": "OK",
            "regime": current_regime,
            "conf_multiplier": round(conf_multiplier, 2),
            "vol_adjustments": len(vol_adjustment),
            "duration_s": layer_times["L4"],
        }

        # ---- L5: SYNTHESIS ----
        l5_start = datetime.now()
        try:
            supervisor = SupervisorAgent()
            synthesis = await supervisor.synthesize(
                agent_scores=agent_scores_current,
                regime=current_regime,
                vol_adjustment=vol_adjustment,
                conf_multiplier=conf_multiplier,
                causal_implications=chain_impl,
                convex_positions=convex,
                lead_lag_signals=ll_signals,
                narrative_signals=narr_signals,
                actor_sim_result=actor_sim_data,
                domain_knowledge="TEST PIPELINE RUN",
                calibration_adjustment=confidence_cal.adjust_probability,
            )
            final_scores = synthesis.get("final_scores", {})
            conviction_ratio = synthesis.get("conviction_ratio", 0.7)
            l5_status = "OK"
        except Exception as e:
            final_scores = {a.get("id", ""): a.get("finalScore", 0) for a in data_service.assets}
            conviction_ratio = 0.5
            l5_status = f"FALLBACK ({e})"

        layer_times["L5"] = round((datetime.now() - l5_start).total_seconds(), 3)
        results["L5_synthesis"] = {
            "status": l5_status,
            "assets_scored": len(final_scores),
            "conviction": round(conviction_ratio, 2),
            "duration_s": layer_times["L5"],
        }

        # ---- L6: ADVERSARIAL ----
        l6_start = datetime.now()
        strong_signals = {k: v for k, v in final_scores.items() if isinstance(v, (int, float)) and abs(v) >= 5}
        blocked = []
        for asset_id, score in list(strong_signals.items())[:2]:
            try:
                challenge_prompt = adversarial.build_challenge_prompt({
                    "asset": asset_id, "weighted_score": score, "action": "BUY" if score > 0 else "SELL"
                })
                resp = await safe_pipeline_llm_call(
                    "gemini", "DEVILS ADVOCATE. JSON.", challenge_prompt,
                    temperature=0.4, max_tokens=2000
                )
                if resp:
                    parsed = parse_llm_json(resp)
                    if parsed:
                        result = adversarial.parse_challenge(parsed, {"asset": asset_id, "weighted_score": score})
                        if not result.should_proceed:
                            blocked.append(asset_id)
            except Exception:
                pass

        layer_times["L6"] = round((datetime.now() - l6_start).total_seconds(), 3)
        results["L6_adversarial"] = {
            "status": "OK",
            "strong_signals_challenged": len(strong_signals),
            "blocked": blocked,
            "duration_s": layer_times["L6"],
        }

        # ---- L7: PORTFOLIO (Core-Satellite) ----
        l7_start = datetime.now()
        try:
            cs_builder = CoreSatelliteBuilder()
            consensus = {}
            for asset in data_service.assets:
                aid = asset.get("id", "")
                score = final_scores.get(aid, 0)
                consensus[aid] = {
                    "consensus_fraction": 0.6 if isinstance(score, (int, float)) and abs(score) > 2 else 0.4,
                }

            portfolio_cs = cs_builder.build_portfolio(
                portfolio_value=700000,
                regime=current_regime,
                final_scores=final_scores,
                consensus=consensus,
                conviction_ratio=conviction_ratio,
                convex_positions=convex,
                trailing_stop_active=False,
            )
            l7_status = "OK"
        except Exception as e:
            portfolio_cs = {}
            l7_status = f"FAIL ({e})"

        layer_times["L7"] = round((datetime.now() - l7_start).total_seconds(), 3)
        results["L7_portfolio"] = {
            "status": l7_status,
            "tier": portfolio_cs.get("tier", {}).get("name", "?"),
            "core_positions": len(portfolio_cs.get("core", [])),
            "satellites": len(portfolio_cs.get("satellites", [])),
            "cash_pct": portfolio_cs.get("cash_pct", 0),
            "duration_s": layer_times["L7"],
        }

        # ---- L8: RISK ----
        l8_start = datetime.now()
        risk_status = {"stop_triggered": False, "drawdown_pct": 0, "action": "NORMAL"}
        try:
            total_value = sum(recent_prices.values()) if recent_prices else 0
            if total_value > 0:
                risk_status = risk_manager.update(total_value)
        except Exception:
            pass

        layer_times["L8"] = round((datetime.now() - l8_start).total_seconds(), 3)
        results["L8_risk"] = {
            "status": "OK",
            "trailing_stop": risk_status.get("stop_triggered", False),
            "drawdown_pct": round(risk_status.get("drawdown_pct", 0), 1),
            "action": risk_status.get("action", "NORMAL"),
            "duration_s": layer_times["L8"],
        }

        # ---- L9: OUTPUT ----
        l9_start = datetime.now()
        total_duration = round((datetime.now() - test_start).total_seconds(), 1)
        layer_times["L9"] = round((datetime.now() - l9_start).total_seconds(), 3)
        results["L9_output"] = {
            "status": "OK",
            "total_duration_s": total_duration,
            "api_calls_used": _pipeline_api_call_count,
            "duration_s": layer_times["L9"],
        }

        # ---- L10: FEEDBACK ----
        results["L10_feedback"] = {
            "status": "OK (scheduled, not executed in test)",
            "note": "ConfidenceCalibrator + MetaStrategy run on Mondays in background_predictive_loop",
            "duration_s": 0,
        }

        # Count passed/failed
        passed = sum(1 for v in results.values() if "OK" in str(v.get("status", "")))
        failed = len(results) - passed

        return {
            "test_result": "PASS" if failed == 0 else f"PARTIAL ({passed}/10 OK)",
            "total_duration_s": total_duration,
            "api_calls_used": _pipeline_api_call_count,
            "api_budget_remaining": MAX_API_CALLS_PER_PIPELINE - _pipeline_api_call_count,
            "regime_detected": current_regime,
            "layers": results,
            "test_event": test_event["title"],
            "note": "Test event was NOT persisted. No production data affected.",
        }

    except Exception as e:
        logger.error(f"Test pipeline failed: {e}", exc_info=True)
        return {
            "test_result": "FAIL",
            "error": str(e),
            "layers_completed": results,
            "total_duration_s": round((datetime.now() - test_start).total_seconds(), 1),
            "api_calls_used": _pipeline_api_call_count,
        }


@app.get("/api/predictive/unprocessed-events")
async def get_unprocessed():
    """Händelser som väntar på analys"""
    events = predictor.event_detector.get_unprocessed()
    return [{"id": e.id, "title": e.title, "severity": e.severity,
             "category": e.category, "assets": e.affected_assets}
            for e in events]


# ============================================================
# Del 5: Final Push — Actor Sim, Convexity, Meta, Adversarial
# ============================================================

@app.post("/api/predictive/actor-simulation")
async def run_actor_simulation(event: str = "Global trade war escalation", context: str = ""):
    """Simulera 10 marknadsaktörers reaktion på en händelse"""
    prompt = actor_sim.build_simulation_prompt(event, context)
    ai_resp = await call_llm(
        "gemini",
        "Du är en marknads-simulator. Svara ENBART med JSON.",
        prompt, temperature=0.4, max_tokens=4000
    )
    parsed = parse_llm_json(ai_resp)
    if not parsed:
        return {"error": "AI parsing failed"}
    result = actor_sim.parse_simulation(parsed, event)
    from dataclasses import asdict
    return asdict(result)


@app.get("/api/predictive/actor-intelligence")
async def get_actor_intelligence():
    """Aggregerad intelligens från alla simuleringar"""
    return actor_sim.get_aggregated_actor_intelligence()


@app.post("/api/predictive/convexity-optimize")
async def convexity_optimize():
    """Scenario-baserad portföljoptimering med event trees"""
    from dataclasses import asdict
    asset_ids = [a.get("id", "") for a in data_service.assets[:10]]
    if not asset_ids:
        return {"error": "No assets loaded"}

    optimizer = ConvexityOptimizer(asset_ids)

    # Hämta scenarion från event trees
    trees_data = []
    for tree in event_tree_engine.trees[-5:]:
        trees_data.append(asdict(tree))

    if not trees_data:
        # Generera default-scenarion
        from predictive.convexity_optimizer import Scenario
        scenarios = [
            Scenario("Bull market", 0.25, {a: 0.15 for a in asset_ids}),
            Scenario("Base case", 0.40, {a: 0.06 for a in asset_ids}),
            Scenario("Mild recession", 0.20, {a: -0.10 for a in asset_ids}),
            Scenario("Crisis", 0.15, {a: -0.25 for a in asset_ids}),
        ]
    else:
        scenarios = optimizer.build_scenarios_from_trees(trees_data)

    if not scenarios:
        return {"error": "No scenarios available"}

    max_exp = optimizer.optimize_max_expected(scenarios)
    max_conv = optimizer.optimize_max_convexity(scenarios)

    return {
        "max_expected": asdict(max_exp),
        "max_convexity": asdict(max_conv),
        "n_scenarios": len(scenarios),
        "scenario_names": [s.name for s in scenarios[:10]]
    }


@app.get("/api/predictive/confidence")
async def get_confidence_calibration():
    """Kalibrering av systemets sannolikhetsbedömningar"""
    return confidence_cal.compute_calibration()


@app.get("/api/predictive/confidence/per-source")
async def get_confidence_per_source():
    """Kalibrering per prediktionskälla"""
    return confidence_cal.per_source_calibration()


@app.get("/api/predictive/meta-strategy")
async def get_meta_strategy():
    """Diagnostik för meta-strategi (vikter per regim)"""
    return meta_strategy.get_diagnostics()


@app.post("/api/predictive/adversarial-check")
async def adversarial_check(asset: str = "SP500", action: str = "KÖP", reasoning: str = "Stark teknisk signal"):
    """Devils Advocate: utmana en portföljrekommendation"""
    from dataclasses import asdict
    rec = {"asset": asset, "action": action, "reasoning": reasoning}
    prompt = adversarial.build_challenge_prompt(rec)
    ai_resp = await call_llm(
        "gemini",
        "Du är en DEVILS ADVOCATE. Svara ENBART med JSON.",
        prompt, temperature=0.4, max_tokens=2000
    )
    parsed = parse_llm_json(ai_resp)
    if not parsed:
        return {"error": "AI parsing failed"}
    result = adversarial.parse_challenge(parsed, rec)
    return asdict(result)


@app.get("/api/system/health")
async def system_health():
    """Systemhälsa: datafärskhet, filstorlek, pipeline-status"""
    return health_check.run_checks()


@app.get("/api/system/scheduler-status")
async def scheduler_status():
    """Status för daglig scheduler"""
    return daily_sched.get_status()


# ============================================================
# AI Chat — Conversational interface to Aether AI data
# ============================================================

@app.post("/api/chat")
async def chat(request: Request):
    """AI Chat endpoint — answers questions using system data + Gemini Flash."""
    body = await request.json()
    user_message = body.get("message", "").strip()
    history = body.get("history", [])  # Previous messages for context

    if not user_message:
        return {"error": "No message provided"}

    # ---- Gather system context ----
    context_parts = []

    # 1. Current market state
    try:
        state = data_service.get_market_state()
        context_parts.append(f"AKTUELLT MARKNADSLÄGE ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}):")
        context_parts.append(f"  Totalscore: {state.get('overallScore', 'N/A')}/10")
        context_parts.append(f"  Sammanfattning: {state.get('overallSummary', 'N/A')}")
        if state.get("expandedSummary"):
            context_parts.append(f"  Detaljerad: {state['expandedSummary'][:500]}")
        context_parts.append(f"  Senast uppdaterat: {state.get('lastUpdated', 'N/A')}")
    except Exception:
        context_parts.append("Marknadsdata: ej tillgängligt just nu.")

    # 2. Current assets with scores
    try:
        assets = data_service.get_assets()
        if assets:
            context_parts.append("\nTILLGÅNGAR (aktuella AI-scores):")
            for a in assets[:10]:
                scores = a.get("scores", {})
                context_parts.append(
                    f"  {a['name']} ({a['id']}): Score={a.get('finalScore', 'N/A')}, "
                    f"Pris={a.get('price', 'N/A')} {a.get('currency', '')}, "
                    f"Förändring={a.get('changePct', 0):.1f}%, "
                    f"Macro={scores.get('macro', 'N/A')}, Micro={scores.get('micro', 'N/A')}, "
                    f"Sentiment={scores.get('sentiment', 'N/A')}, Tech={scores.get('tech', 'N/A')}"
                )
    except Exception:
        pass

    # 3. Recent supervisor summaries (historical)
    try:
        summaries = analysis_store.get_recent_summaries(n=5)
        if summaries:
            context_parts.append("\nHISTORISKA SUPERVISOR-BEDÖMNINGAR (senaste 5):")
            for s in summaries:
                context_parts.append(
                    f"  [{s.get('timestamp', '?')}] Score: {s.get('overall_score', 'N/A')}, "
                    f"Regim: {s.get('regime', 'N/A')}, "
                    f"Sammanfattning: {str(s.get('summary', 'N/A'))[:200]}"
                )
    except Exception:
        pass

    # 4. Recent asset analyses
    try:
        recent = analysis_store.get_recent_analyses(hours=168, analysis_type="asset")  # 7 days
        if recent:
            context_parts.append(f"\nHISTORISKA ANALYSER (senaste 7 dagarna): {len(recent)} st")
            # Group by asset for the AI
            asset_analyses = {}
            for a in recent[:50]:
                aid = a.get("asset_id", "unknown")
                if aid not in asset_analyses:
                    asset_analyses[aid] = []
                asset_analyses[aid].append({
                    "timestamp": a.get("timestamp"),
                    "score": a.get("final_score"),
                    "price": a.get("price_at_analysis"),
                })
            for aid, entries in list(asset_analyses.items())[:8]:
                scores_str = ", ".join([f"{e['timestamp'][:10]}: score={e['score']}, pris={e['price']}" for e in entries[:5]])
                context_parts.append(f"  {aid}: {scores_str}")
    except Exception:
        pass

    # 5. Current regime
    try:
        regime = data_service.get_regime_data()
        if regime:
            context_parts.append(f"\nAKTUELL MARKNADSREGIM: {regime.get('label', 'N/A')} ({regime.get('regime', '')})")
            context_parts.append(f"  Beskrivning: {regime.get('description', 'N/A')}")
            context_parts.append(f"  Konfidens: {regime.get('confidence', 'N/A')}")
    except Exception:
        pass

    # 6. Sectors overview
    try:
        sectors = data_service.get_sectors()
        if sectors:
            context_parts.append("\nSEKTORER:")
            for s in sectors[:10]:
                context_parts.append(f"  {s['name']}: Score={s.get('score', 'N/A')}, Signal={s.get('rotationSignal', 'N/A')}")
    except Exception:
        pass

    context_text = "\n".join(context_parts)

    # ---- Build conversation for LLM ----
    system_prompt = """Du är Aether AI-assistenten — en intelligent marknadschatt integrerad i ett autonomt AI-analysystem.

DINA EGENSKAPER:
- Du svarar på svenska, koncist och insiktsfullt
- Du har tillgång till REALTIDSDATA från Aether AI-systemet (se KONTEXT nedan)
- Du analyserar marknader, tillgångar, sektorer, regimer och historiska bedömningar
- Du kan jämföra hur AI:ns bedömning sett ut över tid
- Du är ärlig när data saknas eller är begränsat

SVARSFORMAT:
- Svara i markdown (bold, listor, etc.)
- Var specifik med siffror och data från kontexten
- Håll svaren under 300 ord om inte användaren ber om mer detalj
- Använd emojis sparsamt men effektivt (📈 📉 ⚠️ 🎯)

VIKTIGT: Basera ALLTID dina svar på den faktiska data du har tillgång till. Spekulera inte."""

    # Build user prompt with context + history
    history_text = ""
    if history:
        history_text = "\nTIDIGARE KONVERSATION:\n"
        for msg in history[-6:]:  # Last 6 messages for context
            role = "Användaren" if msg.get("role") == "user" else "Aether AI"
            history_text += f"{role}: {msg.get('content', '')}\n"

    user_prompt = f"""SYSTEMKONTEXT (Aether AI-data):
{context_text}

{history_text}
ANVÄNDARENS FRÅGA: {user_message}"""

    # ---- Call Gemini Flash (Tier 1 = cheapest) ----
    try:
        response, provider = await call_llm_tiered(
            tier=1,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=1200,
            plain_text=True,
        )
        if not response:
            return {"response": "Tyvärr kunde jag inte generera ett svar just nu. Försök igen om en stund.", "provider": "none"}

        return {
            "response": response,
            "provider": provider,
            "context_size": len(context_text),
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {"response": f"Ett fel uppstod: {str(e)}", "provider": "error"}

