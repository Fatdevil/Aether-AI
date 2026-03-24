"""
Correlation Engine - Analyzes cross-asset correlations and generates systemic signals.
Detects when multiple assets align (risk-on/risk-off) and provides correlation context
for agents and supervisor to make better-informed decisions.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger("aether.correlation")

# Cache per period
_corr_cache: dict[str, dict] = {}
_cache_times: dict[str, float] = {}
_CACHE_TTL = 600  # 10 minutes (correlations change slowly)

# Asset tickers for correlation calculation
CORRELATION_TICKERS = {
    "btc": "BTC-USD",
    "sp500": "^GSPC",
    "gold": "GC=F",
    "silver": "SI=F",
    "oil": "BZ=F",
    "us10y": "^TNX",
    "eurusd": "EURUSD=X",
    "global-equity": "ACWI",
}

# Risk sentiment mapping: positive return = risk-on for these assets
RISK_ON_ASSETS = {"btc", "sp500", "global-equity", "oil", "silver"}   # Up = risk-on
RISK_OFF_ASSETS = {"gold", "us10y"}                                     # Up = risk-off
# eurusd is ambiguous

# Known fundamental relationships
FUNDAMENTAL_PAIRS = [
    ("gold", "us10y", "inverse", "Guld faller när räntor stiger (högre reala räntor)"),
    ("gold", "eurusd", "positive", "Guld och EUR tenderar att röra sig med svagare USD"),
    ("sp500", "us10y", "complex", "Räntor och aktier: beror på om räntor stiger pga tillväxt eller inflation"),
    ("btc", "sp500", "positive", "BTC korrelerar med riskaptit sedan 2020"),
    ("oil", "sp500", "positive", "Olja stiger med ekonomisk tillväxt"),
    ("gold", "btc", "weak_positive", "Båda ses som inflationshedge men BTC är volatilare"),
]

PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}


class CorrelationEngine:
    """Calculates and provides cross-asset correlation intelligence."""

    def calculate_correlations(self, period: str = "30d") -> dict:
        """Calculate correlation matrix from recent price data."""
        global _corr_cache, _cache_times

        now = time.monotonic()
        if period in _cache_times and now - _cache_times[period] < _CACHE_TTL and period in _corr_cache:
            return _corr_cache[period]

        try:
            tickers = list(CORRELATION_TICKERS.values())
            data = yf.download(tickers, period="1y", progress=False)

            if data.empty:
                logger.warning("No data for correlation calculation")
                return {}

            # Extract close prices – yfinance returns MultiIndex (Price, Ticker)
            if isinstance(data.columns, pd.MultiIndex):
                close_data = data["Close"]
            else:
                close_data = data[["Close"]]

            closes = {}
            for asset_id, ticker in CORRELATION_TICKERS.items():
                try:
                    if ticker in close_data.columns:
                        series = close_data[ticker].dropna()
                        if len(series) >= 10:
                            closes[asset_id] = series
                except Exception:
                    pass

            if len(closes) < 3:
                logger.warning(f"Only got {len(closes)} assets for correlation")
                return {}

            # Build returns DataFrame
            returns_df = pd.DataFrame({
                aid: series.pct_change().dropna()
                for aid, series in closes.items()
            })

            # Get the right number of days
            days = PERIOD_DAYS.get(period, 30)
            recent = returns_df.tail(days)

            # Correlation matrix
            corr_matrix = recent.corr()

            # Calculate systemic risk signal
            systemic = self._calculate_systemic_signal(recent)

            # Notable correlations (strongest pairs)
            notable = self._find_notable_correlations(corr_matrix)

            result = {
                "matrix": {
                    row: {col: round(val, 3) for col, val in corr_matrix.loc[row].items()}
                    for row in corr_matrix.index
                },
                "systemic": systemic,
                "notable_pairs": notable,
                "period": period,
                "assets_included": list(closes.keys()),
                "calculated_at": datetime.now(timezone.utc).isoformat(),
            }

            _corr_cache[period] = result
            _cache_times[period] = now

            logger.info(f"📊 Correlations calculated: {len(closes)} assets, "
                        f"regime={systemic['regime']}, signal={systemic['signal_strength']:.1f}")

            return result

        except Exception as e:
            logger.error(f"Correlation calculation failed: {e}")
            return {}

    def _calculate_systemic_signal(self, returns: pd.DataFrame) -> dict:
        """
        Detect if the market is in risk-on or risk-off mode.
        Counts how many assets show consistent directional bias.
        """
        if returns.empty:
            return {"regime": "unknown", "signal_strength": 0, "details": {}}

        # Recent 5-day returns for each asset
        recent_5d = returns.tail(5).sum()

        risk_on_signals = 0
        risk_off_signals = 0
        details = {}

        for asset_id in returns.columns:
            ret = recent_5d.get(asset_id, 0)
            if abs(ret) < 0.005:  # Less than 0.5% = noise
                details[asset_id] = "neutral"
                continue

            if asset_id in RISK_ON_ASSETS:
                if ret > 0:
                    risk_on_signals += 1
                    details[asset_id] = "risk-on"
                else:
                    risk_off_signals += 1
                    details[asset_id] = "risk-off"
            elif asset_id in RISK_OFF_ASSETS:
                if ret > 0:
                    risk_off_signals += 1
                    details[asset_id] = "risk-off"
                else:
                    risk_on_signals += 1
                    details[asset_id] = "risk-on"
            else:
                details[asset_id] = "neutral"

        # Regime classification
        total_signals = risk_on_signals + risk_off_signals
        if total_signals == 0:
            regime = "range-bound"
            signal_strength = 0
        elif risk_on_signals >= 4 and risk_off_signals <= 1:
            regime = "risk-on"
            signal_strength = risk_on_signals / max(1, total_signals)
        elif risk_off_signals >= 4 and risk_on_signals <= 1:
            regime = "risk-off"
            signal_strength = risk_off_signals / max(1, total_signals)
        elif risk_on_signals > risk_off_signals:
            regime = "leaning-risk-on"
            signal_strength = (risk_on_signals - risk_off_signals) / max(1, total_signals)
        elif risk_off_signals > risk_on_signals:
            regime = "leaning-risk-off"
            signal_strength = (risk_off_signals - risk_on_signals) / max(1, total_signals)
        else:
            regime = "mixed"
            signal_strength = 0

        return {
            "regime": regime,
            "signal_strength": round(signal_strength, 2),
            "risk_on_count": risk_on_signals,
            "risk_off_count": risk_off_signals,
            "details": details,
        }

    def _find_notable_correlations(self, corr_matrix: pd.DataFrame) -> list[dict]:
        """Find the most notable (strongest and most unusual) correlations."""
        notable = []
        seen = set()

        for row in corr_matrix.index:
            for col in corr_matrix.columns:
                if row == col:
                    continue
                pair_key = tuple(sorted([row, col]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                corr = corr_matrix.loc[row, col]
                if abs(corr) < 0.3:
                    continue  # Too weak to mention

                # Check if this deviates from fundamental expectation
                fundamental = None
                for a, b, rel, desc in FUNDAMENTAL_PAIRS:
                    if set(pair_key) == {a, b}:
                        fundamental = (rel, desc)
                        break

                notable.append({
                    "asset_a": row,
                    "asset_b": col,
                    "correlation": round(corr, 3),
                    "strength": "stark" if abs(corr) > 0.7 else "måttlig" if abs(corr) > 0.4 else "svag",
                    "fundamental": fundamental,
                })

        # Sort by absolute correlation (strongest first)
        notable.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return notable[:10]

    def get_context_for_asset(self, asset_id: str) -> str:
        """Generate correlation context for a specific asset's agent prompt."""
        data = self.calculate_correlations()
        if not data or "matrix" not in data:
            return ""

        matrix = data["matrix"]
        systemic = data["systemic"]

        if asset_id not in matrix:
            return ""

        parts = ["\nKORRELATIONER (senaste 30d):"]

        # This asset's correlations with others
        asset_corrs = matrix[asset_id]
        significant = [
            (other, corr) for other, corr in asset_corrs.items()
            if other != asset_id and abs(corr) >= 0.3
        ]
        significant.sort(key=lambda x: abs(x[1]), reverse=True)

        name_map = {
            "btc": "Bitcoin", "sp500": "S&P 500", "gold": "Guld", "silver": "Silver",
            "oil": "Olja", "us10y": "US10Y", "eurusd": "EUR/USD", "global-equity": "ACWI",
        }

        for other, corr in significant[:5]:
            direction = "positiv" if corr > 0 else "negativ"
            strength = "stark" if abs(corr) > 0.7 else "måttlig"
            other_name = name_map.get(other, other)
            parts.append(f"  {other_name}: {corr:+.2f} ({strength} {direction})")

        # Systemic regime
        regime_text = {
            "risk-on": "📈 RISK-ON: Majoriteten av tillgångar stiger – riskaptit",
            "risk-off": "📉 RISK-OFF: Tillgångar faller – defensivt läge",
            "leaning-risk-on": "↗️ Lutar risk-on: flertalet positiva men blandat",
            "leaning-risk-off": "↘️ Lutar risk-off: flertalet negativa",
            "mixed": "↔️ Blandat: ingen tydlig riktning",
            "range-bound": "➡️ Range-bound: minimal rörelse",
        }.get(systemic["regime"], "Okänt")

        parts.append(f"  Systemisk signal: {regime_text}")
        parts.append(f"  ({systemic['risk_on_count']} tillgångar risk-on, "
                     f"{systemic['risk_off_count']} risk-off)")

        return "\n".join(parts)

    def get_supervisor_context(self) -> str:
        """Generate correlation context for supervisor overview."""
        data = self.calculate_correlations()
        if not data:
            return ""

        systemic = data["systemic"]
        notable = data.get("notable_pairs", [])

        parts = ["CROSS-ASSET ANALYS:"]

        # Regime
        regime = systemic["regime"]
        strength = systemic["signal_strength"]
        parts.append(f"  Marknadsregim: {regime.upper()} (styrka: {strength:.0%})")

        # Notable pairs
        if notable:
            parts.append("  Starkaste korrelationer:")
            for pair in notable[:4]:
                parts.append(
                    f"    {pair['asset_a']}↔{pair['asset_b']}: {pair['correlation']:+.2f} ({pair['strength']})"
                )
                if pair.get("fundamental"):
                    parts.append(f"      → {pair['fundamental'][1]}")

        return "\n".join(parts)


# Singleton
correlation_engine = CorrelationEngine()
