# ============================================================
# DAILY BRIEF — Opus 4.6 Powered Market Intelligence
#
# Generates premium daily market briefs:
#   Morning (09:00 CET): "The night that was, the day ahead"
#   Evening (22:30 CET): "Today's markets, what it means"
#
# Uses Tier 3 (Opus) for hedge-fund quality writing.
# Persisted via KV store / file for API serving.
# ============================================================

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger("aether.daily_brief")

DATA_FILE = "data/daily_briefs.json"

# CET timezone offset
CET = timezone(timedelta(hours=2))


# ============================================================
# PROMPTS
# ============================================================

MORNING_BRIEF_PROMPT = """Du ar Chief Investment Officer pa en av Scandinaviens mest framgangsrika
hedgefonder. Skriv morgonens marknadsbrev till fondens investerare.

TONALITET: Professionell men ej torr. Insiktsfull. Koppla alltid till portfoljpaverkan.
         Skriv som om du star infor investerare med hundratals miljoner — varje ord spelar roll.

STRUKTUR (hyll exakt denna):
1. RUBRIK — En stark, nyhetsmassig rubrik (max 10 ord)
2. NATTENS MARKNADER (USA & ASIEN) — Sammanfatta stangningen pa Wall Street igår kvall och nattens rorelser i Asien. Hur satter detta tonen infor den svenska/europeiska borsuppningen? Garna specifika indexnivaer. (3-4 meningar)
3. VARLDSBILD & POLITISK SPANNING — Ge en kansla av att vi bevakar varlden. Finns det pagaende geopolitiska spanningar, varningar om krig, eller viktiga beslut fran centralbanker som ligger som en vat filt eller katalysator? (2-3 meningar)
4. DAGENS FOKUS — Vad ska vi bevaka idag? Vilka risker/mojligheter? (2-3 meningar)
5. PORTFOLJPOSITION — Hur star var portfolj positionerad infor detta? Vad skyddar oss? (2-3 meningar)

AKTUELL KONTEXT:
{context}

Svara med JSON:
{{
    "headline": "Rubrik har",
    "overnight": "Overnight-text...",
    "geopolitics": "Geopolitik-text...",
    "today_focus": "Dagens fokus-text...",
    "portfolio_position": "Portfoljposition-text...",
    "market_mood": "RISK_ON|RISK_OFF|CAUTIOUS|NEUTRAL",
    "confidence": 0.75
}}

REGLER:
- Alla texter PA SVENSKA
- ALDRIG generisk — naamn specifika handelser, aktorer, siffror
- Varje sektion max 3-4 meningar
- Avsluta INTE med "Vi fortsatter att bevaka" eller liknande klicheer"""


EVENING_BRIEF_PROMPT = """Du ar Chief Investment Officer pa en av Scandinaviens mest framgangsrika
hedgefonder. Skriv eftermiddagens uppdatering (inför Wall Street-öppningen kl 14:30) till fondens investerare.

TONALITET: Analytisk och framåtblickande. Sammanfatta den svenska handelsdagen hittills och blicka mot USA.

STRUKTUR (folj exakt denna):
1. RUBRIK — En sammanfattande rubrik för dagen (max 10 ord)
2. DAGEN I SVERIGE/EUROPA — Hur har den svenska börsen (OMX) och Europa gått hittills idag? Vilka är de drivande faktorerna bakom rörelserna? (3-4 meningar)
3. INFÖR WALL STREET — Investerare väntar på USA. Hur ser det ut inför öppningen? Vad pekar terminerna på och framförallt varför? Någon viktig makrodata att invänta? (2-3 meningar)
4. PORTFÖLJAVKASTNING — Hur går vår portfölj idag? (2-3 meningar)
5. IMORGON — Vad innebar dagens utveckling för morgondagen? (2 meningar)

AKTUELL KONTEXT:
{context}

Svara med JSON:
{{
    "headline": "Rubrik har",
    "day_summary": "Sammanfattning...",
    "why_it_happened": "Analys...",
    "portfolio_impact": "Portfoljpaverkan...",
    "tomorrow_outlook": "Imorgon...",
    "market_mood": "RISK_ON|RISK_OFF|CAUTIOUS|NEUTRAL",
    "confidence": 0.75
}}

REGLER:
- Alla texter PA SVENSKA
- ALDRIG generisk — naamn specifika handelser, siffror, procent
- Varje sektion max 3-4 meningar
- Om en tillgang stack ut (guld +3%, BTC -5%), NAAMN DEN"""


