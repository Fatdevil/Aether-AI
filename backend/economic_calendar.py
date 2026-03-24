"""
Economic Calendar - Tracks major scheduled economic events that impact markets.
Provides context to agents about upcoming high-impact events (FOMC, NFP, CPI, ECB).
Uses a curated event database + live data from free APIs.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("aether.calendar")

# ============================================================
# CURATED RECURRING EVENTS (updated manually or via API)
# These are the events that move markets most.
# ============================================================

# Monthly recurring events (approximate schedule)
RECURRING_EVENTS = {
    "FOMC": {
        "name": "FOMC Räntebeslut",
        "description": "Federal Reserve räntebeslutet och presskonferens",
        "impact": 10,
        "frequency": "6 weeks",
        "affects_assets": ["sp500", "us10y", "gold", "eurusd", "btc"],
        "affects_sectors": ["finance", "realestate"],
        "category": "rate_decision",
    },
    "NFP": {
        "name": "Non-Farm Payrolls (USA)",
        "description": "Amerikanska jobbdata – första fredagen varje månad",
        "impact": 8,
        "frequency": "monthly",
        "affects_assets": ["sp500", "us10y", "eurusd", "gold"],
        "affects_sectors": ["consumer", "industrials"],
        "category": "employment",
    },
    "CPI_US": {
        "name": "CPI Inflation (USA)",
        "description": "Konsumentprisindex – inflationsdata",
        "impact": 9,
        "frequency": "monthly",
        "affects_assets": ["sp500", "us10y", "gold", "eurusd", "btc"],
        "affects_sectors": ["consumer", "finance"],
        "category": "inflation",
    },
    "ECB": {
        "name": "ECB Räntebeslut",
        "description": "Europeiska centralbankens räntebesked",
        "impact": 8,
        "frequency": "6 weeks",
        "affects_assets": ["eurusd", "global-equity", "us10y"],
        "affects_sectors": ["finance"],
        "category": "rate_decision",
    },
    "GDP_US": {
        "name": "BNP (USA, kvartalsvis)",
        "description": "Bruttonationalprodukt – ekonomisk tillväxt",
        "impact": 7,
        "frequency": "quarterly",
        "affects_assets": ["sp500", "us10y", "eurusd"],
        "affects_sectors": ["industrials", "consumer"],
        "category": "growth",
    },
    "PMI": {
        "name": "PMI Manufacturing/Services",
        "description": "Inköpschefsindex – ledande konjunkturindikator",
        "impact": 6,
        "frequency": "monthly",
        "affects_assets": ["sp500", "global-equity", "oil"],
        "affects_sectors": ["industrials", "energy"],
        "category": "growth",
    },
    "OPEC": {
        "name": "OPEC+ Möte",
        "description": "OPEC produktionsbeslut",
        "impact": 8,
        "frequency": "monthly",
        "affects_assets": ["oil", "global-equity"],
        "affects_sectors": ["energy"],
        "category": "commodity",
    },
    "BOJ": {
        "name": "Bank of Japan Räntebeslut",
        "description": "Japanska centralbankens beslut",
        "impact": 6,
        "frequency": "8 weeks",
        "affects_assets": ["global-equity", "eurusd", "us10y"],
        "affects_sectors": ["finance"],
        "category": "rate_decision",
    },
}

# ============================================================
# 2026 CALENDAR – Key scheduled dates
# Updated quarterly. Format: (month, day, event_key, time_utc)
# ============================================================

CALENDAR_2026 = [
    # Q1 2026
    (1, 10, "NFP", "13:30"), (1, 15, "CPI_US", "13:30"),
    (1, 29, "FOMC", "19:00"), (1, 30, "ECB", "13:15"), (1, 30, "GDP_US", "13:30"),
    (2, 7, "NFP", "13:30"), (2, 12, "CPI_US", "13:30"),
    (3, 7, "NFP", "13:30"), (3, 12, "CPI_US", "13:30"),
    (3, 18, "FOMC", "18:00"), (3, 19, "BOJ", "03:00"),
    # Q2 2026
    (4, 3, "NFP", "12:30"), (4, 10, "CPI_US", "12:30"), (4, 16, "ECB", "12:15"),
    (5, 1, "NFP", "12:30"), (5, 6, "FOMC", "18:00"),
    (5, 13, "CPI_US", "12:30"), (5, 28, "GDP_US", "12:30"),
    (6, 5, "NFP", "12:30"), (6, 10, "CPI_US", "12:30"),
    (6, 11, "OPEC", "12:00"), (6, 17, "FOMC", "18:00"), (6, 18, "BOJ", "03:00"),
    # Q3 2026
    (7, 2, "NFP", "12:30"), (7, 14, "CPI_US", "12:30"), (7, 16, "ECB", "12:15"),
    (7, 29, "FOMC", "18:00"), (7, 30, "GDP_US", "12:30"),
    (8, 7, "NFP", "12:30"), (8, 12, "CPI_US", "12:30"),
    (9, 4, "NFP", "12:30"), (9, 10, "CPI_US", "12:30"),
    (9, 16, "FOMC", "18:00"), (9, 17, "BOJ", "03:00"),
    # Q4 2026
    (10, 2, "NFP", "12:30"), (10, 13, "CPI_US", "12:30"),
    (10, 22, "ECB", "12:15"), (10, 29, "GDP_US", "12:30"),
    (11, 4, "FOMC", "18:00"), (11, 6, "NFP", "13:30"),
    (11, 12, "CPI_US", "13:30"),
    (12, 4, "NFP", "13:30"), (12, 10, "CPI_US", "13:30"),
    (12, 16, "FOMC", "19:00"), (12, 17, "ECB", "13:15"), (12, 18, "BOJ", "03:00"),
]


# ============================================================
# CALENDAR ENGINE
# ============================================================

# Cache
_calendar_cache: Optional[dict] = None
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes


class EconomicCalendar:
    """Provides upcoming economic events and their market impact."""

    def __init__(self):
        self._build_events()

    def _build_events(self):
        """Build datetime events from the 2026 calendar."""
        self.events = []
        year = 2026
        for month, day, event_key, time_utc in CALENDAR_2026:
            template = RECURRING_EVENTS.get(event_key, {})
            if not template:
                continue

            hour, minute = map(int, time_utc.split(":"))
            try:
                dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
                self.events.append({
                    "key": event_key,
                    "datetime": dt,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time_utc": time_utc,
                    **template,
                })
            except ValueError:
                continue

        self.events.sort(key=lambda e: e["datetime"])
        logger.info(f"📅 Calendar loaded: {len(self.events)} events for {year}")

    def get_upcoming(self, hours_ahead: int = 72, limit: int = 5) -> list[dict]:
        """Get upcoming events within the next N hours."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)

        upcoming = []
        for event in self.events:
            if now <= event["datetime"] <= cutoff:
                time_until = event["datetime"] - now
                hours_until = time_until.total_seconds() / 3600

                upcoming.append({
                    "key": event["key"],
                    "name": event["name"],
                    "description": event["description"],
                    "datetime": event["datetime"].isoformat(),
                    "date": event["date"],
                    "time_utc": event["time_utc"],
                    "hours_until": round(hours_until, 1),
                    "impact": event["impact"],
                    "affects_assets": event["affects_assets"],
                    "affects_sectors": event.get("affects_sectors", []),
                    "category": event["category"],
                    "urgency": self._classify_urgency(hours_until),
                })

        return upcoming[:limit]

    def get_recent(self, hours_back: int = 24, limit: int = 3) -> list[dict]:
        """Get events that happened recently (for post-event analysis)."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours_back)

        recent = []
        for event in reversed(self.events):
            if cutoff <= event["datetime"] <= now:
                hours_ago = (now - event["datetime"]).total_seconds() / 3600
                recent.append({
                    "key": event["key"],
                    "name": event["name"],
                    "datetime": event["datetime"].isoformat(),
                    "hours_ago": round(hours_ago, 1),
                    "impact": event["impact"],
                    "affects_assets": event["affects_assets"],
                    "category": event["category"],
                })

        return recent[:limit]

    def get_context_for_asset(self, asset_id: str) -> str:
        """Generate calendar context string for a specific asset's agent prompt."""
        upcoming = self.get_upcoming(hours_ahead=48)
        recent = self.get_recent(hours_back=12)

        relevant_upcoming = [e for e in upcoming if asset_id in e.get("affects_assets", [])]
        relevant_recent = [e for e in recent if asset_id in e.get("affects_assets", [])]

        if not relevant_upcoming and not relevant_recent:
            return ""

        parts = ["\nEKONOMISK KALENDER:"]

        for event in relevant_upcoming:
            urgency_emoji = {"imminent": "🔴", "today": "🟠", "soon": "🟡"}.get(event["urgency"], "📅")
            parts.append(
                f"  {urgency_emoji} OM {event['hours_until']:.0f}h: {event['name']} "
                f"(impact: {event['impact']}/10) – {event['description']}"
            )
            if event["urgency"] == "imminent":
                parts.append(
                    f"     ⚠️ EVENT INOM 4H – förvänta hög volatilitet. "
                    f"Sänk confidence på din bedömning."
                )

        for event in relevant_recent:
            parts.append(
                f"  🔵 FÖR {event['hours_ago']:.0f}h SEDAN: {event['name']} "
                f"(impact: {event['impact']}/10) – Marknaden reagerar fortfarande."
            )

        return "\n".join(parts)

    def get_global_context(self) -> str:
        """Generate calendar context for supervisor/overview."""
        upcoming = self.get_upcoming(hours_ahead=72, limit=8)
        if not upcoming:
            return ""

        parts = ["KOMMANDE EKONOMISKA EVENTS (närmaste 72h):"]
        for event in upcoming:
            urgency_emoji = {"imminent": "🔴", "today": "🟠", "soon": "🟡"}.get(event["urgency"], "📅")
            assets = ", ".join(event["affects_assets"][:4])
            parts.append(
                f"  {urgency_emoji} {event['name']} om {event['hours_until']:.0f}h "
                f"(impact: {event['impact']}/10, påverkar: {assets})"
            )

        return "\n".join(parts)

    def should_reduce_confidence(self, asset_id: str) -> tuple[bool, float]:
        """
        Check if confidence should be reduced due to imminent events.
        Returns (should_reduce, multiplier).
        """
        upcoming = self.get_upcoming(hours_ahead=4)
        relevant = [e for e in upcoming if asset_id in e.get("affects_assets", [])]

        if not relevant:
            return False, 1.0

        max_impact = max(e["impact"] for e in relevant)
        # Impact 10 → confidence * 0.5, Impact 7 → * 0.7
        multiplier = max(0.4, 1.0 - (max_impact * 0.06))
        return True, round(multiplier, 2)

    @staticmethod
    def _classify_urgency(hours_until: float) -> str:
        if hours_until <= 4:
            return "imminent"
        elif hours_until <= 12:
            return "today"
        elif hours_until <= 48:
            return "soon"
        return "upcoming"

    def get_summary(self) -> dict:
        """Get calendar summary for API."""
        upcoming = self.get_upcoming(hours_ahead=168, limit=10)  # Next 7 days
        recent = self.get_recent(hours_back=48)

        imminent = [e for e in upcoming if e["urgency"] == "imminent"]
        today_events = [e for e in upcoming if e["urgency"] in ("imminent", "today")]

        return {
            "upcoming": upcoming,
            "recent": recent,
            "imminent_count": len(imminent),
            "today_count": len(today_events),
            "next_high_impact": next(
                (e for e in upcoming if e["impact"] >= 7), None
            ),
        }


# Singleton
calendar = EconomicCalendar()
