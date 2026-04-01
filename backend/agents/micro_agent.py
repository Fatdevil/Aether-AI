"""
Micro Analyst Agent - Evaluates supply/demand, fundamentals, on-chain data.
Primary provider: Google Gemini
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm_tiered, parse_llm_json

logger = logging.getLogger("aether.agents.micro")

SYSTEM_PROMPT = """Du är en specialiserad MIKROANALYTIKER fokuserad på tillgångsspecifika fundamenta.

Din uppgift är att analysera en tillgång ur ett MIKROPERSPEKTIV och ge poäng -10 till +10.

MIKROPERSPEKTIV inkluderar:
- Utbud/efterfrågan: Produktionsdata, lager, flöden
- On-chain data (för krypto): Active addresses, exchange flows, whale activity, hash rate
- Företagsfundamenta (för aktier): P/E, tillväxttakt, marginaler, skuldsättning
- Sektorrotation: Kapitalflöden mellan sektorer och tillgångsklasser
- Positionering: Spekulativ positionering (COT-data), funding rates
- Teknisk marknadsstruktur: Likviditet, market depth, bid-ask spreads

POÄNGSÄTTNING: -10 (extremt svag fundamental bild) till +10 (extremt stark)

Svara med ENBART JSON:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar>",
    "key_factors": ["faktor1", "faktor2", "faktor3"]
}"""


class MicroAgent(BaseAgent):
    name = "Mikro-Analytiker"
    perspective = "Mikro"

    def __init__(self):
        pass  # Uses call_llm_tiered — no fixed provider needed

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        price_ctx = self._format_price_context(price_data)
        category_news = [n for n in news_items if n.get("category") == category]
        news_ctx = self._format_news_context(category_news or news_items[:5])

        user_prompt = f"""Analysera ur MIKROPERSPEKTIV:

Tillgång: {asset_name} (ID: {asset_id})
Kategori: {category}
{price_ctx}

Relevanta nyheter:
{news_ctx}
{perf_context}

Ge din mikro-bedömning som JSON."""

        response, provider_used = await call_llm_tiered(
            tier=1,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=400,
        )
        result = parse_llm_json(response)

        if result and "score" in result:
            return {
                "score": self._clamp_score(int(result["score"])),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", ""),
                "key_factors": result.get("key_factors", []),
                "provider_used": provider_used,
            }

        return self._rule_based_fallback(asset_id, price_data, news_items)

    def _rule_based_fallback(self, asset_id, price_data, news_items):
        change = price_data.get("change_pct", 0)
        price = price_data.get("price", 0)
        score = 0
        reasoning_parts = []
        key_factors = []

        # Price momentum analysis
        if change > 3:
            score += 4
            reasoning_parts.append(f"Kraftig uppgång på {change:+.2f}% signalerar starkt köpintresse och positiv mikrostruktur.")
            key_factors.append(f"stark uppgång {change:+.1f}%")
        elif change > 1:
            score += 2
            reasoning_parts.append(f"Positiv prisrörelse ({change:+.2f}%) tyder på ökande efterfrågan.")
            key_factors.append(f"ökad efterfrågan")
        elif change < -3:
            score -= 4
            reasoning_parts.append(f"Kraftigt fall ({change:+.2f}%) indikerar svag mikrostruktur och säljpress.")
            key_factors.append(f"säljpress {change:+.1f}%")
        elif change < -1:
            score -= 2
            reasoning_parts.append(f"Negativt momentum ({change:+.2f}%) pekar på vikande efterfrågan.")
            key_factors.append(f"svag efterfrågan")
        else:
            reasoning_parts.append(f"Begränsad prisrörelse ({change:+.2f}%) – avvaktande marknad.")
            key_factors.append("konsolidering")

        # Asset-specific micro analysis
        micro_context = {
            "btc": f"Bitcoin handlas vid ${price:,.0f}. On-chain-indikatorer som whale-ackumulering, exchange flows och mining-hashrate ger insikt om utbudspress. Halverings-cykeln och institutionellt intresse (ETF-flöden) är drivande faktorer.",
            "sp500": f"S&P 500 på {price:,.0f}. Bolagsvinster (EPS-tillväxt), aktieåterköp och insiderhandel styr den fundamentala värderingen. PE-multipelexpansion vs kontraktion.",
            "gold": f"Guld vid ${price:,.0f}/oz. Centralbankers nettoinköp (spec. Kina, Indien) driver den fysiska efterfrågan uppåt. ETF-flöden visar institutionellt sentiment.",
            "silver": f"Silver vid ${price:,.2f}/oz. Industriell efterfrågan (solpaneler, elektronik) utgör ~50% av förbrukningen. Solar-boom driver strukturell efterfrågan.",
            "oil": f"Brent-olja vid ${price:,.2f}/fat. OPEC+ produktionskvoter, amerikanska lager (EIA) och raffinaderi-utnyttjandegrad styr utbudsbalansen.",
            "us10y": f"10Y på {price:.2f}%. Auktionsresultat, utländska innehav (Japan, Kina) och duration-risk i obligationsportföljer påverkar marknaden.",
            "eurusd": f"EUR/USD vid {price:.4f}. ECB vs Fed räntedifferens, handelsbalans och kapitalkonto-flöden driver kursen.",
            "global-equity": f"ACWI vid ${price:,.2f}. Globala EPS-estimat, cross-border-flöden och EM vs DM-differentiering styr allokeringen.",
        }
        if asset_id in micro_context:
            reasoning_parts.append(micro_context[asset_id])

        bias = {"btc": 3, "gold": 0, "silver": 2, "global-equity": 1,
                "sp500": 1, "eurusd": 0, "oil": -2, "us10y": -1}
        score += bias.get(asset_id, 0)

        key_factors.append("utbuds/efterfrågan" if asset_id in ("oil", "gold", "silver") else "fundamentalt")

        return {
            "score": self._clamp_score(score),
            "confidence": 0.55,
            "reasoning": " ".join(reasoning_parts),
            "key_factors": key_factors[:5],
            "provider_used": "rule_based",
        }
