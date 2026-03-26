"""
Supervisor Agent - The "smartest AI" that evaluates and weighs the other agents.
Primary provider: OpenAI GPT-4o (or best available)
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm, parse_llm_json, get_available_providers

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
        pref = os.getenv("SUPERVISOR_AGENT_PROVIDER", "openai")
        available = get_available_providers()
        # Supervisor uses the best available provider
        if pref in available:
            self.provider = pref
        elif available:
            self.provider = available[0]
        else:
            self.provider = "rule_based"

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

        response = await call_llm(self.provider, SYSTEM_PROMPT, user_prompt, temperature=0.2)
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
                "provider_used": self.provider,
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
