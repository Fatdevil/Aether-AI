"""
Data Service - Orchestrates market data, news, and AI analysis.
Caches results and provides APIs for the FastAPI endpoints.
"""

import logging
import yfinance as yf
from datetime import datetime, timezone
from typing import Optional

from market_data import fetch_all_prices, fetch_price_history, ASSET_TICKERS
from news_service import fetch_all_news
from ai_engine import analyze_asset, generate_portfolio
from sectors import SECTORS, get_sector_tickers
from regions import REGIONS, get_region_tickers
from agents.sector_agent import SectorAgent
from agents.region_agent import RegionAgent
from news_sentinel import sentinel
from scheduler import scheduler
from analysis_store import store
from evaluator import evaluator

logger = logging.getLogger("aether.data")

# Icon mapping for frontend
ICON_MAP = {
    "btc": "Bitcoin", "global-equity": "Globe", "sp500": "BarChart",
    "gold": "Coins", "silver": "Gem", "eurusd": "DollarSign",
    "oil": "Droplet", "us10y": "LineChart",
}

COLOR_MAP = {
    "btc": "var(--accent-gold)", "global-equity": "var(--accent-blue)",
    "sp500": "var(--accent-blue)", "gold": "var(--accent-gold)",
    "silver": "#c0c0c0", "eurusd": "var(--accent-cyan)",
    "oil": "var(--text-tertiary)", "us10y": "var(--accent-purple)",
}

# Agent instances
sector_agent = SectorAgent()
region_agent = RegionAgent()


