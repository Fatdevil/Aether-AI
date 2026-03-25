"""
Aether AI Backend - FastAPI Server
Hämtar riktiga priser via yfinance, nyheter via RSS och tillhandahåller REST API.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else

from fastapi import FastAPI, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware

from data_service import DataService
from ai_engine import get_system_info
from risk_manager import PortfolioRiskManager
from transaction_filter import filter_rebalancing
from agent_performance import AgentPerformanceTracker
from domain_knowledge import DomainKnowledgeManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aether")

# Global data service
data_service = DataService()

# Global risk & regime managers
risk_manager = PortfolioRiskManager()
perf_tracker = AgentPerformanceTracker()
domain_mgr = DomainKnowledgeManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: fetch initial data. Shutdown: cleanup."""
    logger.info("🚀 Aether AI Backend starting...")
    await data_service.refresh_all()
    # Start background refresh loop
    task = asyncio.create_task(background_refresh())
    yield
    task.cancel()
    logger.info("Aether AI Backend shutting down.")


async def background_refresh():
    """Refresh market data every 5 minutes."""
    while True:
        await asyncio.sleep(300)  # 5 min
        try:
            logger.info("🔄 Refreshing market data...")
            await data_service.refresh_all()
            logger.info("✅ Market data refreshed.")
        except Exception as e:
            logger.error(f"❌ Refresh failed: {e}")


app = FastAPI(
    title="Aether AI - Macro & Micro Analyst",
    description="AI-driven market analysis backend",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_refresh": data_service.last_refresh,
    }


@app.get("/api/assets")
async def get_assets():
    """Return all assets with current prices and AI analysis."""
    return data_service.get_assets()


