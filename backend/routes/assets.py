"""
Aether AI — Assets & Market Data Routes
Extracted from main.py for modularity.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import logging

logger = logging.getLogger("aether")

router = APIRouter(tags=["Assets & Market Data"])


def setup(data_service, risk_manager, _last_pipeline_run, _pipeline_run_count, PIPELINE_INTERVAL_HOURS, _score_to_rec):
    """Register routes that depend on shared state. Called from main.py after initialization."""

    @router.get("/api/assets")
    async def get_assets():
        """Return all assets with current prices and AI analysis."""
        return data_service.get_assets()

    @router.get("/api/assets/{asset_id}")
    async def get_asset(asset_id: str):
        """Return detailed analysis for a single asset."""
        asset = data_service.get_asset(asset_id)
        if not asset:
            return JSONResponse(status_code=404, content={"error": "Asset not found"})
        return asset

    @router.get("/api/news")
    async def get_news():
        """Return aggregated news feed enriched with sentinel impact data."""
        from news_sentinel import sentinel
        news = data_service.get_news()

        enriched = []
        for item in news:
            enriched_item = dict(item)
            eval_data = sentinel.all_evaluations.get(item.get("title", ""))
            if eval_data:
                enriched_item["impact"] = {
                    "score": eval_data.get("impact_score", 0),
                    "category": eval_data.get("category", "other"),
                    "urgency": eval_data.get("urgency", "routine"),
                    "one_liner": eval_data.get("one_liner", ""),
                    "affected_assets": eval_data.get("affected_assets", []),
                    "affected_sectors": eval_data.get("affected_sectors", []),
                    "affected_regions": eval_data.get("affected_regions", []),
                    "provider": eval_data.get("provider", "rule_based"),
                }
            enriched.append(enriched_item)

        return enriched

    @router.get("/api/portfolio")
    async def get_portfolio():
        """Return AI-recommended portfolio allocation."""
        return data_service.get_portfolio()

    @router.get("/api/market-state")
    async def get_market_state():
        """Return overall market state summary + risk status + pipeline B status."""
        state = data_service.get_market_state()

        try:
            from portfolio_manager import portfolio
            prices = data_service.prices or {}
            port_summary = portfolio.get_portfolio_summary(prices)
            total_value = port_summary.get("total_value", 0) if isinstance(port_summary, dict) else 0
            if total_value > 0:
                risk_check = risk_manager.update(total_value)
                state["risk_status"] = {
                    "trailing_stop": risk_check.get("stop_triggered", False),
                    "drawdown_pct": risk_check.get("drawdown_pct", 0),
                    "action": risk_check.get("action", "NORMAL"),
                    "risk_multiplier": risk_check.get("risk_multiplier", 1.0),
                    "message": risk_check.get("message", ""),
                }
        except Exception:
            state["risk_status"] = {"trailing_stop": False, "action": "NORMAL", "drawdown_pct": 0}

        state["pipeline_b"] = {
            "last_run": _last_pipeline_run.isoformat() if _last_pipeline_run else None,
            "run_count": _pipeline_run_count,
            "next_run_hours": PIPELINE_INTERVAL_HOURS,
        }

        return state

    @router.get("/api/sectors")
    async def get_sectors():
        """Return all sector analyses with scores and rotation signals."""
        return data_service.get_sectors()

    @router.get("/api/regions")
    async def get_regions():
        """Return all geographic region analyses with scores and allocation signals."""
        return data_service.get_regions()

    @router.post("/api/refresh")
    async def force_refresh():
        """Force a full data + analysis refresh (all tiers)."""
        from datetime import datetime, timezone
        await data_service.refresh_all(force=True)
        return {"status": "refreshed", "timestamp": datetime.now(timezone.utc).isoformat()}

    @router.get("/api/regime")
    async def get_regime():
        """Return current market regime detection."""
        from regime_detector import regime_detector
        return regime_detector.detect_regime()

    @router.get("/api/signals")
    async def get_signals():
        """Return trade signals for all assets."""
        from trade_signals import signal_generator
        signals = {}
        try:
            price_map = data_service.prices
            assets = data_service.assets

            for asset_data in assets:
                asset_id = asset_data.get("id", "")
                price_info = price_map.get(asset_id, {})
                if not price_info or not price_info.get("price"):
                    continue

                price_data = {
                    "price": price_info.get("price", 0),
                    "indicators": price_info.get("indicators", {}),
                }

                analysis = {
                    "finalScore": asset_data.get("finalScore", 0),
                    "supervisorConfidence": 0.6,
                    "recommendation": _score_to_rec(asset_data.get("finalScore", 0)),
                }

                signals[asset_id] = signal_generator.generate_signal(asset_id, analysis, price_data)
        except Exception as e:
            logger.error(f"Signal generation failed: {e}")
        return {"signals": signals}

    @router.get("/api/onchain")
    async def get_onchain():
        """Return BTC on-chain data."""
        from onchain_data import fetch_onchain_data
        return await fetch_onchain_data()

    @router.get("/api/prices/history/{asset_id}")
    async def get_price_history(asset_id: str, period: str = "3mo"):
        """Return OHLC price history for TradingView charts (yfinance)."""
        from market_data import ASSET_TICKERS
        import yfinance as yf

        info = ASSET_TICKERS.get(asset_id)
        if not info:
            return {"error": f"Unknown asset: {asset_id}", "candles": []}

        allowed = ["1mo", "3mo", "6mo", "1y", "2y"]
        if period not in allowed:
            period = "3mo"

        try:
            ticker = yf.Ticker(info["ticker"])
            hist = ticker.history(period=period)
            candles = []
            for date, row in hist.iterrows():
                candles.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                })
            return {
                "asset_id": asset_id,
                "name": info["name"],
                "period": period,
                "candles": candles,
                "currency": info.get("currency", "$"),
            }
        except Exception as e:
            logger.error(f"Price history error for {asset_id}: {e}")
            return {"error": str(e), "candles": []}

    @router.get("/api/history/{asset_id}")
    async def get_history(asset_id: str, limit: int = 50):
        """Return analysis history for a specific asset."""
        from analysis_store import store
        return store.get_analysis_history(asset_id, limit)

    @router.get("/api/trending")
    async def get_trending():
        return {"trending": [], "source": "rss"}

    @router.get("/api/sentiment-stats")
    async def get_sentiment_stats(symbols: str = "AAPL,TSLA,NVDA,MSFT,GOOGL", days: int = 7):
        return {"stats": {}, "days": days}

    @router.get("/api/global-news")
    async def get_global_news(
        countries: str = "",
        industries: str = "",
        entity_types: str = "equity",
        language: str = "en",
        search: str = "",
        limit: int = 30,
    ):
        return {"news": data_service.get_news()[:limit], "trending": [], "count": 0}
