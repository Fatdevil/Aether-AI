"""
Data Service - Orchestrates market data, news, and AI analysis.
Caches results and provides APIs for the FastAPI endpoints.
"""

import logging
import os
import yfinance as yf
import pandas as pd
import numpy as np
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
from asset_scenario_generator import level1_generator

logger = logging.getLogger("aether.data")

# ── Scenario cost controls (override via Railway env vars to upgrade quality) ──
# SCENARIO_LLM_SCORE_THRESHOLD: min |score| to use LLM for narrative (default 3.0)
#   Lower = more LLM calls, higher quality.  Raise to 0 when ready to go full-LLM.
# SCENARIO_CACHE_TTL_HOURS: how long to cache per asset before regenerating (default 24h)
#   Lower = fresher narratives but more API calls.
SCENARIO_LLM_SCORE_THRESHOLD = float(os.getenv("SCENARIO_LLM_SCORE_THRESHOLD", "0"))
SCENARIO_CACHE_TTL_SECONDS   = float(os.getenv("SCENARIO_CACHE_TTL_HOURS", "24")) * 3600

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
        # Historical returns cache
        self._returns_cache: Optional[pd.DataFrame] = None
        self._returns_cache_time: Optional[datetime] = None
        self._returns_cache_ttl = 21600  # 6 hours
        # Scenario cache: {asset_id: {"result": ScenarioResult, "score": float, "ts": datetime}}
        self._scenario_cache: dict = {}

    def get_historical_returns(self, period: str = "1y") -> pd.DataFrame:
        """
        Fetch historical daily returns for all tracked assets.
        Returns DataFrame with date index and asset columns.
        Cached for 6 hours.
        """
        now = datetime.now()
        if (self._returns_cache is not None and
            self._returns_cache_time is not None and
            (now - self._returns_cache_time).total_seconds() < self._returns_cache_ttl):
            return self._returns_cache

        logger.info("📊 Fetching historical returns for quantitative modules...")
        tickers = {aid: info["ticker"] for aid, info in ASSET_TICKERS.items()}
        ticker_list = list(tickers.values())

        try:
            data = yf.download(ticker_list, period=period, progress=False)
            closes = data["Close"] if "Close" in data.columns.get_level_values(0) else data

            # Rename columns from tickers to asset IDs
            ticker_to_id = {info["ticker"]: aid for aid, info in ASSET_TICKERS.items()}
            rename_map = {}
            for col in closes.columns:
                col_str = str(col)
                if col_str in ticker_to_id:
                    rename_map[col] = ticker_to_id[col_str]

            closes = closes.rename(columns=rename_map)
            returns = closes.pct_change().dropna()

            # Filter out columns with too many NaN
            valid_cols = [c for c in returns.columns if returns[c].notna().sum() > 100]
            returns = returns[valid_cols]

            self._returns_cache = returns
            self._returns_cache_time = now
            logger.info(f"  ✅ Historical returns: {len(returns)} days × {len(returns.columns)} assets")
            return returns

        except Exception as e:
            logger.error(f"  ❌ Failed to fetch historical returns: {e}")
            if self._returns_cache is not None:
                return self._returns_cache
            return pd.DataFrame()

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

        # 2a/2b: AI News Analysis (Tier 1, runs on a schedule to save API cost)
        if scheduler.should_refresh("news_sentiment"):
            # 2a. News Scout — ranks top stories + stamps impact_sv (Gemini Flash, ~$0.002)
            logger.info("🔍 Running news scout...")
            try:
                from news_service import get_news_scout
                scout_result = await get_news_scout(self.news)
                self.news_scout_digest = scout_result.get("digest", "")
                if self.news_scout_digest:
                    logger.info(f"  📋 Scout digest ready ({len(self.news_scout_digest)} chars)")
            except Exception as e:
                logger.warning(f"Scout error: {e}")
                self.news_scout_digest = ""

            # 2b. Run news sentinel (AI impact scoring) - Tier 1 (cheap)
            logger.info("🚨 Running news sentinel...")
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
        else:
            logger.info("⏭️ Skipping AI news analysis (not due yet)")


        # 3. Run AI analysis on each asset - Tier 2 (medium cost)
        # Read VIX once for scenario generation
        vix_now = self.prices.get("sp500", {}).get("indicators", {}).get("vix", 20.0) or 20.0
        try:
            from regime_detector import regime_detector as _rd
            _regime_now = _rd.detect_regime().get("regime", "neutral")
        except Exception:
            _regime_now = "neutral"
        # Top news headlines for scenario context
        _news_headlines = [
            n.get("title", "") for n in (self.news or []) if n.get("sentiment") in ("negative", "positive")
        ][:8]

        if scheduler.should_refresh("full_analysis"):
            logger.info("🧠 Running AI analysis (Tier 2)...")
            assets_analysis = {}
            self.assets = []

            for asset_id, info in ASSET_TICKERS.items():
                price_data = self.prices.get(asset_id, {})
                analysis = await analyze_asset(
                    asset_id, price_data, self.news, info["category"],
                    news_scout_digest=getattr(self, "news_scout_digest", ""),
                )

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

                # ── Scenario generation (Level 1, cost-optimised) ───────────────
                try:
                    _final_score = analysis.get("finalScore", 0)
                    _cached = self._scenario_cache.get(asset_id)
                    _score_changed = _cached and abs(_cached["score"] - _final_score) >= 2.0
                    _cache_expired = not _cached or (
                        (datetime.now() - _cached["ts"]).total_seconds() >= SCENARIO_CACHE_TTL_SECONDS
                    )
                    _strong_signal = abs(_final_score) >= SCENARIO_LLM_SCORE_THRESHOLD

                    if _cached and not _cache_expired and not _score_changed:
                        # ✅ Serve from cache
                        asset_obj.update(_cached["result"].to_frontend(info["name"]))
                        logger.info(f"  📦 Scenario cached for {info['name']} (score unchanged)")
                    else:
                        # Generate fresh
                        agent_scores_for_scenario = {
                            k: v.get("score", 0)
                            for k, v in analysis.get("agentDetails", {}).items()
                            if isinstance(v, dict)
                        }
                        scenario_result = await level1_generator.generate(
                            asset_id=asset_id,
                            asset_name=info["name"],
                            current_price=price_data.get("price", 0),
                            final_score=_final_score,
                            agent_scores=agent_scores_for_scenario,
                            regime=_regime_now,
                            vix=vix_now,
                            news_headlines=_news_headlines,
                            supervisor_text=analysis.get("supervisorText", "") if _strong_signal else "",
                            llm_narratives=_strong_signal,   # Skip LLM for neutral assets
                        )
                        asset_obj.update(scenario_result.to_frontend(info["name"]))
                        # Save to cache
                        self._scenario_cache[asset_id] = {
                            "result": scenario_result,
                            "score": _final_score,
                            "ts": datetime.now(),
                        }
                        tag = "📊 LLM" if _strong_signal else "📊 rule-based"
                        logger.info(f"  {tag} Scenario for {info['name']} (score {_final_score:+.1f})")
                except Exception as _se:
                    logger.warning(f"  ⚠️ Scenario gen skipped for {asset_id}: {_se}")
                # ────────────────────────────────────────────────────────────

                assets_analysis[asset_id] = {**analysis, "name": info["name"]}
                self.assets.append(asset_obj)

                # Store analysis in persistent database
                try:
                    store.store_analysis(asset_id, analysis, price_data, info["name"], info["category"])
                except Exception as e:
                    logger.warning(f"Failed to store analysis for {asset_id}: {e}")

                # FIX 3A: Log prediction + apply confidence calibration
                try:
                    from predictive.confidence_calibrator import ConfidenceCalibrator
                    calibrator = ConfidenceCalibrator()
                    # Log this prediction for future calibration
                    raw_conf = analysis.get("supervisorConfidence", 0.5)
                    pred_id = f"{asset_id}_{datetime.now().strftime('%Y%m%d_%H%M')}"
                    calibrator.log_prediction(pred_id, raw_conf, "supervisor", asset=asset_id)
                    # Apply calibration to displayed confidence
                    calibrated_conf = calibrator.adjust_probability(raw_conf)
                    if abs(calibrated_conf - raw_conf) > 0.02:
                        asset_obj["supervisorConfidence"] = round(calibrated_conf, 3)
                        analysis["supervisorConfidence"] = round(calibrated_conf, 3)
                except Exception:
                    pass

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

                # FIX 1C: Update MetaStrategy weights after evaluation
                # This closes the self-improvement loop — method weights adjust based on real performance
                try:
                    from predictive.meta_strategy import MetaStrategySelector
                    meta = MetaStrategySelector()
                    meta.update_weights()
                    logger.info("  🔄 MetaStrategy weights updated from evaluation results")
                except Exception as me:
                    logger.warning(f"  MetaStrategy update skipped: {me}")

            except Exception as e:
                logger.warning(f"Evaluation error: {e}")
            scheduler.mark_refreshed("evaluation")

        # 7. Generate overall market state with human-friendly V2 summary
        avg_score = sum(a["finalScore"] for a in self.assets) / len(self.assets) if self.assets else 0
        avg_score = round(avg_score, 1)

        # Determine mood from score
        if avg_score >= 4:
            mood = "RISK ON"
        elif avg_score >= 1:
            mood = "SELEKTIV POSITIV"
        elif avg_score >= -1:
            mood = "NEUTRAL"
        elif avg_score >= -4:
            mood = "SELEKTIV DEFENSIV"
        else:
            mood = "RISK OFF"

        # Build full predict context
        predict_context_text = ""
        try:
            from supervisor_context import SupervisorContextBuilder
            ctx_builder = SupervisorContextBuilder(analysis_store=store)
            # Build global context (not per-asset)
            full_ctx = {
                "regime": ctx_builder._get_regime_context(),
                "active_events": ctx_builder._get_event_context(),
                "narratives": ctx_builder._get_narrative_context(),
                "causal_chains": ctx_builder._get_causal_chains_context(),
                "event_trees": ctx_builder._get_event_trees_context(),
                "calendar": ctx_builder._get_calendar_context(),
                "lead_lag": ctx_builder._get_lead_lag_context(),
                "meta_strategy": ctx_builder._get_meta_strategy_context(),
                "previous_summary": ctx_builder._get_latest_supervisor_summary(),
                "accuracy": ctx_builder._get_accuracy_context(),
            }
            # Format into prompt text
            predict_context_text = ctx_builder._format_for_prompt(
                "global", "Hela marknaden", "overview",
                {}, {}, full_ctx
            )
        except Exception as e:
            logger.warning(f"Predict context build failed: {e}")

        # Build short human-friendly summary (rule-based, free)
        summary_text = self._build_human_summary(avg_score, mood)

        # Build expanded A4 summary (LLM-powered, ~$0.001 per call)
        expanded_text = ""
        try:
            expanded_text = await self._generate_expanded_summary(
                avg_score, mood, summary_text, predict_context_text
            )
        except Exception as e:
            logger.warning(f"Expanded summary generation failed: {e}")

        # Store supervisor summary for memory/continuity
        try:
            regime_label = ""
            try:
                from regime_detector import regime_detector
                regime = regime_detector.detect_regime()
                regime_label = regime.get("regime", "")
            except Exception:
                pass

            store.store_supervisor_summary(
                overall_score=avg_score,
                regime=regime_label,
                mood=mood,
                summary_text=expanded_text or summary_text,
                accuracy_7d=0.0,
                events_count=0,
                assets_count=len(self.assets),
            )
        except Exception as e:
            logger.warning(f"Failed to store supervisor summary: {e}")

        sched_status = scheduler.get_status()
        next_analysis = sched_status.get("full_analysis", {}).get("seconds_until_next", 0)

        self.market_state = {
            "overallScore": avg_score,
            "overallSummary": summary_text,
            "expandedSummary": expanded_text,
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


    async def _generate_expanded_summary(
        self, avg_score: float, mood: str, short_summary: str, predict_context: str
    ) -> str:
        """Generate an A4-length expanded summary using LLM.

        Uses GPT-4o-mini or equivalent. Cost: ~$0.001 per call.
        Returns empty string if no LLM provider is available.
        """
        if not predict_context and not self.assets:
            return ""

        # Build asset overview for the prompt
        asset_lines = []
        for a in sorted(self.assets, key=lambda x: x["finalScore"], reverse=True):
            score = a["finalScore"]
            emoji = "🟢" if score >= 3 else "🔴" if score <= -3 else "⚪"
            asset_lines.append(f"  {emoji} {a['name']}: {score:+.1f} (pris: {a.get('price', 0):.2f}, ändring: {a.get('changePct', 0):+.1f}%)")

        sector_lines = []
        for s in sorted(self.sectors, key=lambda x: x["score"], reverse=True)[:5]:
            sector_lines.append(f"  {s.get('emoji', '')} {s['name']}: {s['score']:+d}")

        region_lines = []
        for r in sorted(self.regions, key=lambda x: x["score"], reverse=True)[:5]:
            region_lines.append(f"  {r.get('flag', '')} {r['name']}: {r['score']:+d}")

        # News summary
        pos = sum(1 for n in self.news if n.get("sentiment") == "positive")
        neg = sum(1 for n in self.news if n.get("sentiment") == "negative")

        prompt = f"""Du är en av Sveriges ledande makroekonomiska analytiker. Skriv en professionell marknadsrapport på svenska riktad till en kompetent privatinvesterare.

DATA UNDERLAG:
Marknadsläge: {mood} (genomsnittsscore: {avg_score:+.1f})
Kort sammanfattning: {short_summary}

TILLGÅNGAR:
{chr(10).join(asset_lines)}

SEKTORER (topp 5):
{chr(10).join(sector_lines) if sector_lines else "  (ej analyserade)"}

REGIONER (topp 5):
{chr(10).join(region_lines) if region_lines else "  (ej analyserade)"}

NYHETSFLÖDE: {pos} positiva, {neg} negativa av {len(self.news)} totalt

{'='*50}
PREDIKTIV INTELLIGENS:
{predict_context if predict_context else "(ingen prediktiv data tillgänglig)"}
{'='*50}

INSTRUKTIONER:
1. Ton: Professionell och analytisk — som en rapport från en senior ekonom till en välutbildad privatinvesterare.
   INTE vänlig konversationston. INTE "Hej" eller "kära vän" eller liknande.
   Börja direkt med analysen, utan hälsningsfraser.
2. Längd: 400-600 ord. Koncist och utan utfyllnad.
3. Svenska: Klar och precis. Finanstermer är OK men förklara om nödvändigt.
4. Obligatoriska sektioner (använd ### som rubrik):

### Situationsanalys
Vad karaktäriserar marknaden just nu? Vad är det övergripande läget?
Vara konkret — referera till faktiska scores, priser och rörelser.

### Makroekonomiska drivkrafter
De strukturella krafterna som styr marknaden — räntor, inflation, penningpolitik, geopolitik.
Kopla till specifika datapunkter.

### Tillgångsöversikt & Signaler
Vilka tillgångar visar de starkaste signalerna, positiva som negativa?
Referera till kausala kedjor och scenarioanalyser om tillgängliga.

### Riskbild
Vad kan bryta nuvarande trend? Vilka faktorer innebär oväntad nedsida?
Nämn kommande makroevents om relevanta.

### Positionering & Rekommendationer
Klar bottom-line: vad bör en investerare göra baserat på nuläget?
Vara specifik — tillgångsslag, riktning, och motivering.

5. SJÄLVUTVÄRDERING (om föregående analys finns): Inled sektionen Situationsanalys med en mening om
   huruvida föregående analys var korrekt. Ex: "Föregående bedömning om X visade sig stämma/avvika då Y."
6. Om kausala kedjor finns — lyft den viktigaste i klartext under Makroekonomiska drivkrafter.
7. Om lead-lag-signaler finns — inkludera dem under Positionering.

FORMAT:
- Ingen inledande hälsning
- Inga avslutningshälsningar
- Enbart rapporten, inga metadata eller JSON
- Varje sektion ska tillföra konkret värde — ingen utfyllnad"""

        try:
            from llm_provider import call_llm_tiered
            result_text, provider = await call_llm_tiered(
                tier=2,
                system_prompt="Du är en senior makroekonomisk analytiker. Skriv precisa, professionella marknadsrapporter på svenska.",
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=2000,
                plain_text=True,
            )
            if result_text:
                logger.info(f"📝 Expanded summary generated: {len(result_text)} chars via {provider}")
                return result_text
        except Exception as e:
            logger.warning(f"LLM expanded summary failed: {e}")

        return ""

    def _build_human_summary(self, avg_score: float, mood: str) -> str:
        """Build a human-friendly summary text for the dashboard.

        Writes like an experienced advisor explaining the market to a friend.
        Integrates regime, news, previous summaries, and key signals.
        """
        parts = []

        # --- Opening: what's happening right now ---
        top_positive = [a for a in self.assets if a["finalScore"] >= 3]
        top_negative = [a for a in self.assets if a["finalScore"] <= -3]
        neutral_count = len(self.assets) - len(top_positive) - len(top_negative)

        if avg_score >= 4:
            parts.append("Marknaderna visar tydliga styrketecken just nu.")
        elif avg_score >= 1:
            parts.append("Marknaderna är övervägande positiva med selektiva möjligheter.")
        elif avg_score >= -1:
            parts.append("Marknaderna rör sig sidledes — varken tydliga köp- eller säljsignaler dominerar.")
        elif avg_score >= -4:
            parts.append("Marknaderna visar svaghetstecken och våra modeller flaggar för försiktighet.")
        else:
            parts.append("Marknaderna är under press — starka säljsignaler dominerar och vi rekommenderar defensiv positionering.")

        # --- Regime context ---
        try:
            from regime_detector import regime_detector
            regime = regime_detector.detect_regime()
            regime_label = regime.get("label", "")
            regime_conf = regime.get("confidence", 0)
            vix_level = regime.get("signals", {}).get("vix", {}).get("level")

            if regime_label and regime_conf > 0.3:
                regime_text = f"Marknadsregimen klassas som {regime_label}"
                if vix_level:
                    regime_text += f" med VIX på {vix_level}"
                regime_text += "."
                parts.append(regime_text)
        except Exception:
            pass

        # --- Key signals: what to buy/sell ---
        if top_positive:
            names = " och ".join(a["name"] for a in top_positive[:2])
            parts.append(f"Starkast just nu: {names} med tydliga köpsignaler från våra AI-modeller.")
        if top_negative:
            names = " och ".join(a["name"] for a in top_negative[:2])
            parts.append(f"Svagast: {names} där modellerna ser fallande potential.")

        # --- News sentiment ---
        pos_news = sum(1 for n in self.news if n.get("sentiment") == "positive")
        neg_news = sum(1 for n in self.news if n.get("sentiment") == "negative")
        total_news = len(self.news)
        if total_news > 0:
            if pos_news > neg_news * 1.5:
                parts.append(f"Nyhetsflödet lutar positivt ({pos_news} positiva vs {neg_news} negativa av {total_news} analyserade).")
            elif neg_news > pos_news * 1.5:
                parts.append(f"Nyhetsflödet lutar negativt ({neg_news} negativa vs {pos_news} positiva) — marknaden reagerar.")
            else:
                parts.append(f"Nyhetsflödet är blandat ({total_news} artiklar analyserade).")

        # --- Continuity: reference previous summary ---
        try:
            prev_summaries = store.get_recent_summaries(n=1)
            if prev_summaries:
                prev = prev_summaries[0]
                prev_score = prev.get("overall_score", 0)
                prev_mood = prev.get("mood", "")
                score_diff = avg_score - prev_score

                if abs(score_diff) >= 2:
                    if score_diff > 0:
                        parts.append(f"Sedan senaste analysen har marknadsläget förbättrats — från {prev_mood} till {mood}.")
                    else:
                        parts.append(f"Sedan senaste analysen har marknadsläget försämrats — från {prev_mood} till {mood}.")
                elif prev_mood and prev_mood != mood:
                    parts.append(f"Marknadshumöret har skiftat från {prev_mood} till {mood}.")
        except Exception:
            pass

        # --- Sectors/regions highlight ---
        top_sectors = [s for s in self.sectors if s["score"] >= 3][:2]
        if top_sectors:
            names = " och ".join(s["name"] for s in top_sectors)
            parts.append(f"Sektorsmässigt sticker {names} ut positivt.")

        return " ".join(parts)

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

            # Store sector analysis in persistent database
            try:
                store.store_sector_analysis(sector_id, {
                    "name": info["name"],
                    "category": "sector",
                    "price": price_data.get("price", 0),
                    "change_pct": price_data.get("change_pct", 0),
                    "score": analysis.get("score", 0),
                    "recommendation": analysis.get("rotation_signal", "Neutralvikt"),
                    "reasoning": analysis.get("reasoning", ""),
                    "confidence": analysis.get("confidence", 0.5),
                    "provider": analysis.get("provider_used", "rule_based"),
                    "analysis_type": "sector",
                })
            except Exception as e:
                logger.warning(f"Failed to store sector analysis for {sector_id}: {e}")

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

            # Store region analysis in persistent database
            try:
                store.store_sector_analysis(region_id, {
                    "name": info["name"],
                    "category": "region",
                    "price": price_data.get("price", 0),
                    "change_pct": price_data.get("change_pct", 0),
                    "score": analysis.get("score", 0),
                    "recommendation": analysis.get("allocation_signal", "Neutralvikt"),
                    "reasoning": analysis.get("reasoning", ""),
                    "confidence": analysis.get("confidence", 0.5),
                    "provider": analysis.get("provider_used", "rule_based"),
                    "analysis_type": "region",
                })
            except Exception as e:
                logger.warning(f"Failed to store region analysis for {region_id}: {e}")

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
