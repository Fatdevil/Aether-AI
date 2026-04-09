"""
Sentiment Analyst Agent - Analyzes news sentiment and market mood.
Uses rule-based keyword analysis as primary (fast), LLM as enhancement.
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm, parse_llm_json

logger = logging.getLogger("aether.agents.sentiment")

SYSTEM_PROMPT = """Du är en SENTIMENTANALYTIKER som bedömer marknadshumör och nyhetssentiment.

Analysera nyheterna och deras påverkan på en given tillgång. Ge poäng -10 till +10.

SENTIMENTFAKTORER:
- Nyhetssentiment: Andel positiva vs negativa nyheter kring tillgången
- Social media: Generellt marknadshumör, Twitter/X sentiment, Reddit diskussioner
- Fear & Greed Index: Aktuellt riskhumör på marknaderna
- Positionering: Retail vs institutional sentiment
- Konträrindikator: Extremt sentiment kan vara konträrt (panic selling = köpläge)
- Narrativ: Vilka berättelser driver marknaden? Styrkan i rådande narrativ

POÄNGSÄTTNING: -10 (extrem rädsla/negativism) till +10 (extrem girighet/optimism)

Svara med ENBART JSON:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar>",
    "key_factors": ["faktor1", "faktor2", "faktor3"]
}"""


class SentimentAgent(BaseAgent):
    name = "Sentiment-Analytiker"
    perspective = "Sentiment"

    def __init__(self):
        # Sentiment uses rule-based by default (fast) but can enhance with LLM
        self.provider = os.getenv("SENTIMENT_AGENT_PROVIDER", "rule_based")

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        # Always compute rule-based sentiment first (instant)
        rule_result = self._rule_based_analysis(asset_id, news_items)

        # If LLM provider configured, enhance with deeper analysis
        if self.provider != "rule_based":
            llm_result = await self._llm_analysis(
                asset_id, asset_name, category, price_data, news_items
            )
            if llm_result:
                return llm_result

        return rule_result

    async def _llm_analysis(self, asset_id, asset_name, category, price_data, news_items):
        price_ctx = self._format_price_context(price_data)
        news_ctx = self._format_news_context(news_items, max_items=12)

        # Add quantitative sentiment from Marketaux entity data
        mx_scores = self._extract_entity_sentiments(news_items, asset_id)
        quant_ctx = ""
        if mx_scores:
            avg = sum(mx_scores) / len(mx_scores)
            quant_ctx = f"""
Kvantitativ sentimentdata (Marketaux, {len(mx_scores)} mätpunkter):
- Genomsnittlig entity-sentiment: {avg:.3f} (skala -1 till +1)
- Mest positiva: {max(mx_scores):.3f}
- Mest negativa: {min(mx_scores):.3f}"""

        user_prompt = f"""Analysera SENTIMENT för:

Tillgång: {asset_name}
Kategori: {category}
{price_ctx}
{quant_ctx}

Alla tillgängliga nyheter:
{news_ctx}

