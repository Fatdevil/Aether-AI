"""
Regime Detector - Classifies the current market regime using multiple signals.
Detects risk-on/risk-off, inflation/deflation, and market stress states.
Uses VIX, yield curve, credit correlations, and momentum to classify regimes.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger("aether.regime")

# Cache
_regime_cache: Optional[dict] = None
_cache_time: float = 0
_CACHE_TTL = 600  # 10 minutes


# Regime types and their characteristics
REGIME_PROFILES = {
    "risk-on": {
        "label": "📈 Risk-On",
        "description": "Stark riskaptit. Aktier och krypto stiger, säkra hamnar faller.",
        "agent_guidance": {
            "macro": "Fokusera på tillväxtdata och positiva konjunktursignaler.",
            "micro": "Likviditet och flöden är positiva. Momentum gynnas.",
            "sentiment": "Eufori kan vara konträrindikator om extrem.",
            "tech": "Trendföljande strategier fungerar bäst. Momentum starkare än mean-reversion.",
        },
        "weight_adjustments": {"macro": 1.0, "micro": 1.1, "sentiment": 0.8, "tech": 1.2},
    },
    "risk-off": {
        "label": "📉 Risk-Off",
        "description": "Defensivt läge. Guld och obligationer stiger, aktier faller.",
        "agent_guidance": {
            "macro": "Recessionsrisker och centralbanksrespons är centralt.",
            "micro": "Utflöden dominerar. Likviditetsproblem möjligt.",
            "sentiment": "Rädsla driver marknaden. Konträrt tänkande kan vara värdefullt.",
            "tech": "Stödnivåer viktigare. Teknisk analys mindre pålitlig i panik.",
        },
        "weight_adjustments": {"macro": 1.3, "micro": 0.9, "sentiment": 1.2, "tech": 0.7},
    },
    "inflation": {
        "label": "🔥 Inflation",
        "description": "Stigande priser. Råvaror och realtillgångar gynnas.",
        "agent_guidance": {
            "macro": "Inflationsdata och centralbanksretorik är avgörande.",
            "micro": "Prissättningskraft och marginaler under press.",
            "sentiment": "Inflationsoro kan skapa överreaktioner.",
            "tech": "Trendföljande i råvaror, mean-reversion i räntor.",
        },
        "weight_adjustments": {"macro": 1.4, "micro": 1.0, "sentiment": 0.9, "tech": 0.8},
    },
    "deflation": {
        "label": "❄️ Deflation/Stagnation",
        "description": "Fallande priser, svag tillväxt. Obligationer gynnas, råvaror faller.",
        "agent_guidance": {
            "macro": "BNP-data och arbetsmarknad centralt. Centralbanker kan stimulera.",
            "micro": "Svag efterfrågan. Konsumentförtroende viktigt.",
            "sentiment": "Pessimism men stimulansförväntningar kan ge vändning.",
            "tech": "Sidledstrender vanligare. Range-trading bättre än trendföljning.",
        },
        "weight_adjustments": {"macro": 1.3, "micro": 1.1, "sentiment": 1.0, "tech": 0.7},
    },
    "transition": {
        "label": "🔄 Övergång",
        "description": "Marknaden skiftar regim. Hög osäkerhet, motstridiga signaler.",
        "agent_guidance": {
            "macro": "Var extra uppmärksam på trendbrott i data.",
            "micro": "Flödesdata kan ge tidiga signaler.",
            "sentiment": "Extremt sentiment (åt båda håll) kan signalera regimskifte.",
            "tech": "Breakout-signaler viktigare. Sök bekräftelse från volym.",
        },
        "weight_adjustments": {"macro": 1.1, "micro": 1.1, "sentiment": 1.1, "tech": 0.8},
    },
}


class RegimeDetector:
    """Detects and classifies the current market regime."""

    def detect_regime(self) -> dict:
        """Run full regime detection using multiple signals."""
        global _regime_cache, _cache_time

        now = time.monotonic()
        if now - _cache_time < _CACHE_TTL and _regime_cache:
            return _regime_cache

        signals = {}

        # Signal 1: VIX level
        signals["vix"] = self._check_vix()

        # Signal 2: Yield curve (10Y vs 2Y spread)
        signals["yield_curve"] = self._check_yield_curve()

        # Signal 3: Gold vs Stocks momentum
        signals["gold_vs_stocks"] = self._check_safe_haven_flow()

        # Signal 4: Broad market momentum
        signals["market_momentum"] = self._check_market_momentum()

        # Signal 5: USD strength
        signals["usd"] = self._check_usd()

        # Classify regime from signals
        regime = self._classify_regime(signals)

        result = {
            "regime": regime["name"],
            "label": regime["label"],
            "description": regime["description"],
            "confidence": regime["confidence"],
            "signals": signals,
            "agent_guidance": regime.get("agent_guidance", {}),
            "weight_adjustments": regime.get("weight_adjustments", {}),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

        _regime_cache = result
        _cache_time = now

        logger.info(f"🌊 Regime detected: {regime['label']} (confidence: {regime['confidence']:.0%})")
        return result

    def _check_vix(self) -> dict:
        """Check VIX level for fear/complacency."""
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1mo")
            if hist.empty:
                return {"level": None, "signal": "unknown"}

            current = float(hist["Close"].iloc[-1])
            avg_20 = float(hist["Close"].tail(20).mean())

            if current > 30:
                signal = "extreme_fear"
            elif current > 20:
                signal = "elevated_fear"
            elif current < 12:
                signal = "extreme_complacency"
            elif current < 15:
                signal = "low_volatility"
            else:
                signal = "normal"

            return {
                "level": round(current, 1),
                "avg_20d": round(avg_20, 1),
                "signal": signal,
                "vs_avg": round(((current - avg_20) / avg_20) * 100, 1),
            }
        except Exception as e:
            logger.warning(f"VIX check failed: {e}")
            return {"level": None, "signal": "unknown"}

    def _check_yield_curve(self) -> dict:
        """Check 10Y-2Y yield spread for recession signals."""
        try:
            us10y = yf.Ticker("^TNX")
            us2y = yf.Ticker("2YY=F")

            h10 = us10y.history(period="1mo")
            h2 = us2y.history(period="1mo")

            if h10.empty or h2.empty:
                return {"spread": None, "signal": "unknown"}

            y10 = float(h10["Close"].iloc[-1])
            y2 = float(h2["Close"].iloc[-1])
            spread = y10 - y2

            if spread < -0.5:
                signal = "deeply_inverted"
            elif spread < 0:
                signal = "inverted"
            elif spread < 0.5:
                signal = "flat"
            elif spread < 1.5:
                signal = "normal"
            else:
                signal = "steep"

            return {
                "spread": round(spread, 2),
                "us10y": round(y10, 2),
                "us2y": round(y2, 2),
                "signal": signal,
            }
        except Exception as e:
            logger.warning(f"Yield curve check failed: {e}")
            return {"spread": None, "signal": "unknown"}

    def _check_safe_haven_flow(self) -> dict:
        """Check if money is flowing to safe havens (gold) vs risk (stocks)."""
        try:
            gold = yf.Ticker("GC=F")
            sp500 = yf.Ticker("^GSPC")

            g_hist = gold.history(period="1mo")
            s_hist = sp500.history(period="1mo")

            if g_hist.empty or s_hist.empty:
                return {"signal": "unknown"}

            gold_ret_5d = float((g_hist["Close"].iloc[-1] / g_hist["Close"].iloc[-5] - 1) * 100)
            sp_ret_5d = float((s_hist["Close"].iloc[-1] / s_hist["Close"].iloc[-5] - 1) * 100)

            diff = gold_ret_5d - sp_ret_5d  # Positive = flow toward safety

            if diff > 3:
                signal = "strong_safe_haven"
            elif diff > 1:
                signal = "mild_safe_haven"
            elif diff < -3:
                signal = "strong_risk_appetite"
            elif diff < -1:
                signal = "mild_risk_appetite"
            else:
                signal = "neutral"

            return {
                "gold_5d_return": round(gold_ret_5d, 2),
                "sp500_5d_return": round(sp_ret_5d, 2),
                "diff": round(diff, 2),
                "signal": signal,
            }
        except Exception as e:
            logger.warning(f"Safe haven check failed: {e}")
            return {"signal": "unknown"}

    def _check_market_momentum(self) -> dict:
        """Check broad market momentum across asset classes."""
        try:
            sp = yf.Ticker("^GSPC")
            hist = sp.history(period="3mo")
            if hist.empty or len(hist) < 50:
                return {"signal": "unknown"}

            close = hist["Close"]
            sma_50 = close.rolling(50).mean()
            current = float(close.iloc[-1])
            sma = float(sma_50.iloc[-1])

            ret_5d = float((close.iloc[-1] / close.iloc[-5] - 1) * 100)
            ret_20d = float((close.iloc[-1] / close.iloc[-20] - 1) * 100)

            above_sma = current > sma

            if ret_20d > 5 and above_sma:
                signal = "strong_bullish"
            elif ret_20d > 0 and above_sma:
                signal = "bullish"
            elif ret_20d < -5 and not above_sma:
                signal = "strong_bearish"
            elif ret_20d < 0 and not above_sma:
                signal = "bearish"
            else:
                signal = "neutral"

            return {
                "sp500_vs_sma50": round(((current - sma) / sma) * 100, 2),
                "ret_5d": round(ret_5d, 2),
                "ret_20d": round(ret_20d, 2),
                "above_sma50": above_sma,
                "signal": signal,
            }
        except Exception as e:
            logger.warning(f"Momentum check failed: {e}")
            return {"signal": "unknown"}

    def _check_usd(self) -> dict:
        """Check USD strength via DXY proxy (EURUSD inverse)."""
        try:
            eurusd = yf.Ticker("EURUSD=X")
            hist = eurusd.history(period="1mo")
            if hist.empty:
                return {"signal": "unknown"}

            current = float(hist["Close"].iloc[-1])
            ret_5d = float((hist["Close"].iloc[-1] / hist["Close"].iloc[-5] - 1) * 100)

            # EUR/USD falling = USD strengthening
            if ret_5d < -1:
                signal = "usd_strong"
            elif ret_5d < -0.3:
                signal = "usd_mild_strong"
            elif ret_5d > 1:
                signal = "usd_weak"
            elif ret_5d > 0.3:
                signal = "usd_mild_weak"
            else:
                signal = "neutral"

            return {
                "eurusd": round(current, 4),
                "eurusd_5d_change": round(ret_5d, 2),
                "signal": signal,
            }
        except Exception as e:
            logger.warning(f"USD check failed: {e}")
            return {"signal": "unknown"}

    def _classify_regime(self, signals: dict) -> dict:
        """Classify market regime from all signals."""
        scores = {
            "risk-on": 0,
            "risk-off": 0,
            "inflation": 0,
            "deflation": 0,
        }

        # VIX signals
        vix_sig = signals.get("vix", {}).get("signal", "unknown")
        if vix_sig == "extreme_fear":
            scores["risk-off"] += 3
        elif vix_sig == "elevated_fear":
            scores["risk-off"] += 2
        elif vix_sig == "extreme_complacency":
            scores["risk-on"] += 2
        elif vix_sig == "low_volatility":
            scores["risk-on"] += 1

        # Yield curve
        yc_sig = signals.get("yield_curve", {}).get("signal", "unknown")
        if yc_sig == "deeply_inverted":
            scores["risk-off"] += 2
            scores["deflation"] += 1
        elif yc_sig == "inverted":
            scores["risk-off"] += 1
        elif yc_sig == "steep":
            scores["risk-on"] += 1
            scores["inflation"] += 1

        # Safe haven flows
        sh_sig = signals.get("gold_vs_stocks", {}).get("signal", "unknown")
        if "safe_haven" in sh_sig:
            scores["risk-off"] += 2 if "strong" in sh_sig else 1
        elif "risk_appetite" in sh_sig:
            scores["risk-on"] += 2 if "strong" in sh_sig else 1

        # Market momentum
        mom_sig = signals.get("market_momentum", {}).get("signal", "unknown")
        if "bullish" in mom_sig:
            scores["risk-on"] += 2 if "strong" in mom_sig else 1
        elif "bearish" in mom_sig:
            scores["risk-off"] += 2 if "strong" in mom_sig else 1

        # USD
        usd_sig = signals.get("usd", {}).get("signal", "unknown")
        if "usd_strong" in usd_sig:
            scores["risk-off"] += 1
        elif "usd_weak" in usd_sig:
            scores["inflation"] += 1
            scores["risk-on"] += 1

        # Find dominant regime
        max_score = max(scores.values())
        if max_score <= 1:
            regime_name = "transition"
        else:
            regime_name = max(scores, key=scores.get)

        total_points = sum(scores.values())
        confidence = max_score / max(1, total_points) if total_points > 0 else 0

        profile = REGIME_PROFILES.get(regime_name, REGIME_PROFILES["transition"])
        return {
            "name": regime_name,
            "label": profile["label"],
            "description": profile["description"],
            "confidence": round(confidence, 2),
            "scores": scores,
            "agent_guidance": profile["agent_guidance"],
            "weight_adjustments": profile["weight_adjustments"],
        }

    def get_context_for_agent(self, agent_name: str) -> str:
        """Generate regime context for a specific agent."""
        regime = self.detect_regime()

        guidance = regime.get("agent_guidance", {}).get(agent_name, "")
        if not guidance:
            return ""

        vix = regime["signals"].get("vix", {})
        vix_text = f"VIX: {vix.get('level', '?')}" if vix.get("level") else ""

        parts = [
            f"\nMARKNADSREGIM: {regime['label']} (confidence: {regime['confidence']:.0%})",
            f"  {regime['description']}",
            f"  Vägledning för din analys: {guidance}",
        ]
        if vix_text:
            parts.append(f"  {vix_text}")

        return "\n".join(parts)

    def get_supervisor_context(self) -> str:
        """Generate regime context for supervisor."""
        regime = self.detect_regime()
        signals = regime["signals"]

        parts = [f"MARKNADSREGIM: {regime['label']} (confidence: {regime['confidence']:.0%})"]
        parts.append(f"  {regime['description']}")

        # Key signals
        vix = signals.get("vix", {})
        if vix.get("level"):
            parts.append(f"  VIX: {vix['level']} ({vix['signal']}, {vix.get('vs_avg', 0):+.0f}% vs 20d medel)")

        yc = signals.get("yield_curve", {})
        if yc.get("spread") is not None:
            parts.append(f"  Räntekurva (10Y-2Y): {yc['spread']:+.2f}% ({yc['signal']})")

        mom = signals.get("market_momentum", {})
        if mom.get("ret_20d") is not None:
            above = "ÖVER" if mom.get("above_sma50") else "UNDER"
            parts.append(f"  S&P 500 momentum: {mom['ret_20d']:+.1f}% (20d), {above} SMA50")

        # Weight adjustments
        adj = regime.get("weight_adjustments", {})
        if adj:
            high = [f"{k}(×{v:.1f})" for k, v in adj.items() if v > 1.05]
            low = [f"{k}(×{v:.1f})" for k, v in adj.items() if v < 0.95]
            if high:
                parts.append(f"  Vikta UPP: {', '.join(high)}")
            if low:
                parts.append(f"  Vikta NED: {', '.join(low)}")

        return "\n".join(parts)


# Singleton
regime_detector = RegimeDetector()
