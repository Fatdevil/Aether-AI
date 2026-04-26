"""
Aether AI — Portfolio Routes
Portfolio management, core-satellite, broker comparison, user portfolio.
Extracted from main.py for modularity.
"""
from fastapi import APIRouter, Request, UploadFile
from pydantic import BaseModel, Field

import logging

logger = logging.getLogger("aether")

router = APIRouter(tags=["Portfolio"])


class AddPositionRequest(BaseModel):
    """S2 FIX: Pydantic validation for portfolio positions."""
    asset_id: str = Field(..., min_length=1, max_length=50)
    quantity: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    entry_date: str = ""
    asset_name: str = ""
    currency: str = "$"
    notes: str = ""


def setup(data_service, risk_manager, event_tree_engine, _last_pipeline_result_getter):
    """Register routes. _last_pipeline_result_getter is a callable that returns current pipeline result."""

    @router.get("/api/portfolio/risk")
    async def get_portfolio_risk():
        """Return portfolio summary with live P/L and risk metrics."""
        from portfolio_manager import portfolio
        return portfolio.get_portfolio_summary(data_service.prices)

    @router.post("/api/portfolio/positions")
    async def add_position(body: AddPositionRequest):
        """Add a new portfolio position."""
        from portfolio_manager import portfolio
        result = portfolio.add_position(
            asset_id=body.asset_id,
            quantity=body.quantity,
            entry_price=body.entry_price,
            entry_date=body.entry_date,
            asset_name=body.asset_name,
            currency=body.currency,
            notes=body.notes,
        )
        return result

    @router.delete("/api/portfolio/positions/{position_id}")
    async def delete_position(position_id: str):
        """Delete a portfolio position."""
        from portfolio_manager import portfolio
        success = portfolio.delete_position(position_id)
        return {"success": success}

    @router.get("/api/portfolio/history")
    async def get_portfolio_history(limit: int = 100):
        """Return portfolio value history."""
        from portfolio_manager import portfolio
        return portfolio.get_history(limit)

    @router.get("/api/portfolio/trades")
    async def get_closed_trades(limit: int = 50):
        """Return closed trade history."""
        from portfolio_manager import portfolio
        return portfolio.get_closed_trades(limit)

    @router.get("/api/backtest")
    async def get_backtest():
        """Return AI prediction accuracy and backtesting data."""
        from evaluator import evaluator
        return evaluator.get_performance_report()

    @router.get("/api/portfolio/score-history")
    async def get_portfolio_score_history(days: int = 7):
        """Return portfolio score history for charting."""
        from analysis_store import store
        from datetime import datetime, timezone, timedelta
        from collections import defaultdict

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = store._get_conn()
        rows = conn.execute("""
            SELECT timestamp, asset_id, final_score, price_at_analysis
            FROM analyses
            WHERE analysis_type = 'asset' AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,)).fetchall()
        conn.close()

        cycles = defaultdict(dict)
        for r in rows:
            ts = r["timestamp"][:16]
            cycles[ts][r["asset_id"]] = {
                "score": r["final_score"],
                "price": r["price_at_analysis"],
            }

        history = []
        for ts, assets in sorted(cycles.items()):
            if len(assets) < 3:
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

    @router.get("/api/predictions/outcomes")
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

    @router.get("/api/ensemble/status")
    async def get_ensemble_status_api():
        """Return current ensemble system status."""
        from meta_supervisor import get_ensemble_status
        return get_ensemble_status()

    # ---- Core-Satellite ----

    @router.get("/api/core-satellite")
    async def get_core_satellite(
        portfolio_value: float = 700000,
        broker: str = "avanza",
    ):
        """Hämta Core-Satellite portföljrekommendation anpassad till belopp OCH mäklare."""
        from portfolio_builder import CoreSatelliteBuilder
        from broker_config import get_broker as get_broker_config, calculate_portfolio_courtage
        from regime_detector import regime_detector

        builder = CoreSatelliteBuilder()
        broker_config = get_broker_config(broker)

        regime_data = regime_detector.detect_regime()
        regime = regime_data.get("regime", "neutral") if regime_data else "neutral"

        final_scores = {}
        consensus = {}
        conviction = 0.7

        pipeline_result = _last_pipeline_result_getter()
        if pipeline_result:
            synth = pipeline_result.get("synthesis", {})
            final_scores = synth.get("final_scores", {})
            conviction = synth.get("conviction_ratio", 0.7)

        for asset in data_service.assets:
            aid = asset.get("id", "")
            score = asset.get("finalScore", 0)
            final_scores.setdefault(aid, score)
            consensus.setdefault(aid, {
                "consensus_fraction": 0.6 if abs(score) > 2 else 0.4,
                "avg_score": score,
            })

        convex = []
        try:
            convex = event_tree_engine.get_all_convex_positions()
        except Exception:
            pass

        trailing = False
        try:
            total_value = sum(
                pr.get("price", 0) if isinstance(pr, dict) else pr
                for pr in (data_service.prices or {}).values()
            )
            if total_value > 0:
                trailing = risk_manager.update(total_value).get("stop_triggered", False)
        except Exception:
            pass

        portfolio = builder.build_portfolio(
            portfolio_value=portfolio_value,
            regime=regime,
            final_scores=final_scores,
            consensus=consensus,
            conviction_ratio=conviction,
            convex_positions=convex,
            trailing_stop_active=trailing,
            broker_id=broker,
        )

        all_positions = portfolio["core"] + portfolio["satellites"]
        courtage = calculate_portfolio_courtage(broker, all_positions)
        portfolio["courtage_details"] = courtage
        portfolio["broker"] = broker_config.name

        return portfolio

    @router.get("/api/compare-brokers")
    async def compare_brokers(portfolio_value: float = 700000):
        """Jämför courtage Avanza vs Nordnet för en given portföljstorlek."""
        from portfolio_builder import CoreSatelliteBuilder
        from broker_config import calculate_portfolio_courtage

        builder = CoreSatelliteBuilder()

        results = {}
        for broker_id in ["avanza", "nordnet"]:
            portfolio = builder.build_portfolio(
                portfolio_value=portfolio_value,
                broker_id=broker_id,
                regime="neutral",
            )
            positions = portfolio["core"] + portfolio["satellites"]
            cost = calculate_portfolio_courtage(broker_id, positions)
            results[broker_id] = {
                "name": cost["broker"],
                "total_courtage_sek": cost["total_courtage_sek"],
                "total_fx_fee_sek": cost["total_fx_fee_sek"],
                "total_cost_sek": cost["total_cost_sek"],
                "positions": len(positions),
                "funds_used": sum(1 for p in positions if p.get("courtage_pct", 0) == 0),
            }

        av_cost = results["avanza"]["total_cost_sek"]
        nn_cost = results["nordnet"]["total_cost_sek"]
        if av_cost < nn_cost:
            rec = f"Avanza är billigare ({av_cost:.0f} kr vs {nn_cost:.0f} kr) tack vare fler egna fonder med 0 kr courtage."
        elif nn_cost < av_cost:
            rec = f"Nordnet är billigare ({nn_cost:.0f} kr vs {av_cost:.0f} kr)."
        else:
            rec = "Lika kostnad. Välj baserat på plattform och funktioner."

        return {
            "portfolio_value": portfolio_value,
            "avanza": results["avanza"],
            "nordnet": results["nordnet"],
            "recommendation": rec,
            "note": "Valutaväxling 0.25% tillkommer på utlandshandel hos båda. Fonder har 0 kr courtage hos båda.",
        }

    @router.get("/api/composite-portfolio")
    async def get_composite_portfolio():
        """Return AI composite portfolio backtest."""
        from composite_backtest import run_composite_backtest
        try:
            result = run_composite_backtest()
            return result
        except Exception as e:
            logger.error(f"Composite backtest failed: {e}")
            return {"error": str(e), "equity_curve": [], "benchmark_curve": [], "regime_log": [], "stats": {}}

    @router.get("/api/feedback-stats")
    async def get_feedback_stats():
        """Return AI feedback analysis."""
        from regime_feedback import analyze_regime_feedback
        try:
            result = analyze_regime_feedback()
            return result
        except Exception as e:
            logger.error(f"Feedback analysis failed: {e}")
            return {"error": str(e), "insights": [], "hit_rates": {}, "drawdown_episodes": [], "switch_scores": []}

    # ---- User Portfolio ----

    @router.get("/api/user-portfolio/news")
    async def get_portfolio_news(tickers: str = ""):
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        if not ticker_list:
            return {"news": [], "count": 0}
        all_news = data_service.get_news()
        filtered = [n for n in all_news if any(t.upper() in [tk.upper() for tk in n.get("tickers", [])] for t in ticker_list)]
        return {"news": filtered[:20], "count": len(filtered)}

    @router.post("/api/user-portfolio/parse-image")
    async def parse_portfolio_image_endpoint(file: UploadFile):
        """Parse a portfolio screenshot using Gemini Vision."""
        from user_portfolio import parse_portfolio_image
        contents = await file.read()
        result = await parse_portfolio_image(contents, file.filename or "image.png")
        return result

    @router.get("/api/user-portfolio/search")
    async def search_ticker_endpoint(q: str):
        """Search for a stock/fund ticker."""
        from user_portfolio import search_ticker
        results = await search_ticker(q)
        return {"results": results}

    @router.post("/api/user-portfolio/save")
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

    @router.get("/api/user-portfolio/list")
    async def list_portfolios_endpoint():
        """List all user portfolios."""
        from user_portfolio import get_portfolios
        return {"portfolios": get_portfolios()}

    @router.delete("/api/user-portfolio/{portfolio_id}")
    async def delete_portfolio_endpoint(portfolio_id: int):
        """Delete a user portfolio."""
        from user_portfolio import delete_portfolio
        delete_portfolio(portfolio_id)
        return {"status": "deleted"}

    @router.post("/api/user-portfolio/compare")
    async def compare_portfolios_endpoint(request: Request):
        """Compare user portfolio against AI optimal."""
        from user_portfolio import compare_portfolios, fetch_holdings_data, calculate_efficient_frontier

        data = await request.json()
        holdings = data.get("holdings", [])

        enriched = await fetch_holdings_data(holdings)
        ai_portfolio = data_service.get_portfolio()
        comparison = await compare_portfolios(enriched, ai_portfolio)
        frontier = await calculate_efficient_frontier(
            enriched, ai_portfolio.get("allocations", [])
        )

        return {
            "user_holdings": enriched,
            "ai_portfolio": ai_portfolio,
            "comparison": comparison,
            "frontier": frontier,
        }