@app.get("/api/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Return detailed analysis for a single asset."""
    asset = data_service.get_asset(asset_id)
    if not asset:
        return {"error": "Asset not found"}, 404
    return asset


@app.get("/api/news")
async def get_news():
    """Return aggregated news feed enriched with sentinel impact data."""
    from news_sentinel import sentinel
    news = data_service.get_news()
    
    # Merge ALL sentinel evaluations into news items (not just high-impact alerts)
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


@app.get("/api/portfolio")
async def get_portfolio():
    """Return AI-recommended portfolio allocation."""
    return data_service.get_portfolio()


@app.get("/api/market-state")
async def get_market_state():
    """Return overall market state summary."""
    return data_service.get_market_state()


@app.get("/api/sectors")
async def get_sectors():
    """Return all sector analyses with scores and rotation signals."""
    return data_service.get_sectors()


@app.get("/api/regions")
async def get_regions():
    """Return all geographic region analyses with scores and allocation signals."""
    return data_service.get_regions()


@app.post("/api/refresh")
async def force_refresh():
    """Force a full data + analysis refresh (all tiers)."""
    await data_service.refresh_all(force=True)
    return {"status": "refreshed", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/scheduler")
async def get_scheduler_status():
    """Return tiered scheduler status."""
    from scheduler import scheduler
    return scheduler.get_status()


@app.get("/api/alerts")
async def get_alerts(min_impact: int = 1):
    """Return recent sentinel alerts filtered by minimum impact score."""
    from news_sentinel import sentinel
    return {
        "alerts": sentinel.get_alerts(min_impact),
        "stats": sentinel.get_stats(),
    }


@app.post("/api/alerts/test")
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


@app.get("/api/system")
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


@app.get("/api/performance")
async def get_performance():
    """Return AI performance / accuracy dashboard data."""
    from evaluator import evaluator
    return evaluator.get_performance_report()


@app.get("/api/history/{asset_id}")
async def get_history(asset_id: str, limit: int = 50):
    """Return analysis history for a specific asset."""
    from analysis_store import store
    return store.get_analysis_history(asset_id, limit)


@app.get("/api/calendar")
async def get_calendar():
    """Return upcoming and recent economic events."""
    from economic_calendar import calendar
    return calendar.get_summary()


@app.get("/api/correlations")
async def get_correlations(period: str = "30d"):
    """Return cross-asset correlation matrix and systemic signal."""
    from correlation_engine import correlation_engine
    if period not in ("7d", "30d", "90d", "180d"):
        period = "30d"
    return correlation_engine.calculate_correlations(period=period)


@app.get("/api/correlations/insights")
async def get_correlation_insights(period: str = "30d"):
    """AI-powered analysis of the correlation matrix."""
    from correlation_engine import correlation_engine
    from llm_provider import call_llm

    if period not in ("7d", "30d", "90d", "180d"):
        period = "30d"

    corr_data = correlation_engine.calculate_correlations(period=period)
    if not corr_data or "matrix" not in corr_data:
        return {"insights": [], "source": "none"}

    matrix = corr_data["matrix"]
    systemic = corr_data.get("systemic", {})
    notable = corr_data.get("notable_pairs", [])

    # Build a compact text representation
    name_map = {
        "btc": "Bitcoin", "sp500": "S&P 500", "gold": "Guld", "silver": "Silver",
        "oil": "Olja", "us10y": "US 10Y Räntor", "eurusd": "EUR/USD", "global-equity": "ACWI",
    }

    matrix_text = "Korrelationsmatris (senaste " + period + "):\n"
    assets = list(matrix.keys())
    for a in assets:
        for b in assets:
            if a < b:
                val = matrix[a].get(b, 0)
                if abs(val) >= 0.25:
                    matrix_text += f"  {name_map.get(a,a)} ↔ {name_map.get(b,b)}: {val:+.2f}\n"

    regime_text = f"Marknadsregim: {systemic.get('regime', 'okänt')}, {systemic.get('risk_on_count', 0)} risk-on, {systemic.get('risk_off_count', 0)} risk-off"

    system_prompt = """Du är en erfaren portföljanalytiker. Analysera korrelationsmatrisen och ge 3-5 korta, actionable insikter på svenska.

Fokusera på:
1. KONCENTRATIONSRISKER – vilka tillgångar som rör sig likt (korrelation > 0.7) och vad det innebär
2. HEDGING-MÖJLIGHETER – negativa korrelationer som ger diversifiering
3. AVVIKELSER – ovanliga korrelationer som avviker från det normala
4. ACTIONABLE RÅD – konkreta handlingar att överväga

Format: Returnera exakt en JSON-array med objekt: [{"icon": "emoji", "title": "kort titel", "text": "2-3 meningar med insikt och handlingsråd"}]
Max 5 insikter. Skriv på svenska. Var konkret och specifik, inte generell."""

    user_prompt = f"""{matrix_text}

{regime_text}

Starkaste par: {', '.join(f"{name_map.get(p['asset_a'],p['asset_a'])}↔{name_map.get(p['asset_b'],p['asset_b'])} ({p['correlation']:+.2f})" for p in notable[:6])}

Ge 3-5 actionable insikter om denna matris. Svara BARA med JSON-arrayen."""

    try:
        response = await call_llm("gemini", system_prompt, user_prompt, temperature=0.3, max_tokens=800)
        if response:
            import json as _json
            # Extract JSON from response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            insights = _json.loads(text)
            if isinstance(insights, list):
                return {"insights": insights[:5], "source": "ai", "period": period}
    except Exception as e:
        logger.warning(f"AI correlation insights failed: {e}")

    # Rule-based fallback
    insights = _generate_rule_based_insights(matrix, systemic, notable, period, name_map)
    return {"insights": insights, "source": "rule_based", "period": period}


def _generate_rule_based_insights(matrix, systemic, notable, period, name_map):
    """Generate insights without LLM."""
    insights = []

    # 1. Concentration risk
    high_corr = [p for p in notable if p["correlation"] > 0.7]
    if high_corr:
        pairs_text = ", ".join(f"{name_map.get(p['asset_a'],p['asset_a'])}↔{name_map.get(p['asset_b'],p['asset_b'])} ({p['correlation']:+.2f})" for p in high_corr[:3])
        insights.append({
            "icon": "⚠️",
            "title": "Koncentrationsrisk",
            "text": f"Dessa tillgångar rör sig nästan identiskt ({period}): {pairs_text}. Om du äger flera av dem ger de inte diversifiering – överväg att minska i en."
        })

    # 2. Hedging opportunities
    neg_corr = [p for p in notable if p["correlation"] < -0.4]
    if neg_corr:
        best = neg_corr[0]
        insights.append({
            "icon": "🛡️",
            "title": "Hedging-möjlighet",
            "text": f"{name_map.get(best['asset_a'],best['asset_a'])} och {name_map.get(best['asset_b'],best['asset_b'])} har {best['correlation']:+.2f} korrelation. Kombinationen ger effektiv riskspridning – om en faller tenderar den andra att stiga."
        })

    # 3. Regime signal
    regime = systemic.get("regime", "")
    risk_on = systemic.get("risk_on_count", 0)
    risk_off = systemic.get("risk_off_count", 0)
    if regime in ("risk-off", "leaning-risk-off"):
        insights.append({
            "icon": "📉",
            "title": "Risk-Off läge",
            "text": f"{risk_off} av 7 tillgångar signalerar risk-off. Defensiva tillgångar (Guld, obligationer) tenderar att prestera bättre. Överväg att minska aktiexponering."
        })
    elif regime in ("risk-on", "leaning-risk-on"):
        insights.append({
            "icon": "📈",
            "title": "Risk-On läge",
            "text": f"{risk_on} av 7 tillgångar signalerar risk-on. Riskaptiten driver marknaden – aktier och BTC tenderar att prestera bäst. Säkerhetshedge via Guld kan vara billig just nu."
        })

    # 4. BTC decorrelation check
    btc_sp = matrix.get("btc", {}).get("sp500", 0)
    if abs(btc_sp) < 0.2:
        insights.append({
            "icon": "₿",
            "title": "BTC dekorrelerad",
            "text": f"Bitcoin och S&P 500 har bara {btc_sp:+.2f} korrelation ({period}). BTC handlas på egna drivers (on-chain/krypto-specifikt) – ger verklig diversifiering just nu."
        })
    elif btc_sp > 0.6:
        insights.append({
            "icon": "🔗",
            "title": "BTC tightly coupled",
            "text": f"Bitcoin följer S&P 500 nära ({btc_sp:+.2f}). Krypto ger ingen diversifiering mot aktier – de faller och stiger tillsammans."
        })

    # 5. Ensure at least 2 insights
    if len(insights) < 2:
        insights.append({
            "icon": "📊",
            "title": "Normal korrelationsstruktur",
            "text": f"Inga extrema korrelationsmönster detekterade ({period}). Marknaden beter sig normalt – ingen speciell åtgärd krävs."
        })

    return insights[:5]


@app.get("/api/regime")
async def get_regime():
    """Return current market regime detection."""
    from regime_detector import regime_detector
    return regime_detector.detect_regime()


@app.get("/api/signals")
async def get_signals():
    """Return trade signals for all assets."""
    from trade_signals import signal_generator
    signals = {}
    try:
        price_map = data_service.prices  # {asset_id: {price, changePct, indicators, ...}}
        assets = data_service.assets     # [{id, finalScore, ...}, ...]

        for asset_data in assets:
            asset_id = asset_data.get("id", "")
            price_info = price_map.get(asset_id, {})
            if not price_info or not price_info.get("price"):
                continue

            # Build price_data in the format signal generator expects
            price_data = {
                "price": price_info.get("price", 0),
                "indicators": price_info.get("indicators", {}),
            }

            # Build analysis dict from stored asset
            analysis = {
                "finalScore": asset_data.get("finalScore", 0),
                "supervisorConfidence": 0.6,
                "recommendation": _score_to_rec(asset_data.get("finalScore", 0)),
            }

            signals[asset_id] = signal_generator.generate_signal(asset_id, analysis, price_data)
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
    return {"signals": signals}


def _score_to_rec(score: float) -> str:
    if score >= 5: return "Starkt Köp"
    if score >= 2: return "Köp"
    if score <= -5: return "Starkt Sälj"
    if score <= -2: return "Sälj"
    return "Neutral"


@app.get("/api/onchain")
async def get_onchain():
    """Return BTC on-chain data."""
    from onchain_data import fetch_onchain_data
    return await fetch_onchain_data()


@app.get("/api/portfolio/risk")
async def get_portfolio_risk():
    """Return portfolio summary with live P/L and risk metrics (CVaR, Monte Carlo, etc)."""
    from portfolio_manager import portfolio
    return portfolio.get_portfolio_summary(data_service.prices)


@app.post("/api/portfolio/positions")
async def add_position(body: dict):
    """Add a new portfolio position."""
    from portfolio_manager import portfolio
    result = portfolio.add_position(
        asset_id=body.get("asset_id", ""),
        quantity=body.get("quantity", 0),
        entry_price=body.get("entry_price", 0),
        entry_date=body.get("entry_date", ""),
        asset_name=body.get("asset_name", ""),
        currency=body.get("currency", "$"),
        notes=body.get("notes", ""),
    )
    return result


@app.delete("/api/portfolio/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a portfolio position."""
    from portfolio_manager import portfolio
    success = portfolio.delete_position(position_id)
    return {"success": success}


@app.get("/api/portfolio/history")
async def get_portfolio_history(limit: int = 100):
    """Return portfolio value history."""
    from portfolio_manager import portfolio
    return portfolio.get_history(limit)


@app.get("/api/portfolio/trades")
async def get_closed_trades(limit: int = 50):
    """Return closed trade history."""
    from portfolio_manager import portfolio
    return portfolio.get_closed_trades(limit)


@app.get("/api/backtest")
async def get_backtest():
    """Return AI prediction accuracy and backtesting data."""
    from evaluator import evaluator
    return evaluator.get_performance_report()


@app.get("/api/portfolio/history")
async def get_portfolio_history(days: int = 7):
    """Return portfolio score history for charting."""
    from analysis_store import store
    from datetime import datetime, timezone, timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = store._get_conn()
    rows = conn.execute("""
        SELECT timestamp, asset_id, final_score, price_at_analysis
        FROM analyses
        WHERE analysis_type = 'asset' AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (cutoff,)).fetchall()
    conn.close()

    # Group by timestamp (rounded to nearest analysis cycle)
    from collections import defaultdict
    cycles = defaultdict(dict)
    for r in rows:
        ts = r["timestamp"][:16]  # Truncate to minute
        cycles[ts][r["asset_id"]] = {
            "score": r["final_score"],
            "price": r["price_at_analysis"],
        }

    # Build timeline
    history = []
    for ts, assets in sorted(cycles.items()):
        if len(assets) < 3:  # Skip incomplete cycles
            continue
        scores = [a["score"] for a in assets.values()]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0
        buy_count = sum(1 for s in scores if s > 2.5)
        sell_count = sum(1 for s in scores if s < -2.5)
        history.append({
            "timestamp": ts,
            "avg_score": avg_score,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "assets_analyzed": len(assets),
        })

    return {"history": history, "total_cycles": len(history)}


@app.get("/api/predictions/outcomes")
async def get_predictions_outcomes(limit: int = 100):
    """Return prediction vs actual outcome pairs for charting."""
    from analysis_store import store
    conn = store._get_conn()
    rows = conn.execute("""
        SELECT e.asset_id, e.timeframe, e.predicted_direction, e.actual_direction,
               e.direction_correct, e.actual_change_pct, e.score_at_analysis,
               e.evaluated_at, a.asset_name
        FROM evaluations e
        LEFT JOIN analyses a ON a.id = e.analysis_id
        WHERE e.timeframe IN ('1h', '4h', '24h')
        ORDER BY e.evaluated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    return {
        "outcomes": [dict(r) for r in rows],
        "total": len(rows),
    }


@app.get("/api/ensemble/status")
async def get_ensemble_status_api():
    """Return current ensemble system status."""
    from meta_supervisor import get_ensemble_status
    return get_ensemble_status()


# ===== Marketaux Trending & Sentiment =====

@app.get("/api/trending")
async def get_trending():
    """Return trending entities from Marketaux."""
    from news_service import fetch_trending_entities
    trending = fetch_trending_entities()
    return {"trending": trending, "source": "marketaux"}


@app.get("/api/sentiment-stats")
async def get_sentiment_stats(symbols: str = "AAPL,TSLA,NVDA,MSFT,GOOGL", days: int = 7):
    """Return sentiment time series for given symbols."""
    from news_service import fetch_entity_sentiment_stats
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    stats = fetch_entity_sentiment_stats(symbol_list, days)
    return {"stats": stats, "days": days}


@app.get("/api/global-news")
async def get_global_news(
    countries: str = "",
    industries: str = "",
    entity_types: str = "equity",
    language: str = "en",
    search: str = "",
    limit: int = 30,
):
    """Fetch filterable global news from Marketaux."""
    from news_service import _fetch_mx_page, fetch_trending_entities
    import os
    import httpx

    api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        return {"news": data_service.get_news()[:limit], "trending": [], "count": 0}

    params = {
        "filter_entities": "true",
        "must_have_entities": "true",
        "limit": min(limit, 50),
    }

    if countries:
        params["countries"] = countries
    if industries:
        params["industries"] = industries
    if entity_types:
        params["entity_types"] = entity_types
    if language:
        params["language"] = language
    if search:
        params["search"] = search

    news_items = []
    try:
        with httpx.Client(timeout=20.0) as client:
            _fetch_mx_page(client, api_key, params, news_items)
    except Exception:
        pass

    # Also get trending for same filters
    trending = []
    try:
        with httpx.Client(timeout=15.0) as client:
            t_params = {
                "api_token": api_key,
                "min_doc_count": 3,
                "limit": 15,
            }
            if countries:
                t_params["countries"] = countries
            if language:
                t_params["language"] = language
            response = client.get(
                "https://api.marketaux.com/v1/entity/trending/aggregation",
                params=t_params,
            )
            if response.status_code == 200:
                data = response.json()
                for e in data.get("data", []):
                    trending.append({
                        "symbol": e.get("key", ""),
                        "mentions": e.get("total_documents", 0),
                        "sentiment_avg": round(e.get("sentiment_avg", 0) or 0, 3),
                        "score": round(e.get("score", 0) or 0, 2),
                    })
    except Exception:
        pass

    return {"news": news_items, "trending": trending, "count": len(news_items)}


# ===== Risk Profile Portfolios =====

@app.get("/api/risk-profiles")
async def get_risk_profiles():
    """Return 3 risk-profiled AI portfolios + regime advice."""
    from ai_engine import generate_risk_portfolios

    # Build assets_analysis from current data
    assets_analysis = {}
    for asset in data_service.assets:
        assets_analysis[asset["id"]] = {
            "finalScore": asset.get("finalScore", 0),
            "name": asset.get("name", asset["id"]),
        }

    if not assets_analysis:
        return {"profiles": {}, "regime": {"regime": "neutral", "recommended_profile": "balanced", "advice": "Ingen data tillgänglig."}}

    # === Extract macro signals for scoring ===
    overall_score = sum(a.get("finalScore", 0) for a in assets_analysis.values()) / max(len(assets_analysis), 1)
    oil_score = assets_analysis.get("oil", {}).get("finalScore", 0)
    rates_score = assets_analysis.get("us10y", {}).get("finalScore", 0)
    equity_score = assets_analysis.get("sp500", {}).get("finalScore", 0)
    gold_score = assets_analysis.get("gold", {}).get("finalScore", 0)
    eurusd_score = assets_analysis.get("eurusd", {}).get("finalScore", 0)
    btc_score = assets_analysis.get("btc", {}).get("finalScore", 0)

    # === Fas 2+3: Sector & Region scoring via momentum ranking (#4) ===
    try:
        from signal_optimizer import compute_momentum_scores
        momentum = compute_momentum_scores()
    except Exception as e:
        logger.warning(f"⚠️ Momentum ranking failed, using heuristic fallback: {e}")
        momentum = {}

    # Sector ETFs — use momentum if available, fallback to heuristic
    sector_ids = ["sector-finance", "sector-energy", "sector-tech", "sector-health", "sector-defense"]
    region_ids = ["region-em", "region-europe", "region-japan", "region-india"]

    # Heuristic fallback scores (same as before)
    heuristic_scores = {
        "sector-finance": round(rates_score * 0.5 + equity_score * 0.3 + overall_score * 0.2, 1),
        "sector-energy": round(oil_score * 0.6 + equity_score * 0.2 + overall_score * 0.2, 1),
        "sector-tech": round(equity_score * 0.4 - rates_score * 0.3 + overall_score * 0.3, 1),
        "sector-health": round(-overall_score * 0.3 + gold_score * 0.3 + 1.0, 1),
        "sector-defense": round(gold_score * 0.4 - overall_score * 0.2 + 1.5, 1),
        "region-em": round(max(-5, min(5, -eurusd_score * 0.3 + oil_score * 0.2 + equity_score * 0.3 + overall_score * 0.2)), 1),
        "region-europe": round(max(-5, min(5, eurusd_score * 0.4 + equity_score * 0.3 + overall_score * 0.3)), 1),
        "region-japan": round(max(-5, min(5, -rates_score * 0.3 + equity_score * 0.3 + overall_score * 0.2 + 0.5)), 1),
        "region-india": round(max(-5, min(5, equity_score * 0.3 + btc_score * 0.2 + overall_score * 0.3 + 1.0)), 1),
    }

    from portfolio_optimizer import ASSET_NAMES

    for asset_id in sector_ids + region_ids:
        if asset_id in momentum and "score" in momentum[asset_id]:
            # Use momentum-ranked score (data-driven)
            mom_data = momentum[asset_id]
            score = mom_data["score"]
            # Blend: 70% momentum + 30% heuristic (smooths transitions)
            heuristic = heuristic_scores.get(asset_id, 0)
            blended = round(score * 0.7 + heuristic * 0.3, 1)
            blended = max(-5, min(5, blended))
        else:
            # Pure heuristic fallback
            blended = heuristic_scores.get(asset_id, 0)

        assets_analysis[asset_id] = {
            "finalScore": blended,
            "name": ASSET_NAMES.get(asset_id, asset_id),
        }

    # === Leveraged ETFs (Turbo profile) ===
    # Scored as amplified versions of their underlying (2x equity signal)
    lev_sp500_score = max(-5, min(5, equity_score * 2.0))
    lev_nasdaq_score = max(-5, min(5, equity_score * 1.5 + overall_score * 0.5))
    assets_analysis["leveraged-sp500"] = {"finalScore": round(lev_sp500_score, 1), "name": "S&P 500 2x (SSO)"}
    assets_analysis["leveraged-nasdaq"] = {"finalScore": round(lev_nasdaq_score, 1), "name": "Nasdaq 2x (QLD)"}

    market_state = data_service.get_market_state()
    result = generate_risk_portfolios(assets_analysis, market_state)
    return result


@app.get("/api/signal-weights")
async def get_signal_weights_api():
    """Return trained signal weights and momentum rankings."""
    from signal_optimizer import get_signal_weights, compute_momentum_scores
    try:
        weights = get_signal_weights()
        momentum = compute_momentum_scores()
        return {"signal_weights": weights, "momentum_rankings": momentum}
    except Exception as e:
        logger.error(f"Signal weights failed: {e}")
        return {"error": str(e), "signal_weights": {}, "momentum_rankings": {}}


@app.get("/api/composite-portfolio")
async def get_composite_portfolio():
    """Return AI composite portfolio backtest — regime-switching track record."""
    from composite_backtest import run_composite_backtest
    try:
        result = run_composite_backtest()
        return result
    except Exception as e:
        logger.error(f"Composite backtest failed: {e}")
        return {"error": str(e), "equity_curve": [], "benchmark_curve": [], "regime_log": [], "stats": {}}


@app.get("/api/feedback-stats")
async def get_feedback_stats():
    """Return AI feedback analysis — hit rates, drawdown episodes, learning insights."""
    from regime_feedback import analyze_regime_feedback
    try:
        result = analyze_regime_feedback()
        return result
    except Exception as e:
        logger.error(f"Feedback analysis failed: {e}")
        return {"error": str(e), "insights": [], "hit_rates": {}, "drawdown_episodes": [], "switch_scores": []}


# ===== User Portfolio Endpoints =====

@app.get("/api/user-portfolio/news")
async def get_portfolio_news(tickers: str = ""):
    """Fetch news for specific portfolio tickers."""
    from news_service import _fetch_mx_page
    import os
    import httpx

    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {"news": [], "count": 0}

    api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        # Fallback: filter from existing news
        all_news = data_service.get_news()
        filtered = [n for n in all_news if any(t.upper() in [tk.upper() for tk in n.get("tickers", [])] for t in ticker_list)]
        return {"news": filtered[:20], "count": len(filtered)}

    # Fetch from Marketaux for these specific tickers
    news_items = []
    try:
        with httpx.Client(timeout=15.0) as client:
            _fetch_mx_page(client, api_key, {
                "symbols": ",".join(ticker_list[:10]),
                "filter_entities": "true",
                "limit": 30,
                "language": "en",
            }, news_items)
    except Exception:
        pass

    return {"news": news_items[:20], "count": len(news_items)}

@app.post("/api/user-portfolio/parse-image")
async def parse_portfolio_image_endpoint(file: UploadFile):
    """Parse a portfolio screenshot using Gemini Vision."""
    from user_portfolio import parse_portfolio_image
    contents = await file.read()
    result = await parse_portfolio_image(contents, file.filename or "image.png")
    return result


@app.get("/api/user-portfolio/search")
async def search_ticker_endpoint(q: str):
    """Search for a stock/fund ticker."""
    from user_portfolio import search_ticker
    results = await search_ticker(q)
    return {"results": results}


@app.post("/api/user-portfolio/save")
async def save_portfolio_endpoint(request: Request):
    """Save a user portfolio."""
    from user_portfolio import save_portfolio
    data = await request.json()
    pid = save_portfolio(
        name=data.get("name", "Min Portfölj"),
        holdings=data.get("holdings", []),
        total_value=data.get("total_value", 0),
    )
    return {"id": pid, "status": "saved"}


@app.get("/api/user-portfolio/list")
async def list_portfolios_endpoint():
    """List all user portfolios."""
    from user_portfolio import get_portfolios
    return {"portfolios": get_portfolios()}


@app.delete("/api/user-portfolio/{portfolio_id}")
async def delete_portfolio_endpoint(portfolio_id: int):
    """Delete a user portfolio."""
    from user_portfolio import delete_portfolio
    delete_portfolio(portfolio_id)
    return {"status": "deleted"}


@app.post("/api/user-portfolio/compare")
async def compare_portfolios_endpoint(request: Request):
    """Compare user portfolio against AI optimal."""
    from user_portfolio import compare_portfolios, fetch_holdings_data, calculate_efficient_frontier

    data = await request.json()
    holdings = data.get("holdings", [])

    # Enrich with live prices
    enriched = await fetch_holdings_data(holdings)

    # Get AI portfolio from data_service (same as /api/portfolio)
    ai_portfolio = data_service.get_portfolio()

    # Compare
    comparison = await compare_portfolios(enriched, ai_portfolio)

    # Calculate efficient frontier
    frontier = await calculate_efficient_frontier(
        enriched, ai_portfolio.get("allocations", [])
    )

    return {
        "user_holdings": enriched,
        "ai_portfolio": ai_portfolio,
        "comparison": comparison,
        "frontier": frontier,
    }


# ============================================================
# RegimeTransition: Gradual regime change with confirmation
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RegimeTransition:
    """Hanterar gradvis övergång mellan regimer"""
    current_regime: str = "NEUTRAL"
    target_regime: str = "NEUTRAL"
    transition_start: Optional[datetime] = None
    transition_days: int = 3           # 3-dagars bekräftelse
    blend_steps: int = 3               # 3 steg för gradvis övergång
    current_step: int = 0
    confirmed: bool = True

    def signal_new_regime(self, detected_regime: str) -> dict:
        """Anropas varje dag med detekterad regim."""
        if detected_regime == self.current_regime:
            self.target_regime = self.current_regime
            self.transition_start = None
            self.current_step = 0
            self.confirmed = True
            return {
                "action": "HOLD",
                "regime": self.current_regime,
                "blend": {self.current_regime: 1.0},
                "message": f"Stabil {self.current_regime}-regim"
            }

        if detected_regime != self.target_regime:
            self.target_regime = detected_regime
            self.transition_start = datetime.now()
            self.current_step = 0
            self.confirmed = False
            return {
                "action": "WAIT",
                "regime": self.current_regime,
                "blend": {self.current_regime: 1.0},
                "message": f"Ny signal: {detected_regime}. Väntar bekräftelse (dag 1/{self.transition_days})"
            }

        # Samma target som förut — räkna bekräftelsedagar
        if self.transition_start:
            days = (datetime.now() - self.transition_start).days

            if days < self.transition_days and not self.confirmed:
                return {
                    "action": "WAIT",
                    "regime": self.current_regime,
                    "blend": {self.current_regime: 1.0},
                    "message": f"Bekräftar {self.target_regime} (dag {days+1}/{self.transition_days})"
                }

            # Bekräftad! Starta gradvis övergång
            self.confirmed = True
            self.current_step += 1
            blend_pct = min(self.current_step / self.blend_steps, 1.0)

            if blend_pct >= 1.0:
                self.current_regime = self.target_regime
                self.current_step = 0
                return {
                    "action": "COMPLETE",
                    "regime": self.current_regime,
                    "blend": {self.current_regime: 1.0},
                    "message": f"Regimövergång till {self.current_regime} klar"
                }

            return {
                "action": "TRANSITION",
                "regime": f"{self.current_regime}->{self.target_regime}",
                "blend": {
                    self.current_regime: round(1.0 - blend_pct, 2),
                    self.target_regime: round(blend_pct, 2)
                },
                "message": f"Övergår till {self.target_regime}: steg {self.current_step}/{self.blend_steps} ({blend_pct*100:.0f}%)"
            }

        return {"action": "HOLD", "regime": self.current_regime, "blend": {self.current_regime: 1.0}}

    def get_blended_weights(
        self,
        regime_weights: dict,
        blend: dict
    ) -> dict:
        """Blanda vikter från två regimer baserat på blend-procent."""
        result = {}
        all_assets = set()
        for weights in regime_weights.values():
            all_assets.update(weights.keys())

        for asset in all_assets:
            blended = 0.0
            for regime, pct in blend.items():
                regime_w = regime_weights.get(regime, {})
                blended += regime_w.get(asset, 0) * pct
            result[asset] = round(blended, 2)

        return result


# Global regime transition manager
regime_transition = RegimeTransition()


# ============================================================
# New API Endpoints
# ============================================================

from pydantic import BaseModel


class PortfolioUpdate(BaseModel):
    portfolio_value: float
    profile: str = "balanced"


class RebalanceRequest(BaseModel):
    current_weights: dict
    target_weights: dict
    portfolio_value: float


@app.post("/api/risk-check")
async def check_risk(update: PortfolioUpdate):
    """Kolla trailing stop och risk-status"""
    result = risk_manager.update(update.portfolio_value, update.profile)
    return result


@app.post("/api/filter-trades")
async def filter_trades_endpoint(request: RebalanceRequest):
    """Filtrera trades baserat på courtage vs förväntad förbättring"""
    trades = filter_rebalancing(
        request.current_weights,
        request.target_weights,
        request.portfolio_value
    )
    approved = {k: v for k, v in trades.items() if v["should_trade"]}
    blocked = {k: v for k, v in trades.items() if not v["should_trade"]}

    return {
        "approved_trades": approved,
        "blocked_trades": blocked,
        "total_fee_cost": sum(v["fee_cost_sek"] for v in approved.values()),
        "n_approved": len(approved),
        "n_blocked": len(blocked)
    }


@app.get("/api/walkforward")
async def run_walkforward():
    """Kör walk-forward-backtest med historisk data"""
    import pandas as pd
    from walkforward_backtest import WalkForwardEngine, WalkForwardConfig
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}

    # Build price data from returns (cumulative)
    price_data = (1 + returns).cumprod() * 100

    # Generate signal scores from momentum (proxy signals)
    signals = pd.DataFrame(index=returns.index)
    for col in returns.columns:
        # ROC 10d as signal
        signals[f"{col}_mom"] = returns[col].rolling(10).mean() * 100

    signals = signals.dropna()
    price_data = price_data.loc[signals.index]

    engine = WalkForwardEngine(WalkForwardConfig(
        train_months=12,
        test_months=3,
        min_train_samples=200
    ))
    result = engine.run(price_data, signals)
    return result


@app.get("/api/regime-transition")
async def get_regime_status():
    """Hämta aktuell regim-övergångs-status"""
    return {
        "current_regime": regime_transition.current_regime,
        "target_regime": regime_transition.target_regime,
        "confirmed": regime_transition.confirmed,
        "step": regime_transition.current_step,
        "blend_steps": regime_transition.blend_steps,
        "transition_days": regime_transition.transition_days
    }


# ============================================================
# Del 2 API Endpoints
# ============================================================

class DomainNote(BaseModel):
    text: str
    category: str = "general"
    priority: int = 5


class PortfolioWeights(BaseModel):
    weights: dict


@app.get("/api/agent-performance")
async def get_agent_performance(lookback_days: int = 90):
    """Hämta prestandarapport per agent"""
    return perf_tracker.get_agent_report(lookback_days)


@app.post("/api/risk-attribution")
async def get_risk_attribution(portfolio: PortfolioWeights):
    """Vilken position bidrar mest till portföljrisk?"""
    from risk_attribution import RiskAttribution
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    # Filter weights to only include assets in returns data
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar i historisk data", "available": list(returns.columns)}
    attr = RiskAttribution(returns, valid_weights)
    return attr.compute()


@app.post("/api/stress-test")
async def run_stress_test(portfolio: PortfolioWeights):
    """Monte Carlo + historiska scenarier"""
    from stress_test import MonteCarloStressTest
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar", "available": list(returns.columns)}
    mc = MonteCarloStressTest(returns, n_simulations=10000, horizon_days=21)
    result = mc.run(valid_weights)
    result["historical"] = mc.historical_scenarios(valid_weights)
    return result


@app.post("/api/efficient-frontier")
async def analyze_frontier(portfolio: PortfolioWeights):
    """Var på effektiva fronten ligger din portfölj?"""
    from efficient_frontier import EfficientFrontierAnalyzer
    returns = data_service.get_historical_returns()
    if returns.empty:
        return {"error": "Ingen historisk data tillgänglig"}
    valid_weights = {k: v for k, v in portfolio.weights.items() if k in returns.columns}
    if not valid_weights:
        return {"error": "Inga matchande tillgångar", "available": list(returns.columns)}
    ef = EfficientFrontierAnalyzer(returns)
    return ef.analyze_portfolio(valid_weights)


@app.post("/api/domain-note")
async def add_domain_note(note: DomainNote):
    """Lägg till domänkunskap som injiceras i alla agenter"""
    return domain_mgr.add_note(note.text, note.category, note.priority)


@app.get("/api/domain-notes")
async def get_domain_notes():
    """Hämta alla aktiva domännoteringar"""
    return domain_mgr.get_active_notes()


@app.delete("/api/domain-note/{note_id}")
async def delete_domain_note(note_id: int):
    """Ta bort en domännotering"""
    domain_mgr.remove_note(note_id)
    return {"status": "removed"}
