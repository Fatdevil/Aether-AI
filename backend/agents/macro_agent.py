"""
Macro Analyst Agent - Evaluates monetary policy, global liquidity, and macro trends.
Primary provider: OpenAI GPT-4o
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm_tiered, parse_llm_json

logger = logging.getLogger("aether.agents.macro")

SYSTEM_PROMPT = """Du är en erfaren MAKROANALYTIKER specialiserad på global makroekonomi och finansmarknader.

Din uppgift är att analysera en specifik tillgång ur ett makroperspektiv och ge ett poäng från -10 till +10.

MAKROPERSPEKTIV inkluderar:
- Penningpolitik (Fed, ECB, BoJ): Ränteläge, QE/QT, forward guidance
- Global likviditet: M2-tillväxt, kreditcykeln, finansiella förhållanden
- Inflation: CPI, PCE, inflationsförväntningar
- Tillväxt: BNP, PMI, arbetsmarknad, consumer confidence
- Geopolitik: Handelskonflikter, sanktioner, krig, politisk instabilitet
- Valutatrender: DXY, carry trades, valutakrig
- Räntemarknad: Yieldkurvan, credit spreads, statsobligationer

POÄNGSÄTTNING:
- +8 till +10: Extremt gynnsam makromiljö, stark risk-on
- +5 till +7: Positiv makrobild, stödjande förhållanden
- +1 till +4: Svagt positiv, viss medvind
- -1 till +1: Neutral, blandade signaler
- -4 till -1: Svagt negativ, viss motvind
- -7 till -4: Negativ makrobild, riskaverta förhållanden
- -10 till -7: Extremt ogynnsam, systemrisk

Du MÅSTE svara med ENBART giltig JSON:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar med din makroanalys>",
    "key_factors": ["faktor1", "faktor2", "faktor3"]
}"""


class MacroAgent(BaseAgent):
    name = "Makro-Analytiker"
    perspective = "Makro"

    def __init__(self):
        pass  # Uses call_llm_tiered — no fixed provider needed

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        price_ctx = self._format_price_context(price_data)
        news_ctx = self._format_news_context(
            [n for n in news_items if n.get("category") in ["Makro", "Räntor", category]]
        )

        user_prompt = f"""Analysera följande tillgång ur ett MAKROPERSPEKTIV:

Tillgång: {asset_name}
Kategori: {category}
{price_ctx}

Relevanta nyheter:
{news_ctx}
{perf_context}