class DataService:
    def __init__(self):
        self.prices: dict = {}
        self.news: list = []
        self.assets: list = []
        self.sectors: list = []
        self.regions: list = []
        self.portfolio: dict = {}
        self.market_state: dict = {}
        self.last_refresh: Optional[str] = None

    async def refresh_all(self, force: bool = False):
        """Tiered refresh: only runs expensive analysis when due."""
        if force:
            scheduler.force_all()

        logger.info("="*50)
        logger.info("📊 Starting tiered data refresh...")

        # 1. Fetch real market prices (assets)
        logger.info("📈 Fetching market prices...")
        self.prices = fetch_all_prices()

        # 2. Fetch news
        logger.info("📰 Fetching news...")
        self.news = fetch_all_news()

        # 2b. Run news sentinel (AI impact scoring) - Tier 1 (cheap)
        logger.info("🔍 Running news sentinel...")
        try:
            new_alerts = await sentinel.scan_news(self.news)
            if new_alerts:
                logger.info(f"🚨 Sentinel: {len(new_alerts)} alerts triggered!")
                # Critical alerts trigger Tier 2 re-analysis
                critical = [a for a in new_alerts if a.get("impact_score", 0) >= 7]
                if critical:
                    scheduler.force_refresh("full_analysis")
                    logger.info(f"⚡ {len(critical)} critical alerts → forced full analysis!")
        except Exception as e:
            logger.warning(f"Sentinel error: {e}")
        scheduler.mark_refreshed("news_sentiment")

        # 3. Run AI analysis on each asset - Tier 2 (medium cost)
        if scheduler.should_refresh("full_analysis"):
            logger.info("🧠 Running AI analysis (Tier 2)...")
            assets_analysis = {}
            self.assets = []

            for asset_id, info in ASSET_TICKERS.items():
                price_data = self.prices.get(asset_id, {})
                analysis = await analyze_asset(asset_id, price_data, self.news, info["category"])
                providers = analysis.get("providersUsed", ["rule_based"])
                logger.info(f"  🤖 {info['name']}: {analysis['finalScore']:+.1f} (via {', '.join(providers)})")

                asset_obj = {
                    "id": asset_id, "name": info["name"], "category": info["category"],
                    "icon": ICON_MAP.get(asset_id, "Circle"),
                    "color": COLOR_MAP.get(asset_id, "var(--text-secondary)"),
                    "price": price_data.get("price", 0),
                    "prevPrice": price_data.get("prev_price", 0),
                    "changePct": price_data.get("change_pct", 0),
                    "currency": price_data.get("currency", "$"),
                    "isFallback": price_data.get("is_fallback", False),
                    **analysis,
                }
                assets_analysis[asset_id] = {**analysis, "name": info["name"]}
                self.assets.append(asset_obj)

                # Store analysis in persistent database
                try:
                    store.store_analysis(asset_id, analysis, price_data, info["name"], info["category"])
                except Exception as e:
                    logger.warning(f"Failed to store analysis for {asset_id}: {e}")

            self.assets.sort(key=lambda x: abs(x["finalScore"]), reverse=True)

            # 4. Sector analysis
            logger.info("🏭 Running sector analysis...")
            await self._refresh_sectors()

            # 5. Region analysis
            logger.info("🌍 Running region analysis...")
            await self._refresh_regions()

            # 6. Generate portfolio
            logger.info("💼 Generating portfolio...")
            self.portfolio = generate_portfolio(assets_analysis)

            scheduler.mark_refreshed("full_analysis")

        else:
            logger.info("⏭️ Skipping full analysis (not due yet)")
            # Update prices on existing assets
            for asset in self.assets:
                price_data = self.prices.get(asset["id"], {})
                asset["price"] = price_data.get("price", asset["price"])
                asset["changePct"] = price_data.get("change_pct", asset["changePct"])

        # 6b. Backfill prices and evaluate predictions (runs EVERY cycle)
        if scheduler.should_refresh("evaluation"):
            logger.info("📊 Running evaluation cycle...")
            try:
                eval_results = evaluator.evaluate_all(self.prices)
                if eval_results["evaluated"] > 0:
                    logger.info(f"  ✅ Evaluated {eval_results['evaluated']} predictions")
                if eval_results["backfilled"] > 0:
                    logger.info(f"  📈 Backfilled {eval_results['backfilled']} price snapshots")
                if eval_results["agents_updated"] > 0:
                    logger.info(f"  🧠 Updated {eval_results['agents_updated']} agent accuracy stats")
            except Exception as e:
                logger.warning(f"Evaluation error: {e}")
            scheduler.mark_refreshed("evaluation")

        # 7. Generate overall market state
        avg_score = sum(a["finalScore"] for a in self.assets) / len(self.assets) if self.assets else 0
        avg_score = round(avg_score, 1)

        top_positive = [a for a in self.assets if a["finalScore"] >= 3]
        top_negative = [a for a in self.assets if a["finalScore"] <= -3]
        summary_parts = []
        if top_positive:
            names = ", ".join(a["name"] for a in top_positive[:3])
            summary_parts.append(f"Starkaste köpsignaler: {names}.")
        if top_negative:
            names = ", ".join(a["name"] for a in top_negative[:3])
            summary_parts.append(f"Starkaste säljsignaler: {names}.")

        top_sectors = [s for s in self.sectors if s["score"] >= 3][:3]
        if top_sectors:
            names = ", ".join(s["name"] for s in top_sectors)
            summary_parts.append(f"Starkaste sektorer: {names}.")

        top_regions = [r for r in self.regions if r["score"] >= 3][:3]
        if top_regions:
            names = ", ".join(r["name"] for r in top_regions)
            summary_parts.append(f"Starkaste regioner: {names}.")

        pos_news = sum(1 for n in self.news if n["sentiment"] == "positive")
        neg_news = sum(1 for n in self.news if n["sentiment"] == "negative")
        if pos_news > neg_news:
            summary_parts.append(f"Nyhetsbild: Positiv ({pos_news} pos vs {neg_news} neg).")
        elif neg_news > pos_news:
            summary_parts.append(f"Nyhetsbild: Negativ ({neg_news} neg vs {pos_news} pos).")
        else:
            summary_parts.append("Nyhetsbild: Balanserad.")

        sched_status = scheduler.get_status()
        next_analysis = sched_status.get("full_analysis", {}).get("seconds_until_next", 0)

        self.market_state = {
            "overallScore": avg_score,
            "overallSummary": " ".join(summary_parts),
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "assetCount": len(self.assets),
            "sectorCount": len(self.sectors),
            "regionCount": len(self.regions),
            "newsCount": len(self.news),
            "nextAnalysisIn": next_analysis,
            "schedulerStatus": sched_status,
        }

        self.last_refresh = datetime.now(timezone.utc).isoformat()
        logger.info(f"✅ Refresh complete. {len(self.assets)} assets, {len(self.sectors)} sectors, {len(self.regions)} regions, {len(self.news)} news.")
        logger.info(f"📊 Overall market score: {avg_score:+.1f}")
        logger.info("="*50)

    async def _refresh_sectors(self):
        """Fetch sector ETF prices and run sector analysis."""
        self.sectors = []
        sector_tickers = get_sector_tickers()
        ticker_list = list(sector_tickers.values())

        # Batch download sector ETF prices
        sector_prices = {}
        try:
            data = yf.download(ticker_list, period="5d", group_by="ticker", progress=False)
            for sector_id, ticker in sector_tickers.items():
                try:
                    ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else None
                    if ticker_data is not None and not ticker_data.empty:
                        closes = ticker_data["Close"].dropna()
                        if len(closes) >= 2:
                            cur = float(closes.iloc[-1])
                            prev = float(closes.iloc[-2])
                            chg = ((cur - prev) / prev) * 100
                            sector_prices[sector_id] = {
                                "price": cur, "prev_price": prev,
                                "change_pct": round(chg, 2), "currency": "$",
                            }
                        elif len(closes) == 1:
                            sector_prices[sector_id] = {
                                "price": float(closes.iloc[-1]), "prev_price": float(closes.iloc[-1]),
                                "change_pct": 0.0, "currency": "$",
                            }
                except Exception as e:
                    logger.warning(f"  ❌ Sector {sector_id}: {e}")
        except Exception as e:
            logger.error(f"Sector batch download failed: {e}")

        # Run sector agent on each sector
        for sector_id, info in SECTORS.items():
            price_data = sector_prices.get(sector_id, {"price": 0, "change_pct": 0, "currency": "$"})
            drivers_str = ", ".join(info.get("macro_drivers", []))

            analysis = await sector_agent.analyze(
                sector_id, info["name"], drivers_str, price_data, self.news
            )

            sector_obj = {
                "id": sector_id,
                "name": info["name"],
                "emoji": info["emoji"],
                "description": info["description"],
                "examples": info["examples"],
                "color": info["color"],
                "ticker": info["ticker"],
                "price": price_data.get("price", 0),
                "changePct": price_data.get("change_pct", 0),
                "score": analysis.get("score", 0),
                "confidence": analysis.get("confidence", 0.5),
                "reasoning": analysis.get("reasoning", ""),
                "keyDrivers": analysis.get("key_drivers", []),
                "rotationSignal": analysis.get("rotation_signal", "Neutralvikt"),
                "macroDrivers": info.get("macro_drivers", []),
                "providerUsed": analysis.get("provider_used", "rule_based"),
            }
            self.sectors.append(sector_obj)
            logger.info(f"  🏭 {info['emoji']} {info['name']}: {analysis['score']:+d} ({analysis.get('rotation_signal', 'N/A')})")

        # Sort by score descending
        self.sectors.sort(key=lambda x: x["score"], reverse=True)

    async def _refresh_regions(self):
        """Fetch region ETF prices and run region analysis."""
        self.regions = []
        region_tickers = get_region_tickers()
        ticker_list = list(region_tickers.values())

        # Batch download region ETF prices
        region_prices = {}
        try:
            data = yf.download(ticker_list, period="5d", group_by="ticker", progress=False)
            for region_id, ticker in region_tickers.items():
                try:
                    ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else None
                    if ticker_data is not None and not ticker_data.empty:
                        closes = ticker_data["Close"].dropna()
                        if len(closes) >= 2:
                            cur = float(closes.iloc[-1])
                            prev = float(closes.iloc[-2])
                            chg = ((cur - prev) / prev) * 100
                            region_prices[region_id] = {
                                "price": cur, "prev_price": prev,
                                "change_pct": round(chg, 2), "currency": "$",
                            }
                        elif len(closes) == 1:
                            region_prices[region_id] = {
                                "price": float(closes.iloc[-1]), "prev_price": float(closes.iloc[-1]),
                                "change_pct": 0.0, "currency": "$",
                            }
                except Exception as e:
                    logger.warning(f"  ❌ Region {region_id}: {e}")
        except Exception as e:
            logger.error(f"Region batch download failed: {e}")

        # Run region agent on each region
        for region_id, info in REGIONS.items():
            price_data = region_prices.get(region_id, {"price": 0, "change_pct": 0, "currency": "$"})
            drivers_str = ", ".join(info.get("macro_drivers", []))

            analysis = await region_agent.analyze(
                region_id, info["name"], drivers_str, price_data, self.news
            )

            region_obj = {
                "id": region_id,
                "name": info["name"],
                "flag": info["flag"],
                "description": info["description"],
                "indexName": info["index_name"],
                "color": info["color"],
                "ticker": info["ticker"],
                "price": price_data.get("price", 0),
                "changePct": price_data.get("change_pct", 0),
                "score": analysis.get("score", 0),
                "confidence": analysis.get("confidence", 0.5),
                "reasoning": analysis.get("reasoning", ""),
                "keyDrivers": analysis.get("key_drivers", []),
                "allocationSignal": analysis.get("allocation_signal", "Neutralvikt"),
                "macroDrivers": info.get("macro_drivers", []),
                "providerUsed": analysis.get("provider_used", "rule_based"),
            }
            self.regions.append(region_obj)
            logger.info(f"  🌍 {info['flag']} {info['name']}: {analysis['score']:+d} ({analysis.get('allocation_signal', 'N/A')})")

        # Sort by score descending
        self.regions.sort(key=lambda x: x["score"], reverse=True)

    def get_assets(self) -> list:
        return self.assets

    def get_asset(self, asset_id: str) -> Optional[dict]:
        return next((a for a in self.assets if a["id"] == asset_id), None)

    def get_news(self) -> list:
        return self.news

    def get_portfolio(self) -> dict:
        return self.portfolio

    def get_market_state(self) -> dict:
        return self.market_state

    def get_sectors(self) -> list:
        return self.sectors

    def get_regions(self) -> list:
        return self.regions
