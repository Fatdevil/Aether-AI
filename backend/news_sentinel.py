"""
News Sentinel - AI-powered news monitoring system.
Uses Gemini Flash to score every news item by market impact (1-10).
Triggers analysis and push notifications for critical events.
"""

import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from llm_provider import call_llm_tiered, parse_llm_json
from notification_service import send_notification

logger = logging.getLogger("aether.sentinel")

SENTINEL_PROMPT = """Du är en FINANSIELL NYHETSÖVERVAKARE (News Sentinel).
Din uppgift är att snabbt bedöma en nyhet och avgöra hur stor MARKNADSPÅVERKAN den har,
samt vilka tillgångar och sektorer som påverkas och i vilken riktning.

IMPACT-SKALA:
1-2: Rutinnyhet, ingen marknadspåverkan (företagsnyhet, branschevent)
3-4: Noterbart men begränsat (kvartalsrapport inom förväntan, mindre policyändring)
5-6: Viktig nyhet (centralbanksuttalande, oväntat BNP-tal, betydande geopolitisk händelse)
7-8: Marknadspåverkande (räntebeslut utanför förväntan, stor företagskonkurs, handelskrig)
9-10: Historisk händelse (finanskris, pandemi, krig, valutakollaps, Black Swan)

TILLGÅNGAR: btc, sp500, global-equity, gold, silver, eurusd, oil, us10y
SEKTORER: tech, finance, defense, energy, healthcare, consumer, industrials, realestate
REGIONER: usa, europe, japan, china, india, em, latam, asia_pac

RIKTNING: "up" = nyheten gynnar/driver upp, "down" = nyheten missgynnar/driver ner, "mixed" = osäker
STYRKA: "weak", "moderate", "strong"

Svara ENBART med JSON:
{
    "impact_score": <int 1-10>,
    "category": "<rate_decision|geopolitics|earnings|crash|policy|commodity|crypto|other>",
    "affected_assets": [
        {"id": "asset_id", "direction": "up|down|mixed", "strength": "weak|moderate|strong", "reason": "<kort förklaring på svenska>"}
    ],
    "affected_sectors": [
        {"id": "sector_id", "direction": "up|down|mixed", "reason": "<kort förklaring på svenska>"}
    ],
    "affected_regions": ["region1", "region2"],
    "urgency": "<routine|notable|urgent|critical>",
    "one_liner": "<En mening som sammanfattar marknadspåverkan på svenska>"
}"""


