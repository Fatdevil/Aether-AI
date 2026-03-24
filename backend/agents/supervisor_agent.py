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

Din uppgift är att:
1. UTVÄRDERA de 4 underliggande AI-analytikernas bedömningar (Makro, Mikro, Sentiment, Teknisk)
2. VIKTA dem baserat på deras relevans, confidence och inbördes konsistens
3. GENERERA ett transparent och förklarande slutvärde (-10 till +10)

VÄGLEDNING FÖR VIKTNING:
- Om alla analytiker är överens: Ge hög confidence till slutvärdet
- Om stor oenighet: Vikta analytikern med högst confidence tyngst
- Konträr analys: Om 3 av 4 är positiva men sentiment är extremt negativt, överväg konträreffekt
- Kategorispecifik viktning: Mäklarperspektiv viktigare för aktier, on-chain för krypto
- Extremvärden: Ifrågasätt extremvärden – är de motiverade av data eller bias?

FORMAT FÖR SVAR (JSON):
{
    "final_score": <float -10.0 till 10.0, en decimal>,
    "weights_applied": {
        "macro": <float 0-1>,
        "micro": <float 0-1>,
        "sentiment": <float 0-1>,
        "tech": <float 0-1>
    },
    "supervisor_text": "<3-5 meningar transparent motivering på SVENSKA. Inkludera: vilka modeller som drev slutvärdet, eventuella konflikter, och din slutliga rekommendation. Nämn specifika priser och poäng.>",
    "recommendation": "<Starkt Köp | Köp | Neutral | Sälj | Starkt Sälj>",
    "confidence": <float 0.0 till 1.0>,
    "risk_flags": ["ev. riskflagga1", "ev. riskflagga2"]
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
    ) -> dict:
        """
        Evaluate the outputs from all 4 agents and produce final assessment.
        agent_results: {"macro": {...}, "micro": {...}, "sentiment": {...}, "tech": {...}}
        """
        if self.provider == "rule_based":
            return self._rule_based_evaluate(asset_id, asset_name, price_data, agent_results)

        # Build context for LLM
        price_ctx = self._format_price_context(price_data)
        agent_summary = self._format_agent_results(agent_results)

        user_prompt = f"""SUPERVISOR-UTVÄRDERING för {asset_name} ({category})

{price_ctx}

ANALYTIKERNAS BEDÖMNINGAR:
{agent_summary}

Utvärdera dessa 4 bedömningar. Var transparent om hur du viktar dem.
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