Bedöm det övergripande sentimentet kring denna tillgång och ge ditt JSON-svar."""

        response = await call_llm(self.provider, SYSTEM_PROMPT, user_prompt)
        result = parse_llm_json(response)

        if result and "score" in result:
            return {
                "score": self._clamp_score(int(result["score"])),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", ""),
                "key_factors": result.get("key_factors", []),
                "provider_used": self.provider,
            }
        return None

    def _extract_entity_sentiments(self, news_items, asset_id):
        """Extract Marketaux entity-level sentiment scores for this asset."""
        scores = []
        # Map asset_id to common ticker symbols
        asset_tickers = {
            "btc": ["BTC", "BITCOIN"], "gold": ["XAU", "GLD", "GOLD"],
            "silver": ["XAG", "SLV", "SILVER"], "oil": ["CL", "OIL", "BRENT"],
            "sp500": ["SPY", "SPX", "S&P"], "global-equity": ["ACWI", "VT"],
            "eurusd": ["EUR", "EURUSD"], "us10y": ["TNX", "TLT"],
        }
        relevant_symbols = asset_tickers.get(asset_id, [asset_id.upper()])

        for item in news_items:
            for es in item.get("entity_sentiments", []):
                symbol = es.get("symbol", "").upper()
                if any(sym in symbol for sym in relevant_symbols):
                    scores.append(es.get("score", 0))
        return scores

    def _rule_based_analysis(self, asset_id, news_items):
        if not news_items:
            return {
                "score": 0, "confidence": 0.3,
                "reasoning": "Inga nyheter tillgängliga för sentimentanalys.",
                "key_factors": ["data_brist"], "provider_used": "rule_based",
            }

        # Try quantitative sentiment from Marketaux first
        mx_scores = self._extract_entity_sentiments(news_items, asset_id)
        if mx_scores:
            avg = sum(mx_scores) / len(mx_scores)
            # Scale from [-1, 1] to [-10, 10]
            score = int(avg * 10)
            confidence = min(0.9, 0.5 + len(mx_scores) * 0.05)

            reasoning_parts = [
                f"Marketaux-sentimentdata: {len(mx_scores)} mätpunkter, genomsnitt {avg:.3f}."
            ]
            if avg > 0.2:
                reasoning_parts.append("Tydligt positivt nyhetssentiment kring tillgången.")
            elif avg < -0.2:
                reasoning_parts.append("Tydligt negativt nyhetssentiment kring tillgången.")
            else:
                reasoning_parts.append("Blandat/neutralt nyhetssentiment.")

            return {
                "score": self._clamp_score(score),
                "confidence": confidence,
                "reasoning": " ".join(reasoning_parts),
                "key_factors": [
                    f"entity_sentiment: {avg:.3f}",
                    f"{len(mx_scores)} datapunkter",
                    f"max: {max(mx_scores):.3f}, min: {min(mx_scores):.3f}",
                ],
                "provider_used": "marketaux_quantitative",
            }

        # Fallback to keyword-based — BUT filter news per asset first
        asset_keywords = {
            "btc": ["bitcoin", "btc", "crypto", "krypto", "halvering", "halving", "satoshi", "mining"],
            "gold": ["gold", "guld", "xau", "precious metal", "ädelmetall", "bullion"],
            "silver": ["silver", "xag", "precious metal", "ädelmetall"],
            "oil": ["oil", "olja", "brent", "crude", "opec", "petroleum", "barrel", "fat"],
            "sp500": ["s&p", "sp500", "wall street", "nasdaq", "dow jones", "aktie", "stock", "equity"],
            "global-equity": ["global", "msci", "acwi", "emerging", "developed", "world market"],
            "eurusd": ["euro", "eur/usd", "eurusd", "dollar", "forex", "valuta", "ecb"],
            "us10y": ["treasury", "yield", "ränta", "bond", "obligation", "10-year", "10y", "fed fund"],
        }

        keywords = asset_keywords.get(asset_id, [asset_id])

        # Filter: only count news relevant to this asset
        relevant_news = []
        for n in news_items:
            text = (n.get("title", "") + " " + n.get("summary", "")).lower()
            if any(kw in text for kw in keywords):
                relevant_news.append(n)

        # If no asset-specific news found, use all news but with lower confidence
        if relevant_news:
            items_to_score = relevant_news
            base_confidence = 0.5
        else:
            items_to_score = news_items
            base_confidence = 0.3  # Lower confidence for unfiltered

        pos = sum(1 for n in items_to_score if n.get("sentiment") == "positive")
        neg = sum(1 for n in items_to_score if n.get("sentiment") == "negative")
        total = len(items_to_score)

        ratio = (pos - neg) / total if total > 0 else 0
        score = int(ratio * 8)

        bias = {"btc": 2, "gold": 1, "silver": 0, "global-equity": 1,
                "sp500": 1, "eurusd": 0, "oil": -1, "us10y": -2}
        score += bias.get(asset_id, 0)

        reasoning_parts = []
        filter_note = f" (av {len(news_items)} totalt)" if len(items_to_score) != len(news_items) else ""
        if pos > neg:
            reasoning_parts.append(f"{pos} positiva vs {neg} negativa av {total} relevanta nyheter{filter_note} ger positivt sentiment.")
        elif neg > pos:
            reasoning_parts.append(f"{neg} negativa vs {pos} positiva av {total} relevanta nyheter{filter_note} ger negativt sentiment.")
        else:
            reasoning_parts.append(f"Balanserat nyhetsflöde bland {total} relevanta nyheter{filter_note}.")

        return {
            "score": self._clamp_score(score),
            "confidence": min(0.8, base_confidence + total * 0.05),
            "reasoning": " ".join(reasoning_parts),
            "key_factors": [f"{pos} positiva", f"{neg} negativa", f"{total} relevanta av {len(news_items)}"],
            "provider_used": "rule_based",
        }


# ============================================================
# SentimentPaceTracker: Sentiment velocity indicator
# ============================================================

from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List


class SentimentPaceTracker:
    """
    Mäter HASTIGHET av sentimentförändring.
    50 negativa rubriker/dag → 5 = avspänningssignal INNAN priset rör sig.
    """

    def __init__(self, window_days: int = 7):
        self.history: deque = deque(maxlen=window_days * 50)  # Max 50 artiklar/dag
        self.window_days = window_days

    def add_articles(self, articles: List[Dict]):
        """
        Lägg till artiklar: [{"timestamp": ..., "sentiment": -0.8, "title": "..."}]
        """
        for article in articles:
            ts = article.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    ts = datetime.now()
            elif not isinstance(ts, datetime):
                ts = datetime.now()

            self.history.append({
                "timestamp": ts,
                "sentiment": article.get("sentiment", 0),
            })

    def compute_pace(self) -> Dict:
        """Beräkna sentiment-pace"""
        if len(self.history) < 5:
            return {"pace": "INSUFFICIENT_DATA", "score": 0, "message": "För få artiklar"}

        now = datetime.now()
        recent = [h for h in self.history if (now - h["timestamp"]).days <= 1]
        older = [h for h in self.history if 1 < (now - h["timestamp"]).days <= 3]

        if not recent or not older:
            return {"pace": "STABLE", "score": 0, "message": "Stabilt nyhetsflöde"}

        recent_avg = sum(h["sentiment"] for h in recent) / len(recent)
        older_avg = sum(h["sentiment"] for h in older) / len(older)
        recent_volume = len(recent)
        older_volume = len(older) / 2  # Normalisera för 2 dagar

        sentiment_change = recent_avg - older_avg
        volume_change = (recent_volume - older_volume) / (older_volume + 1)

        # Pace score: -10 (snabbt försämras) till +10 (snabbt förbättras)
        pace_score = sentiment_change * 5 + volume_change * 2
        pace_score = max(-10, min(10, pace_score))

        if pace_score > 3:
            pace = "IMPROVING"
        elif pace_score > 1:
            pace = "SLOWLY_IMPROVING"
        elif pace_score > -1:
            pace = "STABLE"
        elif pace_score > -3:
            pace = "SLOWLY_DETERIORATING"
        else:
            pace = "RAPIDLY_DETERIORATING"

        return {
            "pace": pace,
            "score": round(pace_score, 2),
            "recent_sentiment": round(recent_avg, 3),
            "older_sentiment": round(older_avg, 3),
            "volume_today": recent_volume,
            "volume_avg": round(older_volume, 1),
            "message": (
                f"Sentiment {pace.lower()}: {recent_avg:.2f} vs {older_avg:.2f}, "
                f"volym {recent_volume} artiklar"
            )
        }