class NewsSentinel:
    """Monitors news and scores by market impact."""

    def __init__(self):
        self.alerts: list[dict] = []  # Recent alerts (last 50)
        self.all_evaluations: dict[str, dict] = {}  # ALL evaluations keyed by title
        self.pending_triggers: list[dict] = []  # Analysis triggers
        self.stats = {
            "total_scanned": 0,
            "alerts_triggered": 0,
            "critical_alerts": 0,
            "last_scan": None,
        }
        self._seen_titles: list[str] = []  # Dedup list to maintain order (LIFO)

    async def scan_news(self, news_items: list[dict]) -> list[dict]:
        """
        Scan a batch of news items and return any alerts.
        Only processes news items not seen before.
        """
        new_items = []
        for item in news_items:
            title = item.get("title", "")
            if title and title not in self._seen_titles:
                self._seen_titles.append(title)
                new_items.append(item)

        if not new_items:
            return []

        # Keep dedup list manageable (FIFO cache)
        if len(self._seen_titles) > 1000:
            # We use list to maintain insertion order (newest at the end).
            self._seen_titles = self._seen_titles[-500:]

        # Political Intelligence v2: lazy-load engine for sentinel integration
        political_engine = None
        try:
            import sys
            main_mod = sys.modules.get("__main__")
            if main_mod and hasattr(main_mod, "political_engine"):
                political_engine = main_mod.political_engine
            else:
                pi_mod = sys.modules.get("predictive.political_intelligence")
                if pi_mod and hasattr(pi_mod, "_sentinel_engine"):
                    political_engine = pi_mod._sentinel_engine
                else:
                    from predictive.political_intelligence import PoliticalIntelligenceEngine
                    political_engine = PoliticalIntelligenceEngine()
                    if pi_mod:
                        pi_mod._sentinel_engine = political_engine
        except Exception as e:
            logger.debug(f"Political engine not available: {e}")

        logger.info(f"🔍 Sentinel scanning {len(new_items)} new items...")
        new_alerts = []

        for item in new_items:
            try:
                alert = await self._evaluate_news(item)
                self.stats["total_scanned"] += 1

                if alert:
                    # Store ALL evaluations for news enrichment
                    self.all_evaluations[alert.get("title", "")] = alert

                    if alert["impact_score"] >= 5:
                        self.alerts.append(alert)
                        new_alerts.append(alert)
                        self.stats["alerts_triggered"] += 1

                        # Political Intelligence v2: match against power actors
                        if political_engine:
                            try:
                                pol_signal = political_engine.process_sentinel_alert(alert)
                                if pol_signal:
                                    logger.info(
                                        f"🏛️ Political: {pol_signal['actor_name']} "
                                        f"{pol_signal['tone']} (impact={alert['impact_score']})"
                                    )
                            except Exception as pe:
                                logger.debug(f"Political filter error: {pe}")

                        if alert["impact_score"] >= 7:
                            self.stats["critical_alerts"] += 1
                            # Send push notification for critical alerts
                            await self._send_alert_notification(alert)
                            # Queue analysis trigger
                            self.pending_triggers.append({
                                "alert": alert,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "status": "pending",
                            })

            except Exception as e:
                logger.warning(f"Sentinel error on '{item.get('title', '')[:50]}': {e}")

        # Keep only last 50 alerts
        self.alerts = self.alerts[-50:]
        self.stats["last_scan"] = datetime.now(timezone.utc).isoformat()

        if new_alerts:
            logger.info(f"🚨 Sentinel found {len(new_alerts)} alerts (impact ≥5)")
        else:
            logger.info(f"✅ Sentinel: No significant alerts in {len(new_items)} items")

        return new_alerts

    async def _evaluate_news(self, item: dict) -> Optional[dict]:
        """Use AI to evaluate a single news item's market impact."""
        title = item.get("title", "")
        source = item.get("source", "Unknown")
        summary = item.get("summary", title)

        user_prompt = f"""Bedöm denna nyhet:

Titel: "{title}"
Källa: {source}
Sammanfattning: "{summary[:500]}"
Tid: {item.get('time', 'okänd')}

Ge din impact-bedömning som JSON."""

        # Use cheapest model: gemini flash
        response, provider_used = await call_llm_tiered(0, SENTINEL_PROMPT, user_prompt, temperature=0.1, max_tokens=300)
        logger.debug(f"Sentinel used model: {provider_used}")
        result = parse_llm_json(response)

        if not result or "impact_score" not in result:
            # Rule-based fallback for sentinel
            return self._rule_based_evaluate(item)

        impact = int(result["impact_score"])
        impact = max(1, min(10, impact))

        return {
            "id": f"alert-{self.stats['total_scanned']}",
            "title": title,
            "source": source,
            "time": item.get("time", ""),
            "impact_score": impact,
            "category": result.get("category", "other"),
            "affected_assets": result.get("affected_assets", []),
            "affected_sectors": result.get("affected_sectors", []),
            "affected_regions": result.get("affected_regions", []),
            "urgency": result.get("urgency", "routine"),
            "one_liner": result.get("one_liner", title),
            "provider": "gemini",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _rule_based_evaluate(self, item: dict) -> dict:
        """Fallback: rule-based impact scoring with asset/sector mapping."""
        title = (item.get("title", "") + " " + item.get("summary", "")).lower()
        score = 2  # Default: routine
        affected_assets = []
        affected_sectors = []
        affected_regions = []
        category = "other"

        # === KEYWORD → IMPACT + ASSET/SECTOR MAPPING ===

        # Central banks & rates
        if any(kw in title for kw in ["rate hike", "rate cut", "räntebeslut", "fed ", "federal reserve", "interest rate"]):
            score = max(score, 8)
            category = "rate_decision"
            is_hike = any(kw in title for kw in ["hike", "raise", "höj"])
            dir_bonds = "up" if is_hike else "down"
            dir_equity = "down" if is_hike else "up"
            dir_gold = "down" if is_hike else "up"
            affected_assets = [
                {"id": "us10y", "direction": dir_bonds, "strength": "strong", "reason": "Räntebeslutet påverkar obligationsmarknaden direkt"},
                {"id": "sp500", "direction": dir_equity, "strength": "strong", "reason": f"{'Högre' if is_hike else 'Lägre'} räntor {'pressar' if is_hike else 'gynnar'} aktievärderingar"},
                {"id": "gold", "direction": dir_gold, "strength": "moderate", "reason": f"Guld {'missgynnas av högre' if is_hike else 'gynnas av lägre'} realräntor"},
                {"id": "btc", "direction": dir_equity, "strength": "moderate", "reason": f"Krypto {'pressas av åtstramning' if is_hike else 'gynnas av lättare penningpolitik'}"},
            ]
            affected_sectors = [
                {"id": "finance", "direction": "up" if is_hike else "down", "reason": f"Banker {'tjänar på' if is_hike else 'pressas av'} {'högre' if is_hike else 'lägre'} räntemarginaler"},
                {"id": "realestate", "direction": "down" if is_hike else "up", "reason": f"Fastigheter {'pressas av dyrare' if is_hike else 'gynnas av billigare'} finansiering"},
            ]
            affected_regions = ["usa"]

        elif any(kw in title for kw in ["ecb ", "european central"]):
            score = max(score, 7)
            category = "rate_decision"
            affected_assets = [
                {"id": "eurusd", "direction": "up", "strength": "strong", "reason": "ECB-beslut påverkar euron direkt"},
                {"id": "us10y", "direction": "mixed", "strength": "weak", "reason": "Smittoeffekt via globala ränteförväntningar"},
            ]
            affected_regions = ["europe"]

        # Geopolitics & war
        elif any(kw in title for kw in ["war ", "invasion", "military", "krig", "sanctions", "sanktion", "tariff", "tull"]):
            score = max(score, 8)
            category = "geopolitics"
            affected_assets = [
                {"id": "gold", "direction": "up", "strength": "strong", "reason": "Guld stiger som säker hamn vid geopolitisk osäkerhet"},
                {"id": "oil", "direction": "up", "strength": "moderate", "reason": "Geopolitisk risk driver oljepriser uppåt"},
                {"id": "sp500", "direction": "down", "strength": "moderate", "reason": "Aktier pressas av ökad osäkerhet och riskversion"},
                {"id": "btc", "direction": "mixed", "strength": "weak", "reason": "Krypto kan fungera som alternativ tillflyktsort"},
            ]
            affected_sectors = [
                {"id": "defense", "direction": "up", "reason": "Försvarssektorn gynnas av ökade geopolitiska spänningar"},
                {"id": "energy", "direction": "up", "reason": "Energipriser stiger vid utbudsoro"},
            ]

        # Recession & crisis
        elif any(kw in title for kw in ["recession", "lågkonjunktur", "crash", "collapse", "kris", "crisis", "default"]):
            score = max(score, 8)
            category = "crash"
            affected_assets = [
                {"id": "sp500", "direction": "down", "strength": "strong", "reason": "Aktier faller kraftigt vid recessionsoro"},
                {"id": "gold", "direction": "up", "strength": "strong", "reason": "Guld stiger som säker hamn under kriser"},
                {"id": "us10y", "direction": "down", "strength": "moderate", "reason": "Räntor faller när marknaden flyr till statsobligationer"},
                {"id": "oil", "direction": "down", "strength": "moderate", "reason": "Lägre efterfrågan pressar oljepriser"},
            ]

        # Crypto specific
        elif any(kw in title for kw in ["bitcoin", "crypto", "ethereum", "btc", "halvening", "halving"]):
            score = max(score, 5)
            category = "crypto"
            sentiment = item.get("sentiment", "neutral")
            direction = "up" if sentiment == "positive" else "down" if sentiment == "negative" else "mixed"
            affected_assets = [
                {"id": "btc", "direction": direction, "strength": "strong", "reason": "Direkt kryptorelaterad nyhet"},
            ]

        # Oil & OPEC
        elif any(kw in title for kw in ["oil", "opec", "crude", "olja", "brent", "petroleum"]):
            score = max(score, 6)
            category = "commodity"
            affected_assets = [
                {"id": "oil", "direction": "mixed", "strength": "strong", "reason": "Direkt oljerelaterad nyhet"},
            ]
            affected_sectors = [
                {"id": "energy", "direction": "mixed", "reason": "Energisektorn följer oljepriset direkt"},
            ]

        # Inflation
        elif any(kw in title for kw in ["inflation", "cpi", "pce", "consumer price"]):
            score = max(score, 6)
            category = "policy"
            high = any(kw in title for kw in ["surge", "high", "rise", "hög", "stiger", "above"])
            affected_assets = [
                {"id": "gold", "direction": "up" if high else "down", "strength": "moderate", "reason": f"{'Hög' if high else 'Låg'} inflation {'gynnar' if high else 'missgynnar'} guld som inflationsskydd"},
                {"id": "us10y", "direction": "up" if high else "down", "strength": "moderate", "reason": f"{'Hög' if high else 'Låg'} inflation {'driver upp' if high else 'sänker'} ränteförväntningar"},
                {"id": "sp500", "direction": "down" if high else "up", "strength": "moderate", "reason": f"{'Hög' if high else 'Låg'} inflation {'pressar' if high else 'gynnar'} aktier via räntevägen"},
            ]

        # Earnings & companies
        elif any(kw in title for kw in ["earnings", "quarterly", "revenue", "profit", "vinst", "rapport"]):
            score = max(score, 4)
            category = "earnings"
            affected_assets = [
                {"id": "sp500", "direction": "mixed", "strength": "weak", "reason": "Bolagsrapporter påverkar aktiesentimentet"},
            ]
            affected_sectors = [
                {"id": "tech", "direction": "mixed", "reason": "Tekniksektorn mest fokuserad under rapportsäsong"},
            ]

        # GDP & employment
        elif any(kw in title for kw in ["gdp", "bnp", "unemployment", "jobs", "nonfarm", "employment"]):
            score = max(score, 6)
            category = "policy"
            affected_assets = [
                {"id": "sp500", "direction": "mixed", "strength": "moderate", "reason": "Makrodata påverkar tillväxtförväntningarna"},
                {"id": "us10y", "direction": "mixed", "strength": "moderate", "reason": "Arbetsmarknadsdata styr ränteförväntningar"},
            ]
            affected_regions = ["usa"]

        # Nuclear / pandemic
        elif any(kw in title for kw in ["nuclear", "pandemic", "virus"]):
            score = max(score, 9)
            category = "geopolitics"
            affected_assets = [
                {"id": "gold", "direction": "up", "strength": "strong", "reason": "Extremhändelse driver guld som säker hamn"},
                {"id": "sp500", "direction": "down", "strength": "strong", "reason": "Aktier kollapsar vid systemisk risk"},
            ]

        # Sentiment boost for negative news with high score
        sentiment = item.get("sentiment", "neutral")
        if sentiment == "negative" and score >= 4:
            score = min(10, score + 1)

        urgency = "routine"
        if score >= 7: urgency = "critical"
        elif score >= 5: urgency = "urgent"
        elif score >= 4: urgency = "notable"

        return {
            "id": f"alert-{self.stats['total_scanned']}",
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "time": item.get("time", ""),
            "impact_score": score,
            "category": category,
            "affected_assets": affected_assets,
            "affected_sectors": affected_sectors,
            "affected_regions": affected_regions,
            "urgency": urgency,
            "one_liner": item.get("title", ""),
            "provider": "rule_based",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _send_alert_notification(self, alert: dict):
        """Send push notification for critical alerts."""
        impact = alert["impact_score"]
        emoji = "🚨" if impact >= 9 else "⚠️" if impact >= 7 else "📊"

        # Handle both old (list of strings) and new (list of dicts) format
        raw_assets = alert.get("affected_assets", [])
        if raw_assets and isinstance(raw_assets[0], dict):
            assets_str = ", ".join(
                f'{a["id"]}{"↑" if a.get("direction")=="up" else "↓" if a.get("direction")=="down" else "↔"}' 
                for a in raw_assets
            )[:60]
        else:
            assets_str = ", ".join(raw_assets)[:60]

        raw_sectors = alert.get("affected_sectors", [])
        if raw_sectors and isinstance(raw_sectors[0], dict):
            sectors_str = ", ".join(s["id"] for s in raw_sectors)[:40]
        else:
            sectors_str = ", ".join(raw_sectors)[:40]
        regions_str = ", ".join(alert.get("affected_regions", []))[:40]

        title = f"{emoji} MARKNADSLARM (Impact: {impact}/10)"

        parts = [alert.get("one_liner", alert["title"])]
        if assets_str:
            parts.append(f"→ Tillgångar: {assets_str}")
        if sectors_str:
            parts.append(f"→ Sektorer: {sectors_str}")
        if regions_str:
            parts.append(f"→ Regioner: {regions_str}")

        message = "\n".join(parts)

        priority = 5 if impact >= 9 else 4 if impact >= 7 else 3
        tags = ["warning" if impact >= 8 else "chart_with_upwards_trend"]

        await send_notification(
            title=title,
            message=message,
            priority=priority,
            tags=tags,
        )

    def get_alerts(self, min_impact: int = 1) -> list[dict]:
        """Return recent alerts filtered by minimum impact."""
        return [a for a in self.alerts if a["impact_score"] >= min_impact]

    def get_stats(self) -> dict:
        return self.stats

    def get_pending_triggers(self) -> list[dict]:
        triggers = self.pending_triggers.copy()
        self.pending_triggers = []
        return triggers


# Singleton
sentinel = NewsSentinel()
