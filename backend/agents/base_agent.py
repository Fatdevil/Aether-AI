"""
Base Agent - Abstract interface for all AI analyst agents.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("aether.agents")


class BaseAgent(ABC):
    """Base class for all AI analyst agents."""

    name: str = "Base Agent"
    perspective: str = "General"
    provider: str = "rule_based"

    @abstractmethod
    async def analyze(
        self,
        asset_id: str,
        asset_name: str,
        category: str,
        price_data: dict,
        news_items: list,
        perf_context: str = "",
    ) -> dict:
        """
        Analyze an asset and return:
        {
            "score": int (-10 to 10),
            "confidence": float (0-1),
            "reasoning": str,
            "key_factors": list[str],
            "provider_used": str
        }
        """
        pass

    def _clamp_score(self, score: int) -> int:
        return max(-10, min(10, score))

    def _format_price_context(self, price_data: dict) -> str:
        price = price_data.get("price", 0)
        change = price_data.get("change_pct", 0)
        currency = price_data.get("currency", "$")
        base = f"Aktuellt pris: {currency}{price:,.2f}, Daglig förändring: {change:+.2f}%"

        # Include technical indicators if available
        indicators_text = price_data.get("indicators_text", "")
        if indicators_text:
            return f"{base}\n\n{indicators_text}"
        return base

    def _format_news_context(self, news_items: list, max_items: int = 8) -> str:
        if not news_items:
            return "No recent news available."
        lines = []
        for n in news_items[:max_items]:
            sent = n.get("sentiment", "neutral")
            lines.append(f"- [{sent.upper()}] {n.get('title', '')} ({n.get('source', '')})")
        return "\n".join(lines)
