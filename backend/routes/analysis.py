"""
Aether AI — Analysis Routes
Correlations, calendar, enrichment, prediction markets, and secondary regime.
Extracted from main.py for modularity.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Request

import logging

logger = logging.getLogger("aether")

router = APIRouter(tags=["Analysis"])


def setup(data_service, limiter, enrichment_loader, prediction_markets):
    """Register routes that depend on shared state."""

    @router.get("/api/calendar")
    async def get_calendar():
        """Return upcoming and recent economic events."""
        from economic_calendar import calendar
        return calendar.get_summary()

    @router.get("/api/correlations")
    async def get_correlations(period: str = "30d"):
        """Return cross-asset correlation matrix and systemic signal."""
        from correlation_engine import correlation_engine
        if period not in ("7d", "30d", "90d", "180d"):
            period = "30d"
        return correlation_engine.calculate_correlations(period=period)

    @router.get("/api/correlations/insights")
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
                text = response.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                insights = _json.loads(text)
                if isinstance(insights, list):
                    return {"insights": insights[:5], "source": "ai", "period": period}
        except Exception as e:
            logger.warning(f"AI correlation insights failed: {e}")

        insights = _generate_rule_based_insights(matrix, systemic, notable, period, name_map)
        return {"insights": insights, "source": "rule_based", "period": period}

    # ---- Enrichment endpoints ----

    @router.get("/api/enrichment-status")
    @limiter.limit("10/minute")
    async def get_enrichment_status(request: Request):
        """Visa alla enrichment-features, direktsignaler och sekundär regim."""
        from regime_classifier import detect_secondary_regime
        try:
            features = enrichment_loader.get_features()
            signals = enrichment_loader.get_direct_signals()
            secondary = detect_secondary_regime(features)
            return {
                "status": "ok",
                "features": features,
                "signals": signals,
                "secondary_regime": secondary,
                "n_features": len(features),
                "n_signals": len(signals),
                "cache_status": "cached" if enrichment_loader.cache else "fresh_fetch",
            }
        except Exception as e:
            logger.error(f"Enrichment status failed: {e}")
            return {"status": "error", "error": str(e)}

    @router.get("/api/secondary-regime")
    @limiter.limit("10/minute")
    async def get_secondary_regime(request: Request):
        """Visa sekundär regim (konjunktur × inflation)."""
        from regime_classifier import detect_secondary_regime
        try:
            features = enrichment_loader.get_features()
            result = detect_secondary_regime(features)
            return {"status": "ok", **result}
        except Exception as e:
            logger.error(f"Secondary regime failed: {e}")
            return {"status": "error", "error": str(e)}

    # ---- Prediction Markets ----

    @router.get("/api/prediction-markets")
    @limiter.limit("10/minute")
    async def get_prediction_markets_dashboard(request: Request):
        """Hämta senaste prediction market-odds, rörelser och signaler."""
        try:
            return {"status": "ok", **prediction_markets.get_dashboard()}
        except Exception as e:
            logger.error(f"PM dashboard failed: {e}")
            return {"status": "error", "error": str(e)}

    @router.get("/api/prediction-markets/movements")
    @limiter.limit("10/minute")
    async def get_pm_movements(request: Request, hours: int = 48):
        """Hämta oddsrörelser senaste N timmar."""
        cutoff = datetime.now() - timedelta(hours=hours)
        # S4 FIX: Safe timestamp parsing
        recent = []
        for m in prediction_markets.movements:
            try:
                if datetime.fromisoformat(m.timestamp) > cutoff:
                    recent.append(m.__dict__)
            except (ValueError, AttributeError):
                continue
        return {"movements": recent, "count": len(recent), "period_hours": hours}

    @router.get("/api/prediction-markets/top")
    @limiter.limit("5/minute")
    async def get_top_pm_markets(request: Request):
        """Hämta topp prediction markets sorterade efter volym."""
        try:
            top = prediction_markets.get_top_markets(limit=10)
            return {"markets": top, "count": len(top)}
        except Exception as e:
            logger.error(f"PM top failed: {e}")
            return {"markets": [], "count": 0, "error": str(e)}

    @router.post("/api/prediction-markets/refresh")
    @limiter.limit("2/minute")
    async def refresh_pm(request: Request):
        """Manuell refresh av prediction markets data."""
        try:
            await prediction_markets.refresh()
            return {"status": "ok", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"PM refresh failed: {e}")
            return {"status": "error", "error": str(e)}


def _generate_rule_based_insights(matrix, systemic, notable, period, name_map):
    """Generate insights without LLM."""
    insights = []

    high_corr = [p for p in notable if p["correlation"] > 0.7]
    if high_corr:
        pairs_text = ", ".join(f"{name_map.get(p['asset_a'],p['asset_a'])}↔{name_map.get(p['asset_b'],p['asset_b'])} ({p['correlation']:+.2f})" for p in high_corr[:3])
        insights.append({
            "icon": "⚠️",
            "title": "Koncentrationsrisk",
            "text": f"Dessa tillgångar rör sig nästan identiskt ({period}): {pairs_text}. Om du äger flera av dem ger de inte diversifiering – överväg att minska i en."
        })

    neg_corr = [p for p in notable if p["correlation"] < -0.4]
    if neg_corr:
        best = neg_corr[0]
        insights.append({
            "icon": "🛡️",
            "title": "Hedging-möjlighet",
            "text": f"{name_map.get(best['asset_a'],best['asset_a'])} och {name_map.get(best['asset_b'],best['asset_b'])} har {best['correlation']:+.2f} korrelation. Kombinationen ger effektiv riskspridning – om en faller tenderar den andra att stiga."
        })

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

    if len(insights) < 2:
        insights.append({
            "icon": "📊",
            "title": "Normal korrelationsstruktur",
            "text": f"Inga extrema korrelationsmönster detekterade ({period}). Marknaden beter sig normalt – ingen speciell åtgärd krävs."
        })

    return insights[:5]
