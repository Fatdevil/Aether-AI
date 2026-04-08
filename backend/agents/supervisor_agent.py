"""
Supervisor Agent - The "smartest AI" that evaluates and weighs the other agents.
Primary provider: OpenAI GPT-4o (or best available)
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm, call_llm_tiered, parse_llm_json, get_available_providers, escalation_guard

logger = logging.getLogger("aether.agents.supervisor")

SYSTEM_PROMPT = """Du är SUPERVISOR AI – den överordnade analytikern i Aether AI-plattformen.
Du skriver för VANLIGA MÄNNISKOR som vill förstå marknaden, inte för professionella traders.

Din uppgift är att:
1. UTVÄRDERA de 4 underliggande AI-analytikernas bedömningar (Makro, Mikro, Sentiment, Teknisk)
2. INTEGRERA prediktiv intelligens (marknadsregim, detekterade händelser, narrativ)
3. REFERERA TILL tidigare analyser för att skapa kontinuitet och visa lärande
4. GENERERA ett transparent slutvärde (-10 till +10)
5. SKRIVA en sammanfattning som vanliga människor förstår

SKRIVRIKTLINJER FÖR supervisor_text:
- 5-7 meningar på ENKEL SVENSKA
- Börja med vad som händer just nu ("Marknaderna visar...")
- Om det finns tidigare analys, referera till den ("Sedan vår förra analys har...")
- Förklara VARFÖR — inte bara vad, utan vad det BETYDER för investerare
- Avsluta med en tydlig rekommendation
- Undvik jargong — skriv som om du förklarar för en smart vän
- Om systemets träffsäkerhet finns, nämn det kort för trovärdighet

VIKTNINGSVÄGLEDNING:
- Om alla analytiker är överens: Ge hög confidence
- Om stor oenighet: Vikta analytikern med högst confidence tyngst
- REGIM påverkar: I risk-off → Makro viktigare. I risk-on → Teknisk viktigare.
- NARRATIV i EXTREME_CONSENSUS → konträr signal. I ACCELERATION → trendföljning.
- HÄNDELSER med severity CRITICAL → sänk confidence, flagga risk
- HISTORIK: Om förra analysen var fel → justera och nämn det

