"""
Aether AI — System Routes
Health, system info, scheduler, alerts, performance, tier status.
Extracted from main.py for modularity.
"""
from datetime import datetime, timezone
from fastapi import APIRouter

import logging

logger = logging.getLogger("aether")

router = APIRouter(tags=["System"])


def setup(data_service, get_system_info):
    """Register routes that depend on shared state."""

    @router.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_refresh": data_service.last_refresh,
        }

    @router.get("/api/scheduler")
    async def get_scheduler_status():
        """Return tiered scheduler status."""
        from scheduler import scheduler
        return scheduler.get_status()

    @router.get("/api/alerts")
    async def get_alerts(min_impact: int = 1):
        """Return recent sentinel alerts filtered by minimum impact score."""
        from news_sentinel import sentinel
        return {
            "alerts": sentinel.get_alerts(min_impact),
            "stats": sentinel.get_stats(),
        }

    @router.post("/api/alerts/test")
    async def test_notification():
        """Send a test push notification."""
        from notification_service import send_notification
        success = await send_notification(
            title="🧪 Aether AI - Testnotis",
            message="Push-notiser fungerar! Du kommer nu få varningar vid marknadskritiska händelser.",
            priority=3,
            tags=["white_check_mark"],
        )
        return {"success": success, "message": "Test notification sent" if success else "Notification failed"}

    @router.get("/api/system")
    async def system_info():
        """Return system info: active providers, agent config, sentinel status."""
        from news_sentinel import sentinel
        from analysis_store import store
        info = get_system_info()
        info["version"] = "0.5.0"
        info["last_refresh"] = data_service.last_refresh
        info["sentinel"] = sentinel.get_stats()
        info["database"] = store.get_total_analyses_count()
        return info

    @router.get("/api/performance")
    async def get_performance():
        """Return AI performance / accuracy dashboard data."""
        from evaluator import evaluator
        return evaluator.get_performance_report()

    @router.get("/api/tier-status")
    async def get_tier_status():
        """Return current LLM tier configuration, escalation status, and daily budget."""
        from llm_provider import TIER_MODELS, get_available_providers, escalation_guard, get_daily_cost_status
        return {
            "tier_models": {str(k): v for k, v in TIER_MODELS.items()},
            "providers": get_available_providers(),
            "escalation": escalation_guard.get_status(),
            "daily_budget": get_daily_cost_status(),
        }