Ge din makro-bedömning som JSON."""

        response, provider_used = await call_llm_tiered(
            tier=1,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=400,
        )
        
        # Diagnostic logging to find why agents always fall back to rule_based
        if response:
            logger.info(f"🔍 MACRO {asset_id}: Got response ({len(response)} chars) from {provider_used}")
            logger.info(f"🔍 MACRO {asset_id}: First 300 chars: {response[:300]}")
        else:
            logger.warning(f"🔍 MACRO {asset_id}: response=None from {provider_used}")
        
        result = parse_llm_json(response)
        
        if result:
            logger.info(f"🔍 MACRO {asset_id}: Parsed OK, keys={list(result.keys())}")
        else:
            logger.warning(f"🔍 MACRO {asset_id}: parse_llm_json returned None")

        if result and "score" in result:
            return {
                "score": self._clamp_score(int(result["score"])),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", ""),
                "key_factors": result.get("key_factors", []),
                "provider_used": provider_used,
            }

        # Fallback to rule-based
        logger.warning(f"🔍 MACRO {asset_id}: Falling back to rule_based (result={result is not None}, has_score={'score' in result if result else False})")
        return self._rule_based_fallback(asset_id, price_data, news_items)

    def _rule_based_fallback(self, asset_id, price_data, news_items):
        change = price_data.get("change_pct", 0)
        price = price_data.get("price", 0)
        currency = price_data.get("currency", "$")
        score = 0
        reasoning_parts = []
        key_factors = []

        # Price momentum
        if change > 2:
            score += 3
            reasoning_parts.append(f"Stark positiv prisrörelse ({change:+.2f}%) signalerar risk-on i makromiljön.")
            key_factors.append(f"momentum {change:+.1f}%")
        elif change > 0.5:
            score += 1
            reasoning_parts.append(f"Svagt positiv prisrörelse ({change:+.2f}%) indikerar försiktig optimism.")
            key_factors.append(f"momentum {change:+.1f}%")
        elif change < -2:
            score -= 3
            reasoning_parts.append(f"Kraftigt prisfall ({change:+.2f}%) tyder på makrostress och risk-off sentiment.")
            key_factors.append(f"säljpress {change:+.1f}%")
        elif change < -0.5:
            score -= 1
            reasoning_parts.append(f"Svagt negativt momentum ({change:+.2f}%) speglar viss makroosäkerhet.")
            key_factors.append(f"svag trend {change:+.1f}%")
        else:
            reasoning_parts.append(f"Priset är relativt oförändrat ({change:+.2f}%), marknaden avvaktar.")
            key_factors.append("sidledes rörelse")

        # News sentiment
        pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
        neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
        total = len(news_items)
        score += min(3, pos - neg)

        if neg > pos * 2:
            reasoning_parts.append(f"Nyhetsflödet är kraftigt negativt ({neg} negativa vs {pos} positiva av {total} nyheter) – skapar motvind.")
            key_factors.append(f"{neg} neg. nyheter")
        elif neg > pos:
            reasoning_parts.append(f"Övervägande negativt nyhetssentiment ({neg} neg. vs {pos} pos. av {total}) ger negativ undertone.")
            key_factors.append("negativt sentiment")
        elif pos > neg * 2:
            reasoning_parts.append(f"Starkt positivt nyhetsflöde ({pos} positiva vs {neg} neg.) stödjer risk-on.")
            key_factors.append(f"{pos} pos. nyheter")
        elif pos > neg:
            reasoning_parts.append(f"Övervägande positivt sentiment i nyhetsflödet ({pos} pos. vs {neg} neg.).")
            key_factors.append("positivt sentiment")
        else:
            reasoning_parts.append(f"Nyhetsflödet är blandat ({pos} pos., {neg} neg. av {total}).")
            key_factors.append("blandat nyhetsflöde")

        # Asset-specific macro context
        macro_context = {
            "btc": "Bitcoin påverkas av likviditetstrender och realräntor. Svagare dollar gynnar BTC.",
            "sp500": "S&P 500 drivs av Fed-politik, vinster och kreditvillkor. Yieldkurvan är nyckelindikator.",
            "gold": "Guld gynnas av negativa realräntor, geopolitisk osäkerhet och centralbanksinköp.",
            "silver": "Silver följer guld men har industriell komponent. Känsligare för konjunkturcykeln.",
            "oil": "Olja styrs av OPEC-beslut, global efterfrågan (PMI) och geopolitiska risker i Mellanöstern.",
            "us10y": "10Y-räntan reflekterar inflationsförväntningar och Fed:s penningpolitik.",
            "eurusd": "EUR/USD drivs av räntedifferens (Fed vs ECB), handelsbalanser och riskaptit.",
            "global-equity": "ACWI speglar global riskvilja – påverkas av alla stora centralbanker och geopolitik.",
        }
        if asset_id in macro_context:
            reasoning_parts.append(macro_context[asset_id])
            key_factors.append("makromiljö")

        bias = {"btc": 1, "gold": 2, "silver": 1, "global-equity": 2,
                "sp500": 2, "eurusd": 0, "oil": -1, "us10y": -2}
        score += bias.get(asset_id, 0)

        return {
            "score": self._clamp_score(score),
            "confidence": min(0.65, 0.4 + total * 0.01),  # Higher confidence with more news
            "reasoning": " ".join(reasoning_parts),
            "key_factors": key_factors[:5],
            "provider_used": "rule_based",
        }
