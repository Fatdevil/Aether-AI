"""
Sector Analyst Agent - Evaluates sectors based on macro environment.
Understands which macro drivers favour which sectors.
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm, parse_llm_json

logger = logging.getLogger("aether.agents.sector")

SYSTEM_PROMPT = """Du är en SEKTORANALYTIKER specialiserad på sektorrotation och branschanalys.

Din uppgift är att analysera en specifik BÖRSSEKTOR utifrån makromiljön och ge poäng -10 till +10.

NYCKELINSIKTER FÖR SEKTORROTATION:
- TEKNOLOGI: Gynnas av låga räntor, AI-boom, stark innovation. Missgynnas av räntehöjningar.
- FINANS/BANKER: Gynnas av HÖGA räntor (bredare marginaler), brant yieldkurva. Missgynnas av inverterad kurva, recession.
- FÖRSVAR: Gynnas av geopolitisk spänning, krig, ökade försvarsbudgetar. Relativt okänslig för konjunktur.
- ENERGI: Starkt kopplad till oljepris, OPEC-beslut. Gynnas av inflation och utbudsbrist.
- HÄLSOVÅRD: Defensiv sektor. Gynnas av demografisk utveckling, GLP-1-revolutionen. Relativt stabil.
- SÄLLANKÖP: Cyklisk – gynnas av stark konsument, låg arbetslöshet. Missgynnas av recession.
- DAGLIGVAROR: Defensiv – outperformar i recession. Underperformar i risk-on-miljö.
- INDUSTRI: Kopplad till PMI/ISM, global handel, infrastruktur. Cyklisk.
- MATERIAL: Kopplad till råvarupriser, Kinas efterfrågan. Cyklisk.
- FASTIGHETER: Extremt räntekänslig (negativt). Gynnas av räntesänkningar.
- KRAFTFÖRSÖRJNING: Defensiv, obligationsproxy. Gynnas av låga räntor. AI-datacenter ökar elefterfrågan.
- KOMMUNIKATION: Kopplad till annonsmarknad, streaming, AI-integration.

POÄNGSÄTTNING: -10 (extremt ogynnsam sektormiljö) till +10 (extremt gynnsam)

Svara med ENBART JSON:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar om varför sektorn är gynnsam/ogynnsam>",
    "key_drivers": ["driver1", "driver2", "driver3"],
    "rotation_signal": "<Övervik | Neutralvikt | Undervikt>"
}"""


class SectorAgent(BaseAgent):
    name = "Sektor-Analytiker"
    perspective = "Sektorrotation"

    def __init__(self):
        self.provider = os.getenv("SECTOR_AGENT_PROVIDER", "openai")

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        """Analyze a sector. asset_id = sector_id, category = sector macro_drivers."""
        price_ctx = self._format_price_context(price_data)
        news_ctx = self._format_news_context(news_items, max_items=10)

        user_prompt = f"""Analysera sektorn:

Sektor: {asset_name}
Sektorns makro-drivers: {category}
{price_ctx}

Relevanta nyheter för sektorbedömning:
{news_ctx}

Ge din sektoranalys som JSON."""

        response = await call_llm(self.provider, SYSTEM_PROMPT, user_prompt)
        result = parse_llm_json(response)

        if result and "score" in result:
            return {
                "score": self._clamp_score(int(result["score"])),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", ""),
                "key_drivers": result.get("key_drivers", []),
                "rotation_signal": result.get("rotation_signal", "Neutralvikt"),
                "provider_used": self.provider,
            }

        return self._rule_based_fallback(asset_id, price_data, news_items)

    def _rule_based_fallback(self, sector_id, price_data, news_items):
        """Rule-based sector analysis using macro signals from news."""
        change = price_data.get("change_pct", 0)

        # Base score from price momentum
        score = 0
        if change > 2: score += 3
        elif change > 0.5: score += 1
        elif change < -2: score -= 3
        elif change < -0.5: score -= 1

        # News sentiment contribution
        pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
        neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
        news_sentiment = (pos - neg) / max(len(news_items), 1)

        # Sector-specific macro-driven biases based on current market conditions
        # These represent the AI's "understanding" of macro-sector relationships
        sector_biases = {
            "tech": 1,              # AI boom ongoing
            "financials": 0,        # Neutral - mixed rate signals
            "defense": 4,           # Geopolitical tensions elevated
            "energy": -1,           # OPEC uncertainties
            "healthcare": 2,        # Defensive + GLP-1 tailwind
            "consumer_disc": -1,    # Consumer under pressure
            "consumer_staples": 1,  # Defensive appeal
            "industrials": 0,       # PMI mixed
            "materials": -1,        # China slowdown
            "real_estate": -2,      # High rates pressure
            "utilities": 1,         # AI datacenter demand
            "communication": 1,     # Ad market recovering
        }

        score += sector_biases.get(sector_id, 0)
        score += int(news_sentiment * 3)

        score = self._clamp_score(score)

        # Determine rotation signal
        if score >= 4: signal = "Övervikt"
        elif score <= -4: signal = "Undervikt"
        else: signal = "Neutralvikt"

        # Generate reasoning
        sector_context = {
            "tech": "AI-investering och innovationscykel driver sektorn, men räntekänslighet skapar motvind.",
            "financials": "Banker gynnas av högre räntor men kreditrisker och yieldkurvan begränsar uppsidan.",
            "defense": "Förhöjd geopolitisk spänning och ökade försvarsbudgetar globalt stödjer sektorn starkt.",
            "energy": "Oljeprisets riktning och OPEC-politik är avgörande. Energiomställning skapar osäkerhet.",
            "healthcare": "Defensiv karaktär med GLP-1-tillväxt ger stabilitet. Regulatorisk risk finns.",
            "consumer_disc": "Konsumentförtroende och arbetsmarknaden är avgörande. Inflationstryck dämpar.",
            "consumer_staples": "Klassisk defensiv sektor som outperformar i osäkerhet. Begränsad uppsida i risk-on.",
            "industrials": "PMI och global handel styr. Infrastrukturinvesteringar ger visst stöd.",
            "materials": "Råvarupriser och Kinas återhämtning är nyckeldrivers. Cyklisk med hög volatilitet.",
            "real_estate": "Extremt räntekänslig. Räntesänkningar krävs för att vända trenden.",
            "utilities": "Defensiv obligationsproxy, men AI-datacenter ökar elefterfrågan strukturellt.",
            "communication": "Annonsmarknaden återhämtar sig. AI-integration i sociala medier driver potential.",
        }

        return {
            "score": score,
            "confidence": 0.5,
            "reasoning": sector_context.get(sector_id, "Sektoranalys baserad på prismomentum och nyhetssentiment."),
            "key_drivers": [f"Prismomentum ({change:+.1f}%)", f"Nyhetssentiment ({pos}+ / {neg}-)"],
            "rotation_signal": signal,
            "provider_used": "rule_based",
        }
