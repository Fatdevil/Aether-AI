"""
Region Analyst Agent - Evaluates geographic markets based on macro environment.
"""

import os
import logging
from .base_agent import BaseAgent
from llm_provider import call_llm, parse_llm_json

logger = logging.getLogger("aether.agents.region")

SYSTEM_PROMPT = """Du är en GEOGRAFISK MARKNADSANALYTIKER specialiserad på global allokering.

Din uppgift är att analysera en specifik GEOGRAFISK MARKNAD och ge poäng -10 till +10.

NYCKELINSIKTER FÖR GEOGRAFISK ALLOKERING:
- USA: Världens reservvaluta. Tech/AI-dominerat. Fed styr global likviditet. Dyrt men kvalitet.
- EUROPA: Exportberoende. Försvarsinvesteringar kan bli nästa katalysator. ECB mer duvaktig.
- JAPAN: Slutet på deflation. BOJ-normalisering. Yen-svaghet gynnar exportörer.
- KINA: Strukturella problem (fastighet, demografi). Stimulans styrs politiskt. Geopolitisk risk.
- INDIEN: Starkaste tillväxtstory. Ung demografi. Infrastructure-boom. Höga värderingar.
- EMERGING MARKETS: Känsliga för USD-styrka och råvarupriser. Heterogen grupp.
- LATINAMERIKA: Höga realräntor, råvaruberoende. Brasilien dominerar.
- ASIEN-STILLAHAVET: Halvledarcykel avgörande. Taiwan-risk. Australien=råvaror.

POÄNGSÄTTNING: -10 (undvik marknaden) till +10 (stark köpsignal)

Svara med ENBART JSON:
{
    "score": <int -10 till 10>,
    "confidence": <float 0.0 till 1.0>,
    "reasoning": "<2-3 meningar om regionens utsikter>",
    "key_drivers": ["driver1", "driver2", "driver3"],
    "allocation_signal": "<Övervikt | Neutralvikt | Undervikt>"
}"""


class RegionAgent(BaseAgent):
    name = "Region-Analytiker"
    perspective = "Geografisk allokering"

    def __init__(self):
        self.provider = os.getenv("REGION_AGENT_PROVIDER", os.getenv("SECTOR_AGENT_PROVIDER", "gemini"))

    async def analyze(self, asset_id, asset_name, category, price_data, news_items, perf_context=""):
        price_ctx = self._format_price_context(price_data)
        news_ctx = self._format_news_context(news_items, max_items=10)

        user_prompt = f"""Analysera geografisk marknad:

Region: {asset_name}
Makro-drivers: {category}
{price_ctx}

Relevanta nyheter:
{news_ctx}

Ge din regionanalys som JSON."""

        response = await call_llm(self.provider, SYSTEM_PROMPT, user_prompt)
        result = parse_llm_json(response)

        if result and "score" in result:
            return {
                "score": self._clamp_score(int(result["score"])),
                "confidence": float(result.get("confidence", 0.7)),
                "reasoning": result.get("reasoning", ""),
                "key_drivers": result.get("key_drivers", []),
                "allocation_signal": result.get("allocation_signal", "Neutralvikt"),
                "provider_used": self.provider,
            }

        return self._rule_based_fallback(asset_id, price_data, news_items)

    def _rule_based_fallback(self, region_id, price_data, news_items):
        change = price_data.get("change_pct", 0)
        score = 0
        if change > 2: score += 3
        elif change > 0.5: score += 1
        elif change < -2: score -= 3
        elif change < -0.5: score -= 1

        pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
        neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
        news_sentiment = (pos - neg) / max(len(news_items), 1)

        region_biases = {
            "usa": 1,          # AI/tech structural growth
            "europe": 2,       # Defense spending catalyst
            "japan": 1,        # Reflation story
            "china": -2,       # Structural headwinds
            "india": 3,        # Strongest growth story
            "em": 0,           # Mixed signals
            "latam": 0,        # High rates, commodity dependent
            "asia_pac": 1,     # Semiconductor upcycle
        }

        score += region_biases.get(region_id, 0)
        score += int(news_sentiment * 2)
        score = self._clamp_score(score)

        if score >= 4: signal = "Övervikt"
        elif score <= -4: signal = "Undervikt"
        else: signal = "Neutralvikt"

        region_context = {
            "usa": "Tech/AI-sektorn driver, men höga värderingar och Fed-osäkerhet begränsar. Dollarstyrka gynnar inhemska tillgångar.",
            "europe": "Försvarsuppbyggnad och ECB-lättnader kan bli katalysatorer. Billigare värderingar än USA. Exportkänslig.",
            "japan": "BOJ-normalisering pågår. Svag yen gynnar exportörer. Företagsreformer förbättrar avkastning.",
            "china": "Stimulanspaket ger kortsiktig lyft men strukturella problem kvarstår. Geopolitisk risk är hög.",
            "india": "Starkaste makrostory med ~7% BNP-tillväxt. Demografi och reformer stödjer. Värderingar höga men motiverade.",
            "em": "Blandad bild. USD-styrka är motvind. Selektiv approach krävs – undvik högskuldsatta.",
            "latam": "Brasilien dominerar. Höga realräntor lockar carry trade. Råvarupriser avgörande.",
            "asia_pac": "Halvledarcykeln är nyckeln. Taiwan/Korea tech-exponering. Australien råvaruberoende.",
        }

        return {
            "score": score,
            "confidence": 0.5,
            "reasoning": region_context.get(region_id, "Regionanalys baserad på prismomentum och sentiment."),
            "key_drivers": [f"Prismomentum ({change:+.1f}%)", f"Nyhetssentiment ({pos}+ / {neg}-)"],
            "allocation_signal": signal,
            "provider_used": "rule_based",
        }