FORMAT FÖR SVAR (JSON):
{
    "final_score": <float -10.0 till 10.0, en decimal>,
    "weights_applied": {
        "macro": <float 0-1>,
        "micro": <float 0-1>,
        "sentiment": <float 0-1>,
        "tech": <float 0-1>
    },
    "supervisor_text": "<5-7 meningar på ENKEL SVENSKA. Skriv som en erfaren rådgivare som förklarar för en vän. Referera till regim, händelser och tidigare analyser om de finns tillgängliga.>",
    "recommendation": "<Starkt Köp | Köp | Neutral | Sälj | Starkt Sälj>",
    "confidence": <float 0.0 till 1.0>,
    "risk_flags": ["ev. riskflagga1", "ev. riskflagga2"],
    "key_change": "<Kort: vad ändrades sedan sist? T.ex. 'Uppgraderad pga regimskifte' eller 'Oförändrad — inväntar data'>"
}"""


class SupervisorAgent(BaseAgent):
    name = "Supervisor AI"
    perspective = "Övergripande"

    def __init__(self):
        # Supervisor uses hybrid tier routing:
        #   Morning 07-09 CET: Opus ("3-opus") for deepest analysis
        #   Rest of day: Sonnet (tier 3) for cost-effective updates
        #   Regime shift / Black swan: Escalates to Opus (max 1x/day)
        available = get_available_providers()
        if not available:
            self.provider = "rule_based"
        else:
            self.provider = available[0]
        self.use_tiered = True
        self.tango_filter = TangoConsensusFilter()
        self.meta_weights = {}

    def set_meta_weights(self, weights: dict):
        """Called by MetaStrategy feedback loop to update method weights per regime."""
        self.meta_weights = weights
        logger.info(f"  ⚖️ Meta-weights updated: {list(weights.keys())}")

    def _load_regime_weights(self, regime: str) -> dict:
        """
        Load regime-specific signal weights (Fas 5 Steg 4).
        Priority:
          1. Trained joblib model → extract feature-group weights
          2. MetaStrategy self.meta_weights (from feedback loop)
          3. Hardcoded defaults
        Always returns a valid dict. Never crashes.
        """
        # Hardcoded defaults (data-validated, Steg 4)
        DEFAULTS = {
            "agents": 0.30, "causal": 0.25, "lead_lag": 0.10,
            "narrative": 0.05, "convexity": 0.15, "actor_sim": 0.15,
        }

        # Map regime name to joblib filename
        regime_key = regime.lower().replace("-", "_")
        regime_file_map = {
            "risk_on": "signal_weights_risk_on.joblib",
            "risk-on": "signal_weights_risk_on.joblib",
            "neutral": "signal_weights_neutral.joblib",
            "risk_off": "signal_weights_risk_off.joblib",
            "risk-off": "signal_weights_risk_off.joblib",
            "crisis": "signal_weights_risk_off.joblib",  # CRISIS uses RISK_OFF model
        }

        joblib_name = regime_file_map.get(regime_key)
        if not joblib_name:
            joblib_name = regime_file_map.get(regime, "signal_weights_single.joblib")

        # Try loading trained model
        try:
            import joblib
            model_path = os.path.join(os.path.dirname(__file__), "..", "models", joblib_name)
            if os.path.exists(model_path):
                model = joblib.load(model_path)
                if hasattr(model, 'coef_'):
                    # Map Ridge coefficients to method weight categories
                    # Features: sp500_roc_10d, sp500_roc_20d, sp500_momentum_50d, sp500_vol_20d,
                    #           vix_level, vix_change_5d, us10y_level, us10y_change_20d,
                    #           gold_roc_10d, gold_vs_sp500_20d, oil_roc_10d, dxy_roc_10d,
                    #           hyg_roc_10d, copper_roc_10d, em_vs_sp500_20d
                    coefs = model.coef_
                    abs_coefs = abs(coefs)
                    total_abs = abs_coefs.sum() if abs_coefs.sum() > 0 else 1.0

                    # Group features by method category:
                    # agents (0-3): sp500 ROC/momentum/vol → base agent signals
                    # causal (4-7): vix, us10y → macro drivers = causal chains
                    # lead_lag (8-11): gold, oil, dxy → cross-asset → lead-lag
                    # narrative (12): hyg → credit sentiment
                    # convexity (13-14): copper, EM → tail risk / opportunity
                    agents_w = float(abs_coefs[0:4].sum() / total_abs)
                    causal_w = float(abs_coefs[4:8].sum() / total_abs)
                    lead_lag_w = float(abs_coefs[8:12].sum() / total_abs)
                    narrative_w = float(abs_coefs[12:13].sum() / total_abs) if len(abs_coefs) > 12 else 0.05
                    convexity_w = float(abs_coefs[13:15].sum() / total_abs) if len(abs_coefs) > 13 else 0.10

                    # actor_sim gets minimum floor
                    actor_sim_w = max(0.05, 1.0 - agents_w - causal_w - lead_lag_w - narrative_w - convexity_w)

                    weights = {
                        "agents": round(agents_w, 3),
                        "causal": round(causal_w, 3),
                        "lead_lag": round(lead_lag_w, 3),
                        "narrative": round(narrative_w, 3),
                        "convexity": round(convexity_w, 3),
                        "actor_sim": round(actor_sim_w, 3),
                    }
                    logger.info(f"  📊 Loaded trained weights for {regime}: {weights}")
                    return weights
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to load regime weights from {joblib_name}: {e}")

        # Fallback 2: MetaStrategy weights (from feedback loop)
        if regime in self.meta_weights:
            logger.info(f"  ⚖️ Using MetaStrategy weights for {regime}")
            return self.meta_weights[regime]

        # Fallback 3: hardcoded defaults
        logger.info(f"  📋 Using default weights for {regime}")
        return DEFAULTS

    async def synthesize(
        self,
        # EXISTING INPUTS
        agent_scores: dict,            # {agent_name: {asset_id: score}}
        regime: str,                   # From RegimeDetector
        vol_adjustment: dict,          # {asset_id: float}
        conf_multiplier: float,        # From Calendar (0.7-1.0)
        # NEW INPUTS (from predictive modules)
        causal_implications: dict = None,
        convex_positions: list = None,
        lead_lag_signals: list = None,
        narrative_signals: list = None,
        actor_sim_result: dict = None,
        domain_knowledge: str = "",
        calibration_adjustment=None,   # callable from ConfidenceCalibrator
        political_signals: dict = None, # From PoliticalIntelligenceEngine
        # Fas 7: Enrichment signals + secondary regime
        enrichment_signals: list = None,  # Direct signals from DataEnrichmentLoader
        secondary_regime: dict = None,    # From detect_secondary_regime()
        # Fas 8: Prediction market signals
        prediction_market_signals: list = None,  # From PredictionMarketIntelligence
    ) -> dict:
        """
        CENTRAL SYNTHESIS METHOD — Pipeline B (6h autonomous)
        Takes ALL 12 inputs and produces final_scores + conviction_ratio.
        """
        import numpy as np

        # Step 1: Aggregate base scores from 4 agents
        assets = set()
        for agent_data in agent_scores.values():
            if isinstance(agent_data, dict):
                assets.update(agent_data.keys())

        base_scores = {}
        for asset in assets:
            scores = []
            for agent_name, agent_data in agent_scores.items():
                if isinstance(agent_data, dict):
                    s = agent_data.get(asset, 0)
                    if isinstance(s, (int, float)):
                        scores.append(s)
                    elif isinstance(s, dict):
                        scores.append(s.get("score", 0))
            base_scores[asset] = float(np.mean(scores)) if scores else 0

        # Step 2: Compute consensus via TangoConsensusFilter
        # Reformat agent_scores for Tango: {agent: {asset: score_float}}
        tango_input = {}
        for agent_name, agent_data in agent_scores.items():
            if isinstance(agent_data, dict):
                tango_input[agent_name] = {}
                for asset_id, val in agent_data.items():
                    if isinstance(val, (int, float)):
                        tango_input[agent_name][asset_id] = float(val)
                    elif isinstance(val, dict):
                        tango_input[agent_name][asset_id] = float(val.get("score", 0))

        consensus = self.tango_filter.compute_consensus(tango_input)

        # Step 3: Get method weights — try trained regime-specific weights first,
        # fall back to MetaStrategy, then hardcoded defaults
        method_weights = self._load_regime_weights(regime)

        # Step 4: Build final score per asset
        final_scores = {}
        for asset in assets:
            score = 0.0

            # Agent base scores (MetaStrategy-weighted)
            score += base_scores.get(asset, 0) * method_weights.get("agents", 0.30)

            # Causal chain implications
            if causal_implications and isinstance(causal_implications, dict):
                asset_impacts = causal_implications.get("assets", {})
                if asset in asset_impacts:
                    impact = asset_impacts[asset]
                    causal_score = impact.get("total_expected_impact_pct", 0) if isinstance(impact, dict) else 0
                    score += causal_score * method_weights.get("causal", 0.25)

            # Lead-lag signals
            if lead_lag_signals and isinstance(lead_lag_signals, list):
                for sig in lead_lag_signals:
                    if sig.get("follower") == asset:
                        direction = 1 if sig.get("action", "").upper() in ("KÖP", "BUY", "KOP") else -1
                        conf = sig.get("confidence", 0.5)
                        score += conf * 5 * direction * method_weights.get("lead_lag", 0.15)

            # Narrative signals
            if narrative_signals and isinstance(narrative_signals, list):
                for sig in narrative_signals:
                    affected = sig.get("assets", sig.get("affected_assets", []))
                    if asset in affected:
                        dir_str = sig.get("direction", "NEUTRAL")
                        direction = 1 if dir_str in ("BULLISH", "TRENDFÖLJ", "TRENDFOLJ") else -1
                        strength_map = {"STARK": 3, "MEDEL": 2, "SVAG": 1}
                        strength = strength_map.get(sig.get("strength", ""), 1)
                        score += strength * direction * method_weights.get("narrative", 0.10)

            # Convex positions (from EventTree)
            if convex_positions and isinstance(convex_positions, list):
                for pos in convex_positions:
                    if pos.get("asset") == asset:
                        direction = 1 if pos.get("direction", "").upper() == "LONG" else -1
                        asymmetry = pos.get("asymmetry", 1.0)
                        score += asymmetry * direction * method_weights.get("convexity", 0.15)

            # Actor simulation (only for CRITICAL events)
            if actor_sim_result and isinstance(actor_sim_result, dict):
                net_impacts = actor_sim_result.get("net_asset_impact", {})
                if asset in net_impacts:
                    sim_impact = net_impacts[asset]
                    if isinstance(sim_impact, (int, float)):
                        score += sim_impact * 0.3 * method_weights.get("actor_sim", 0.05)

            # Political Intelligence signals
            if political_signals:
                pol_direct = political_signals.get("direct_signals", [])
                pol_predictions = political_signals.get("predictions", {})

                # Dynamic weight based on political risk level
                pol_risk = political_signals.get("political_risk", "NORMAL")
                if pol_risk == "HIGH":
                    pol_weight = 0.25  # Strong signal, clear direction
                elif pol_risk == "ELEVATED":
                    pol_weight = 0.15  # Indication but uncertain
                else:
                    pol_weight = 0.05  # Background noise

                for sig in pol_direct:
                    affected = sig.get("affected_assets", [])
                    if asset in affected:
                        signal_type = sig.get("signal", "")
                        conf = sig.get("confidence", 0.5)
                        impact = sig.get("expected_impact", 0)
                        if isinstance(impact, (int, float)) and impact != 0:
                            score += impact * conf * pol_weight
                        elif "ESCALAT" in str(signal_type).upper():
                            score -= 2.0 * conf * pol_weight
                        elif "DEESCALAT" in str(signal_type).upper():
                            score += 2.0 * conf * pol_weight

                # AI predictions per actor
                for actor_id, pred_data in pol_predictions.items():
                    for pred in pred_data.get("predictions", []):
                        pred_assets = pred.get("affected_assets", []) + pred.get("known_transmission_assets", [])
                        est_impact = pred.get("estimated_impact", {})
                        # Match on explicit asset list OR estimated_impact keys
                        if asset in pred_assets or (isinstance(est_impact, dict) and asset in est_impact):
                            if isinstance(est_impact, dict) and asset in est_impact:
                                impact_pct = est_impact[asset]
                                prob = pred.get("probability", 0.5)
                                score += impact_pct * prob * 0.1 * pol_weight

            # Fas 7: Enrichment direct signals
            # These are strong data-driven signals (VIX backwardation, breadth divergence, etc.)
            if enrichment_signals and isinstance(enrichment_signals, list):
                for sig in enrichment_signals:
                    affected = sig.get("affected_assets", [])
                    if asset in affected or asset.lower() in [a.lower() for a in affected]:
                        strength_map = {"CRITICAL": 3.0, "HIGH": 2.0, "MEDIUM": 1.0}
                        strength = strength_map.get(sig.get("strength", ""), 1.0)
                        action = sig.get("action", "")

                        # Determine direction from action
                        if "KOP" in action.upper() or "OKA_GULD" in action.upper():
                            direction = 1
                        else:
                            direction = -1  # Most signals are defensive (reduce risk)

                        score += direction * strength * 0.20  # Weighted at 0.20 for data-driven signals

            # Fas 8: Prediction market signals
            # These are odds-movement signals from Polymarket
            if prediction_market_signals and isinstance(prediction_market_signals, list):
                for pm_sig in prediction_market_signals:
                    pm_affected = pm_sig.get("affected_assets", [])
                    if asset in pm_affected or asset.upper() in [a.upper() for a in pm_affected]:
                        # Weight by significance: NOTABLE=0.3, MAJOR=0.6, EXTREME=1.0
                        sig_type = pm_sig.get("signal", "")
                        if "EXTREME" in sig_type:
                            pm_weight = 1.0
                        elif "MAJOR" in sig_type:
                            pm_weight = 0.6
                        else:
                            pm_weight = 0.3

                        # Direction from implication
                        impl = pm_sig.get("implication", "").upper()
                        if any(w in impl for w in ["BULLISH", "RISK_ON", "RELIEF"]):
                            pm_direction = 1
                        elif any(w in impl for w in ["BEARISH", "RISK_OFF", "CRISIS"]):
                            pm_direction = -1
                        else:
                            pm_direction = -0.5  # Default to slightly defensive for uncertainty

                        score += pm_direction * pm_weight * 0.15  # 0.15 weight for prediction markets

            # Apply vol_adjustment and conf_multiplier
            score *= vol_adjustment.get(asset, 1.0)
            score *= conf_multiplier

            # Apply ConfidenceCalibrator if available
            if calibration_adjustment and callable(calibration_adjustment):
                try:
                    raw_confidence = min(abs(score) / 10, 0.99)
                    adjusted = calibration_adjustment(raw_confidence)
                    if raw_confidence > 0.01:
                        score = score * (adjusted / raw_confidence)
                except Exception:
                    pass

            final_scores[asset] = round(score, 2)

        # Step 5: Apply Tango consensus filter
        tango_filtered = self.tango_filter.apply_to_mpt_weights(
            final_scores, consensus, vol_adjustment
        )

        # Step 6: Compute conviction_ratio from divergence
        divergence = self.tango_filter.detect_divergence_signal(consensus)
        conviction_ratio = 1.0 - (divergence.get("cash_boost", 0) * 2)
        conviction_ratio = max(0.3, min(1.0, conviction_ratio))

        logger.info(f"  🧠 Synthesize: {len(final_scores)} assets, "
                    f"conviction={conviction_ratio:.2f}, regime={regime}")

        return {
            "final_scores": tango_filtered,
            "conviction_ratio": round(conviction_ratio, 3),
            "regime": regime,
            "method_weights_used": method_weights,
            "consensus": consensus,
            "divergence": divergence,
            "domain_knowledge_injected": len(domain_knowledge) > 0,
        }

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        """Not used directly - supervisor uses evaluate() instead."""
        return {}

    async def evaluate(
        self,
        asset_id: str,
        asset_name: str,
        category: str,
        price_data: dict,
        agent_results: dict,
        predict_context: str = "",
    ) -> dict:
        """
        Evaluate the outputs from all 4 agents and produce final assessment.
        agent_results: {"macro": {...}, "micro": {...}, "sentiment": {...}, "tech": {...}}
        predict_context: formatted string from SupervisorContextBuilder
        """
        if self.provider == "rule_based":
            return self._rule_based_evaluate(asset_id, asset_name, price_data, agent_results)

        # Build context for LLM
        price_ctx = self._format_price_context(price_data)
        agent_summary = self._format_agent_results(agent_results)

        user_prompt = f"""SUPERVISOR-UTVÄRDERING för {asset_name} ({category})