# ============================================================
# BRIEF GENERATOR
# ============================================================

class DailyBriefEngine:
    """Generates premium daily market briefs using Opus."""

    def __init__(self):
        self.briefs: Dict[str, dict] = {}  # date -> brief
        self._load()

    def _load(self):
        """Load persisted briefs."""
        data = None
        try:
            from db import kv_get
            data = kv_get("daily_briefs")
        except Exception:
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass

        if data and isinstance(data, dict):
            self.briefs = data.get("briefs", {})

    def _save(self):
        """Persist briefs."""
        data = {"briefs": self.briefs}
        try:
            from db import kv_set
            kv_set("daily_briefs", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)

    def _build_context(self, brief_type: str = "morning") -> str:
        """Gather all available context for the brief."""
        lines = []

        # 1. Market prices
        try:
            from market_data import get_all_prices
            prices = get_all_prices()
            if prices:
                lines.append("=== MARKNADSDATA ===")
                for asset_id, data in prices.items():
                    price = data.get("price", 0)
                    change = data.get("changePct", 0)
                    direction = "▲" if change >= 0 else "▼"
                    lines.append(f"  {asset_id}: {data.get('currency','$')}{price:.2f} ({direction}{abs(change):.1f}%)")
        except Exception as e:
            logger.debug(f"Could not get prices for brief: {e}")

        # 2. News headlines (high impact)
        try:
            from news_sentinel import sentinel
            alerts = sentinel.get_alerts(min_impact=5)
            if alerts:
                lines.append("")
                lines.append("=== SENASTE NYHETER (IMPACT >= 5) ===")
                for alert in alerts[:10]:
                    title = alert.get("title", "")
                    impact = alert.get("impact_score", 0)
                    lines.append(f"  [Impact {impact}] {title}")
        except Exception as e:
            logger.debug(f"Could not get news for brief: {e}")

        # 3. Political intelligence
        try:
            from predictive.political_intelligence import political_engine
            dashboard = political_engine.get_dashboard()
            actors = dashboard.get("active_actors", [])
            if actors:
                lines.append("")
                lines.append("=== POLITISKA AKTÖRER ===")
                for actor in actors[:5]:
                    name = actor.get("actor", "?")
                    signals = actor.get("signal_count", 0)
                    lines.append(f"  {name}: {signals} signaler")
            bias = dashboard.get("market_bias", {})
            if bias:
                lines.append(f"  Marknads-bias: {bias.get('bias', '?')} (konfidens: {bias.get('confidence', 0):.0%})")
        except Exception as e:
            logger.debug(f"Could not get political data for brief: {e}")

        # 4. Portfolio state
        try:
            from portfolio_manager import portfolio
            stats = portfolio.get_stats()
            if stats:
                lines.append("")
                lines.append("=== PORTFÖLJSTATUS ===")
                lines.append(f"  Totalvärde: {stats.get('total_value', 0):.0f}")
                lines.append(f"  Daglig avkastning: {stats.get('daily_return', 0):.2%}")
                allocs = stats.get("allocations", [])
                top = sorted(allocs, key=lambda x: x.get("weight", 0), reverse=True)[:5]
                for a in top:
                    lines.append(f"  {a.get('name', '?')}: {a.get('weight', 0):.0%}")
        except Exception as e:
            logger.debug(f"Could not get portfolio for brief: {e}")

        # 5. Scenario engine state (Omega)
        try:
            from scenario_engine import scenario_engine
            omega = scenario_engine.get_current_portfolio()
            if omega:
                lines.append("")
                lines.append("=== OMEGA-PORTFÖLJEN ===")
                lines.append(f"  Förväntad avkastning: {omega.get('expected_return', 0):.1%}")
                lines.append(f"  CVaR 5%: {omega.get('cvar_5pct', 0):.1%}")
                weights = omega.get("weights", {})
                top_omega = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:5]
                for name, w in top_omega:
                    lines.append(f"  {name}: {w:.0%}")
        except Exception as e:
            logger.debug(f"Could not get omega for brief: {e}")

        # 6. Regime
        try:
            from data_service import data_service
            if hasattr(data_service, 'regime'):
                regime = data_service.regime.get("current", "NEUTRAL")
                lines.append(f"\n=== REGIME: {regime} ===")
        except Exception:
            pass

        return "\n".join(lines) if lines else "Ingen kontext tillgänglig."

    async def generate_brief(self, brief_type: str = "morning", force: bool = False) -> dict:
        """Generate a morning or evening brief using Opus (Tier 3)."""
        now = datetime.now(CET)
        date_key = now.strftime("%Y-%m-%d")
        brief_key = f"{date_key}_{brief_type}"

        # Check if already generated today
        if not force and brief_key in self.briefs:
            logger.info(f"Brief {brief_key} already exists, returning cached")
            return self.briefs[brief_key]

        # Build context
        context = self._build_context(brief_type)

        # Select prompt
        if brief_type == "morning":
            prompt_template = MORNING_BRIEF_PROMPT
        else:
            prompt_template = EVENING_BRIEF_PROMPT

        prompt = prompt_template.format(context=context)

        # Call LLM: Morning = Opus (deepest analysis), Evening = Sonnet (cost-effective)
        try:
            from llm_provider import call_llm_tiered, parse_llm_json

            tier = "3-opus" if brief_type == "morning" else 3
            response, provider = await call_llm_tiered(
                tier,
                "Du ar CIO pa en svensk hedgefond. Alla svar PA SVENSKA. Svara ENBART med JSON.",
                prompt,
                temperature=0.3,
                max_tokens=2000,
            )

            if not response:
                logger.warning("Opus brief generation failed")
                return self._fallback_brief(brief_type)

            parsed = parse_llm_json(response)
            if not parsed:
                logger.warning("Could not parse Opus brief response")
                return self._fallback_brief(brief_type)

            brief = {
                "type": brief_type,
                "date": date_key,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "content": parsed,
            }

            self.briefs[brief_key] = brief
            self._save()

            logger.info(f"Generated {brief_type} brief via {provider}: {parsed.get('headline', '?')}")
            return brief

        except Exception as e:
            logger.error(f"Brief generation error: {e}")
            return self._fallback_brief(brief_type)

    def _fallback_brief(self, brief_type: str) -> dict:
        """Minimal fallback if Opus is unavailable."""
        now = datetime.now(CET)
        return {
            "type": brief_type,
            "date": now.strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": "fallback",
            "content": {
                "headline": "Marknadsbrev ej tillgängligt",
                "market_mood": "NEUTRAL",
                "confidence": 0,
            },
        }

    def get_latest(self, brief_type: str = None) -> Optional[dict]:
        """Return the most recent brief (optionally filtered by type)."""
        if not self.briefs:
            return None

        if brief_type:
            matching = {k: v for k, v in self.briefs.items() if v.get("type") == brief_type}
            if not matching:
                return None
            latest_key = max(matching.keys())
            return matching[latest_key]

        latest_key = max(self.briefs.keys())
        return self.briefs[latest_key]

    def get_all(self, limit: int = 14) -> List[dict]:
        """Return recent briefs (default: last 7 days = 14 briefs)."""
        sorted_keys = sorted(self.briefs.keys(), reverse=True)[:limit]
        return [self.briefs[k] for k in sorted_keys]


# Singleton
daily_brief_engine = DailyBriefEngine()
