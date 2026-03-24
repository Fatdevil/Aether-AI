"""
Tiered Scheduler - Manages different refresh intervals per analysis tier.

Tier 1 (Cheapest): Prices + News sentiment every 5 min
Tier 2 (Medium): Full asset/sector/region analysis every 1-2 hours  
Tier 3 (Premium): Supervisor + portfolio every 2-4 hours or on-demand
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("aether.scheduler")


class TieredScheduler:
    """Manages tiered refresh intervals for cost optimization."""

    def __init__(self):
        # Intervals in minutes
        self.intervals = {
            "prices": 5,          # Tier 0: No LLM, just yfinance
            "news_sentiment": 5,  # Tier 1: Gemini Flash (cheapest)
            "full_analysis": 60,  # Tier 2: Haiku/4o-mini (medium)
            "supervisor": 120,    # Tier 3: Opus (premium)
            "evaluation": 15,     # Backfill prices + evaluate predictions
        }

        # Last refresh timestamps
        self._last_refresh = {
            "prices": None,
            "news_sentiment": None,
            "full_analysis": None,
            "supervisor": None,
            "evaluation": None,
        }

        # Force flags (sentinel triggers, manual refresh)
        self._force_flags = {
            "full_analysis": False,
            "supervisor": False,
        }

    def should_refresh(self, tier: str) -> bool:
        """Check if a tier needs refreshing based on its interval."""
        # Check force flag first
        if self._force_flags.get(tier, False):
            self._force_flags[tier] = False
            logger.info(f"⚡ Force refresh triggered for tier: {tier}")
            return True

        last = self._last_refresh.get(tier)
        if last is None:
            return True  # Never refreshed

        interval = self.intervals.get(tier, 60)
        next_refresh = last + timedelta(minutes=interval)
        now = datetime.now(timezone.utc)

        return now >= next_refresh

    def mark_refreshed(self, tier: str):
        """Mark a tier as just refreshed."""
        self._last_refresh[tier] = datetime.now(timezone.utc)

    def force_refresh(self, tier: str):
        """Force a refresh for a specific tier (e.g., sentinel trigger)."""
        self._force_flags[tier] = True

    def force_all(self):
        """Force refresh of all tiers."""
        for tier in self._force_flags:
            self._force_flags[tier] = True

    def set_interval(self, tier: str, minutes: int):
        """Update the refresh interval for a tier."""
        self.intervals[tier] = minutes
        logger.info(f"⏱️ Updated {tier} interval to {minutes} min")

    def get_status(self) -> dict:
        """Return scheduler status for API/frontend."""
        now = datetime.now(timezone.utc)
        status = {}
        for tier, interval in self.intervals.items():
            last = self._last_refresh.get(tier)
            if last:
                next_refresh = last + timedelta(minutes=interval)
                seconds_until = max(0, (next_refresh - now).total_seconds())
                status[tier] = {
                    "interval_min": interval,
                    "last_refresh": last.isoformat(),
                    "next_refresh": next_refresh.isoformat(),
                    "seconds_until_next": int(seconds_until),
                    "due": seconds_until == 0,
                }
            else:
                status[tier] = {
                    "interval_min": interval,
                    "last_refresh": None,
                    "next_refresh": None,
                    "seconds_until_next": 0,
                    "due": True,
                }
        return status


# Singleton
scheduler = TieredScheduler()