{price_ctx}

ANALYTIKERNAS BEDÖMNINGAR:
{agent_summary}"""

        # Add predict context if available
        if predict_context:
            user_prompt += f"""

PREDIKTIV INTELLIGENS & HISTORIK:
{predict_context}"""

        user_prompt += """

Utvärdera dessa bedömningar med hänsyn till regim, händelser och historik.
Skriv supervisor_text för VANLIGA MÄNNISKOR — enkel, tydlig svenska.
Ge ditt slutvärde som JSON."""

        # Smart tier selection:
        #   1. Morning window (07-09 CET) → always Opus
        #   2. Escalation active (regime shift / black swan approved) → Opus (one-shot)
        #   3. Otherwise → Sonnet (cost-effective)
        if escalation_guard.is_morning_opus_window():
            tier = "3-opus"
        elif escalation_guard.is_escalation_active():
            tier = "3-opus"
        else:
            tier = 3  # Sonnet (standard)

        response, provider_used = await call_llm_tiered(
            tier=tier,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=600,
        )

        # Consume the escalation after use (so it doesn't persist)
        if tier == "3-opus" and not escalation_guard.is_morning_opus_window():
            escalation_guard.consume_escalation()
        result = parse_llm_json(response)

        if result and "final_score" in result:
            return {
                "finalScore": round(float(result["final_score"]), 1),
                "weights": result.get("weights_applied", {"macro": 0.3, "micro": 0.25, "sentiment": 0.2, "tech": 0.25}),
                "supervisorText": result.get("supervisor_text", ""),
                "recommendation": result.get("recommendation", "Neutral"),
                "confidence": float(result.get("confidence", 0.7)),
                "risk_flags": result.get("risk_flags", []),
                "key_change": result.get("key_change", ""),
                "provider_used": provider_used,
            }

        return self._rule_based_evaluate(asset_id, asset_name, price_data, agent_results)

    def _format_agent_results(self, results: dict) -> str:
        lines = []
        labels = {"macro": "MAKRO", "micro": "MIKRO", "sentiment": "SENTIMENT", "tech": "TEKNISK"}
        for key, label in labels.items():
            r = results.get(key, {})
            score = r.get("score", 0)
            conf = r.get("confidence", 0)
            reasoning = r.get("reasoning", "N/A")
            provider = r.get("provider_used", "unknown")
            factors = ", ".join(r.get("key_factors", []))
            lines.append(
                f"{label}-ANALYTIKER (via {provider}):\n"
                f"  Poäng: {score:+d}/10 | Confidence: {conf:.0%}\n"
                f"  Motivering: {reasoning}\n"
                f"  Nyckelfaktorer: {factors}"
            )
        return "\n\n".join(lines)

    def _rule_based_evaluate(self, asset_id, asset_name, price_data, agent_results, weights_override=None):
        # Load learned weights if available (from signal optimization)
        weights = weights_override
        if not weights:
            weights = self._get_optimized_weights()

        weighted = sum(
            agent_results.get(key, {}).get("score", 0) * w
            for key, w in weights.items()
        )
        final = round(max(-10, min(10, weighted)), 1)

        scores = {k: agent_results.get(k, {}).get("score", 0) for k in weights}
        strongest = max(scores, key=scores.get)
        weakest = min(scores, key=scores.get)

        labels = {"macro": "Makro", "micro": "Mikro", "sentiment": "Sentiment", "tech": "Teknisk"}
        spread = max(scores.values()) - min(scores.values())
        agreement = "Stark samsyn" if spread <= 3 else "Moderat spridning" if spread <= 6 else "Stor oenighet"

        price = price_data.get("price", 0)
        change = price_data.get("change_pct", 0)
        currency = price_data.get("currency", "$")

        if final >= 6: rec = "Starkt Köp"
        elif final >= 3: rec = "Köp"
        elif final >= -3: rec = "Neutral"
        elif final >= -6: rec = "Sälj"
        else: rec = "Starkt Sälj"

        providers_used = set(agent_results.get(k, {}).get("provider_used", "rule_based") for k in weights)

        text = (
            f"{agreement} bland AI-modellerna. "
            f"{labels[strongest]}-modellen ger starkast signal ({scores[strongest]:+d}) "
            f"medan {labels[weakest]}-modellen är svagast ({scores[weakest]:+d}). "
            f"Aktuellt pris: {currency}{price:,.2f} ({change:+.2f}%). "
            f"Viktad slutpoäng: {final:+.1f}. "
            f"Rekommendation: {rec}. "
            f"(Analys via: {', '.join(providers_used)})"
        )

        return {
            "finalScore": final,
            "weights": weights,
            "supervisorText": text,
            "recommendation": rec,
            "confidence": 0.6,
            "risk_flags": [],
            "provider_used": "rule_based" if "rule_based" in providers_used else list(providers_used)[0],
        }

    def _get_optimized_weights(self) -> dict:
        """Load learned signal weights and translate to agent weights.

        Our signal optimization proved:
        - ROC 10d (97.9%) → comes from TECH agent
        - Momentum 20d (1.1%) → comes from TECH agent
        - Volatility (0.7%) → comes from MACRO agent
        - RSI (~0%) → comes from TECH agent (but irrelevant)
        - SMA cross (~0%) → comes from TECH agent (but irrelevant)

        Therefore: TECH agent should get the highest weight since
        its core signals (momentum/ROC) are the strongest predictors.
        """
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from signal_optimizer import get_signal_weights

            sw = get_signal_weights()
            if not sw or sw.get("confidence") == "low":
                return {"macro": 0.30, "micro": 0.25, "sentiment": 0.20, "tech": 0.25}

            # Translate signal importance to agent weights:
            # ROC + momentum → tech agent produces these
            # Volatility → macro agent context
            # Sentiment → independent signal (keep moderate weight)
            w = sw.get("weights", {})
            roc_w = abs(w.get("roc_10d", {}).get("weight", 0.2))
            mom_w = abs(w.get("momentum_20d", {}).get("weight", 0.1))
            vol_w = abs(w.get("volatility", {}).get("weight", 0.1))

            # Tech gets ROC + momentum contribution
            tech_raw = roc_w + mom_w
            # Macro gets volatility contribution + base
            macro_raw = vol_w + 0.15
            # Sentiment and micro get base weights
            sentiment_raw = 0.15
            micro_raw = 0.10

            total = tech_raw + macro_raw + sentiment_raw + micro_raw
            if total > 0:
                result = {
                    "tech": round(tech_raw / total, 3),
                    "macro": round(macro_raw / total, 3),
                    "sentiment": round(sentiment_raw / total, 3),
                    "micro": round(micro_raw / total, 3),
                }
                logger.info(f"  📊 Using optimized weights: {result}")
                return result

        except Exception as e:
            logger.debug(f"Signal weights not available: {e}")

        return {"macro": 0.30, "micro": 0.25, "sentiment": 0.20, "tech": 0.25}


# ============================================================
# TangoConsensusFilter: Agent consensus → MPT weight multiplier
# ============================================================

import numpy as np
from typing import Dict, List


class TangoConsensusFilter:
    """
    Tango VIX 2.6-principen: exponering = (consensus/n_agents) × MPT-vikt × (1/vol)
    Agenter som är överens = mer exponering. Oenighet = mer kassa.
    """

    def __init__(self, n_agents: int = 5):
        self.n_agents = n_agents

    def compute_consensus(self, agent_scores: Dict[str, Dict[str, float]]) -> Dict[str, Dict]:
        """
        agent_scores: {"macro": {"BTC": 7.5, "GOLD": 3.2, ...}, "micro": {...}, ...}
        Returns: per-asset consensus info
        """
        assets = set()
        for agent_data in agent_scores.values():
            assets.update(agent_data.keys())

        consensus = {}
        for asset in assets:
            scores = []
            go_count = 0
            for agent_name, agent_data in agent_scores.items():
                score = agent_data.get(asset, 0)
                scores.append(score)
                if score > 0:  # GO = positiv score
                    go_count += 1

            avg_score = np.mean(scores) if scores else 0
            std_score = np.std(scores) if scores else 0

            consensus[asset] = {
                "go_count": go_count,
                "total_agents": self.n_agents,
                "consensus_fraction": go_count / self.n_agents,
                "avg_score": round(float(avg_score), 2),
                "divergence": round(float(std_score), 2),
                "unanimous": go_count == self.n_agents or go_count == 0,
            }

        return consensus

    def apply_to_mpt_weights(
        self,
        mpt_weights: Dict[str, float],
        consensus: Dict[str, Dict],
        vol_multipliers: Dict[str, float] = None,
        vol_dampen: float = 1.0
    ) -> Dict[str, float]:
        """
        Multiplicera MPT-vikter med consensus-fraktion och vol-justering.
        Frigjort kapital går till kassa.
        """
        adjusted = {}
        freed = 0.0

        for asset, mpt_weight in mpt_weights.items():
            if asset in ("kassa", "cash", "kort_ranta"):
                adjusted[asset] = mpt_weight
                continue

            cons = consensus.get(asset, {"consensus_fraction": 0.5})
            frac = cons["consensus_fraction"]

            # Volatilitetsjustering
            vol_mult = 1.0
            if vol_multipliers and asset in vol_multipliers:
                vol_mult = vol_multipliers[asset]
            vol_adj = min(1.0 / (vol_mult * vol_dampen), 1.5)

            # Conviction boost
            avg_score = cons.get("avg_score", 0)
            conviction_mult = 1.0
            if avg_score > 5:
                conviction_mult = 1.2
            elif avg_score < -5:
                conviction_mult = 0.5

            new_weight = mpt_weight * frac * vol_adj * conviction_mult
            freed += max(0, mpt_weight - new_weight)
            adjusted[asset] = round(new_weight, 2)

        # Frigjort kapital till kassa
        adjusted["kassa"] = adjusted.get("kassa", 0) + round(freed, 2)

        return adjusted

    def detect_divergence_signal(self, consensus: Dict[str, Dict]) -> Dict:
        """
        Hög divergens mellan agenter = osäker marknad = öka kassa
        """
        divergences = [c["divergence"] for c in consensus.values()]
        avg_div = np.mean(divergences) if divergences else 0
        max_div = max(divergences) if divergences else 0

        if avg_div > 4.0:
            return {"signal": "EXTREME_DIVERGENCE", "cash_boost": 0.15,
                    "message": f"Agenter extremt oeniga (div={avg_div:.1f}). Öka kassa 15%."}
        elif avg_div > 2.5:
            return {"signal": "HIGH_DIVERGENCE", "cash_boost": 0.08,
                    "message": f"Agenter oeniga (div={avg_div:.1f}). Öka kassa 8%."}
        else:
            return {"signal": "NORMAL", "cash_boost": 0.0,
                    "message": "Normal agent-konsensus."}


# ============================================================
# AdaptiveAgentWeights: Exponential decay weighting
# ============================================================

class AdaptiveAgentWeights:
    """
    Vikter som automatiskt justeras baserat på senaste prestanda.
    Senaste 30 dagars träffsäkerhet väger mer än 90 dagars.
    Första 20 prediktionerna: lika vikter (för lite data).
    """

    def __init__(self, n_agents: int = 5, decay_factor: float = 0.95):
        self.n_agents = n_agents
        self.decay = decay_factor
        self.base_weight = 1.0 / n_agents

    def compute_weights(self, performance_history: Dict[str, list]) -> Dict[str, float]:
        """
        performance_history: {
            "macro": [{"date": "2026-03-01", "correct": True}, ...],
            "micro": [...], ...
        }
        """
        weights = {}
        total_score = 0

        for agent, history in performance_history.items():
            if len(history) < 20:
                weights[agent] = self.base_weight
                total_score += self.base_weight
                continue

            # Exponentiell nedgång: senaste observationer väger mer
            score = 0
            weight_sum = 0
            for i, entry in enumerate(reversed(history)):
                decay_weight = self.decay ** i
                score += decay_weight * (1.0 if entry["correct"] else 0.0)
                weight_sum += decay_weight

            agent_accuracy = score / weight_sum if weight_sum > 0 else 0.5

            # Transformera till vikt (min 0.1, max 0.4 för 5 agenter)
            agent_weight = max(0.1, min(0.4, agent_accuracy))
            weights[agent] = agent_weight
            total_score += agent_weight

        # Normalisera så summan = 1.0
        if total_score > 0:
            weights = {a: round(w / total_score, 4) for a, w in weights.items()}

        return weights

    def apply_weights(self, agent_scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """Beräkna viktat consensus-score"""
        total = 0
        for agent, score in agent_scores.items():
            w = weights.get(agent, self.base_weight)
            total += score * w
        return round(total, 2)
