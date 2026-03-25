# ============================================================
# FIL: backend/macro_calendar.py
# Makroevent-kalender med förväntat marknadsimpact
# Proaktiv: vet vad som KOMMER att hända
# ============================================================

from datetime import datetime, timedelta
from typing import Dict, List
import json

# Återkommande events (dag-i-månaden approximationer)
RECURRING_EVENTS = [
    {"name": "US Non-Farm Payrolls", "frequency": "monthly", "typical_day": 1,
     "day_of_week": "friday", "impact": "HÖG", "affects": ["SP500", "GOLD", "USDSEK", "US10Y"],
     "description": "Arbetsmarknadsrapport. Stark = dollar stark, aktier blandad. Svag = guld upp."},

    {"name": "US CPI (Inflation)", "frequency": "monthly", "typical_day": 13,
     "impact": "HÖG", "affects": ["SP500", "GOLD", "US10Y", "BTC"],
     "description": "Över förväntan = ränta upp = aktier ner = guld ner. Under = tvärtom."},

    {"name": "Fed Räntebesked (FOMC)", "frequency": "6_weeks", "impact": "EXTREM",
     "affects": ["SP500", "GOLD", "USDSEK", "US10Y", "BTC"],
     "description": "Ränteändring eller signaler om framtida. Största enskilda marknadshändelsen."},

    {"name": "ECB Räntebesked", "frequency": "6_weeks", "impact": "HÖG",
     "affects": ["VGK", "EURUSD", "USDSEK"],
     "description": "Påverkar euro, europeiska aktier. Indirekt SEK via EURSEK."},

    {"name": "Riksbanken Räntebesked", "frequency": "8_weeks", "impact": "HÖG",
     "affects": ["OMXS30", "USDSEK", "SPILTAN_KORT"],
     "description": "Påverkar SEK direkt. Kort ränta, bolån, svensk ekonomi."},

    {"name": "OPEC+ Möte", "frequency": "monthly", "impact": "HÖG",
     "affects": ["OIL", "XLE", "GOLD"],
     "description": "Produktionsbeslut påverkar oljepris direkt. Hormuz-situationen extra relevant."},

    {"name": "US BNP (GDP)", "frequency": "quarterly", "typical_day": 25,
     "impact": "MEDEL", "affects": ["SP500", "USDSEK"],
     "description": "Stark BNP = styrka för dollar och aktier. Svag = recession-oro."},

    {"name": "Kinas PMI", "frequency": "monthly", "typical_day": 1,
     "impact": "MEDEL", "affects": ["EEM", "OIL", "GOLD"],
     "description": "Kinas tillverknings-PMI påverkar EM, råvaror, global tillväxt."},

    {"name": "VIX Options Expiry", "frequency": "monthly", "typical_day": 16,
     "impact": "MEDEL", "affects": ["SP500"],
     "description": "Kan orsaka volatilitets-squeeze. Ofta lugn dag efter."},

    {"name": "Kvartalsrapportsäsong start", "frequency": "quarterly",
     "impact": "HÖG", "affects": ["SP500", "XLK", "OMXS30"],
     "description": "Storbolagsrapporter (NVDA, MSFT, AAPL etc). Stor rörlighet."},
]

# Specifika kända events 2026
KNOWN_EVENTS_2026 = [
    {"name": "Fed FOMC", "date": "2026-03-19", "impact": "EXTREM", "affects": ["SP500", "GOLD", "US10Y", "BTC"]},
    {"name": "Fed FOMC", "date": "2026-05-07", "impact": "EXTREM", "affects": ["SP500", "GOLD", "US10Y", "BTC"]},
    {"name": "Fed FOMC", "date": "2026-06-18", "impact": "EXTREM", "affects": ["SP500", "GOLD", "US10Y", "BTC"]},
    {"name": "Riksbanken", "date": "2026-04-03", "impact": "HÖG", "affects": ["OMXS30", "USDSEK"]},
    {"name": "Riksbanken", "date": "2026-06-26", "impact": "HÖG", "affects": ["OMXS30", "USDSEK"]},
    {"name": "ECB", "date": "2026-04-17", "impact": "HÖG", "affects": ["EURUSD", "VGK"]},
    {"name": "ECB", "date": "2026-06-05", "impact": "HÖG", "affects": ["EURUSD", "VGK"]},
    {"name": "US CPI mars", "date": "2026-04-10", "impact": "HÖG", "affects": ["SP500", "GOLD", "US10Y"]},
    {"name": "US CPI april", "date": "2026-05-13", "impact": "HÖG", "affects": ["SP500", "GOLD", "US10Y"]},
    {"name": "NVIDIA Q1 rapport", "date": "2026-05-28", "impact": "HÖG", "affects": ["SP500", "XLK"]},
]


class MacroEventCalendar:
    def __init__(self):
        self.custom_events: List[Dict] = []

    def add_event(self, name: str, date: str, impact: str, affects: List[str] = None, note: str = ""):
        self.custom_events.append({
            "name": name, "date": date, "impact": impact,
            "affects": affects or [], "note": note
        })

    def get_upcoming(self, days_ahead: int = 14) -> Dict:
        """Hämta kommande events de nästa X dagarna"""
        today = datetime.now()
        cutoff = today + timedelta(days=days_ahead)
        today_str = today.strftime("%Y-%m-%d")
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        events = []
        for ev in KNOWN_EVENTS_2026 + self.custom_events:
            if today_str <= ev["date"] <= cutoff_str:
                days_until = (datetime.strptime(ev["date"], "%Y-%m-%d") - today).days
                events.append({
                    "name": ev["name"],
                    "date": ev["date"],
                    "days_until": days_until,
                    "impact": ev.get("impact", "MEDEL"),
                    "affects": ev.get("affects", []),
                    "note": ev.get("note", ""),
                    "urgency": "IDAG" if days_until == 0 else "IMORGON" if days_until == 1 else f"{days_until}d"
                })

        events.sort(key=lambda x: x["days_until"])

        # Risk-varning om hög-impact-event nära
        high_impact_soon = [e for e in events if e["impact"] in ("HÖG", "EXTREM") and e["days_until"] <= 3]

        warning = None
        if high_impact_soon:
            warning = {
                "level": "VARNING",
                "message": f"{len(high_impact_soon)} hög-impact events inom 3 dagar: {', '.join(e['name'] for e in high_impact_soon)}. Överväg att minska positioner eller höja kassa före.",
                "affected_assets": list(set(a for e in high_impact_soon for a in e.get("affects", [])))
            }

        return {
            "period": f"{today_str} till {cutoff_str}",
            "events": events,
            "n_events": len(events),
            "warning": warning,
            "busiest_day": max(events, key=lambda x: 0)["date"] if events else None
        }
