"""
Technical Analyst Agent - Evaluates price action, momentum, and chart patterns.
Primary provider: Anthropic Claude
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm_tiered, parse_llm_json

logger = logging.getLogger("aether.agents.tech")

SYSTEM_PROMPT = """Du är en TEKNISK ANALYTIKER specialiserad på prisanalys och tekniska indikatorer.

Analysera en tillgång ur ett TEKNISKT perspektiv. Ge poäng -10 till +10.

TEKNISKA FAKTORER:
- Prismomentum: Kortsiktig och medelfristig trend (daglig, vecka, månad)
- RSI: Överköpt (>70) vs översålt (<30)
- MACD: Signal, histogram, korsningar
- Glidande medelvärden: 50-dagars, 200-dagars, Golden/Death Cross
- Stöd/Motstånd: Nyckelzoner, breakouts, breakdowns
- Volym: Volymtrender, on-balance volume
- Bollinger Bands: Position relativt banden, squeeze
- Elliott Wave / Fibonacci: Vågposition, retracement-nivåer
- Volatilitet: ATR, historisk vs implicit volatilitet

POÄNGSÄTTNING:
+8 till +10: Stark teknisk uppsida, breakout, starkt momentum
+5 till +7: Positiv trend, konstruktiv prisstruktur
+1 till +4: Svagt positivt, neutral med bias uppåt
-1 till +1: Helt neutral, ingen tydlig riktning
-4 till -1: Svagt negativt, svag trend
-7 till -4: Negativt, breakdown-risk, fallande momentum
-10 till -7: Stark teknisk nedsida, sälj-signaler

JSON-svar:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar>",
    "key_factors": ["faktor1", "faktor2", "faktor3"]
}"""


class TechnicalAgent(BaseAgent):
    name = "Teknisk Analytiker"
    perspective = "Teknisk"

    def __init__(self):
        pass  # Uses call_llm_tiered — no fixed provider needed

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        price_ctx = self._format_price_context(price_data)

        user_prompt = f"""Teknisk analys av:

Tillgång: {asset_name}
Kategori: {category}
{price_ctx}

Baserat på den dagliga prisaktionen, bedöm teknisk styrka/svaghet.
{perf_context}
Ge ditt JSON-svar."""

        response, provider_used = await call_llm_tiered(
            tier=1,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
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

        return self._rule_based_fallback(asset_id, price_data)

    def _rule_based_fallback(self, asset_id, price_data):
        change = price_data.get("change_pct", 0)
        price = price_data.get("price", 0)
        score = 0
        reasoning_parts = []
        key_factors = []

        # Price momentum score
        if change > 2:
            score += 5
            reasoning_parts.append(f"Stark upptrend med {change:+.2f}% daglig rörelse.")
        elif change > 0.5:
            score += 2
            reasoning_parts.append(f"Positiv daglig rörelse ({change:+.2f}%).")
        elif change > -0.5:
            score += 0
            reasoning_parts.append(f"Sidledes handel ({change:+.2f}%) utan tydlig riktning.")
        elif change > -2:
            score -= 2
            reasoning_parts.append(f"Svag nedtrend ({change:+.2f}%).")
        else:
            score -= 5
            reasoning_parts.append(f"Kraftig nedgång ({change:+.2f}%) – teknisk signal starkt negativ.")

        key_factors.append(f"dagsförändring {change:+.1f}%")

        # Use technical indicators if available in price_data
        indicators = price_data.get("indicators", {})

        # RSI analysis
        rsi = indicators.get("rsi_14")
        if rsi:
            if rsi >= 70:
                reasoning_parts.append(f"RSI(14) på {rsi:.1f} – överköpt territorium, risk för rekyl nedåt.")
                key_factors.append(f"RSI {rsi:.0f} överköpt")
                score -= 1
            elif rsi >= 60:
                reasoning_parts.append(f"RSI(14) på {rsi:.1f} – starkt momentum, men närmar sig överköpt.")
                key_factors.append(f"RSI {rsi:.0f} stark")
            elif rsi <= 30:
                reasoning_parts.append(f"RSI(14) på {rsi:.1f} – översåld, potentiell botten eller studs.")
                key_factors.append(f"RSI {rsi:.0f} översåld")
                score += 1
            elif rsi <= 40:
                reasoning_parts.append(f"RSI(14) på {rsi:.1f} – svagt momentum, nära översålt.")
                key_factors.append(f"RSI {rsi:.0f} svag")
            else:
                reasoning_parts.append(f"RSI(14) på {rsi:.1f} – neutralt momentum.")
                key_factors.append(f"RSI {rsi:.0f}")

        # MACD analysis
        macd = indicators.get("macd", {})
        if macd:
            crossover = macd.get("crossover", "none")
            bullish = macd.get("bullish", False)
            if crossover == "bullish_cross":
                reasoning_parts.append("MACD har gjort en bullish crossover – köpsignal.")
                key_factors.append("MACD köp-kors")
                score += 2
            elif crossover == "bearish_cross":
                reasoning_parts.append("MACD har gjort en bearish crossover – säljsignal.")
                key_factors.append("MACD sälj-kors")
                score -= 2
            elif bullish:
                reasoning_parts.append("MACD-histogram är positivt – bekräftar upptrend.")
                key_factors.append("MACD positiv")
            else:
                reasoning_parts.append("MACD-histogram är negativt – bekräftar nedtrend.")
                key_factors.append("MACD negativ")

        # SMA trend
        sma_20_vs = indicators.get("price_vs_sma20")
        sma_50_vs = indicators.get("price_vs_sma50")
        if sma_20_vs is not None and sma_50_vs is not None:
            if sma_20_vs > 0 and sma_50_vs > 0:
                reasoning_parts.append(f"Pris över SMA20 ({sma_20_vs:+.1f}%) och SMA50 ({sma_50_vs:+.1f}%) – upptrend intakt.")
                key_factors.append("ovan SMA20/50")
            elif sma_20_vs < 0 and sma_50_vs < 0:
                reasoning_parts.append(f"Pris under SMA20 ({sma_20_vs:+.1f}%) och SMA50 ({sma_50_vs:+.1f}%) – nedtrend intakt.")
                key_factors.append("under SMA20/50")
        elif sma_20_vs is not None:
            pos = "över" if sma_20_vs > 0 else "under"
            reasoning_parts.append(f"Pris {pos} SMA20 ({sma_20_vs:+.1f}%).")

        # Golden/Death cross
        if indicators.get("golden_cross"):
            reasoning_parts.append("Golden cross aktiv (SMA50 > SMA200) – långsiktigt bullish.")
            key_factors.append("golden cross")
        elif indicators.get("death_cross"):
            reasoning_parts.append("Death cross aktiv (SMA50 < SMA200) – långsiktigt bearish.")
            key_factors.append("death cross")

        # Fallback if no indicators available
        if not indicators:
            reasoning_parts.append("Inga tekniska indikatorer tillgängliga ännu – analys baserad enbart på prisrörelse.")

        bias = {"btc": 2, "gold": 1, "silver": 1, "global-equity": 1,
                "sp500": 2, "eurusd": -1, "oil": -1, "us10y": -3}
        score += bias.get(asset_id, 0)

        return {
            "score": self._clamp_score(score),
            "confidence": 0.6 if indicators else 0.4,
            "reasoning": " ".join(reasoning_parts),
            "key_factors": key_factors[:6],
            "provider_used": "rule_based",
        }
