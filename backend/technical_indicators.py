"""
Technical Indicators - Calculates real technical analysis indicators using pandas.
Provides RSI, SMA, MACD, Bollinger Bands, ATR, volume analysis, and trend signals.
Pure pandas/numpy — no external TA library needed.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger("aether.indicators")

# Cache to avoid re-fetching within same refresh cycle
_indicator_cache: dict[str, dict] = {}
_cache_time: float = 0
_CACHE_TTL = 120  # 2 minutes


# ============================================================
# Pure pandas indicator functions (no pandas_ta dependency)
# ============================================================

def _sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=length, min_periods=length).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """RSI — Wilder's Smoothing."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD — returns (macd_line, signal_line, histogram)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bbands(series: pd.Series, length: int = 20, std: float = 2.0):
    """Bollinger Bands — returns (lower, mid, upper)."""
    mid = series.rolling(window=length).mean()
    rolling_std = series.rolling(window=length).std()
    upper = mid + (rolling_std * std)
    lower = mid - (rolling_std * std)
    return lower, mid, upper


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()


# ============================================================

def calculate_indicators(ticker: str, asset_id: str = "") -> dict:
    """
    Calculate technical indicators for a ticker using yfinance data.
    Returns a comprehensive dict of indicators, or empty dict on failure.
    """
    global _indicator_cache, _cache_time

    # Check cache
    now = time.monotonic()
    if now - _cache_time < _CACHE_TTL and ticker in _indicator_cache:
        return _indicator_cache[ticker]

    try:
        t = yf.Ticker(ticker)

        # Daily data (3 months for SMA50, 10 months for SMA200)
        daily = t.history(period="10mo")
        if daily.empty or len(daily) < 20:
            logger.warning(f"Insufficient daily data for {ticker}: {len(daily)} rows")
            return {}

        close = daily["Close"].dropna()
        high = daily["High"].dropna()
        low = daily["Low"].dropna()
        volume = daily["Volume"].dropna()

        result = {}

        # === MOVING AVERAGES ===
        sma_20 = _sma(close, 20)
        sma_50 = _sma(close, 50)
        sma_200 = _sma(close, 200)

        current_price = float(close.iloc[-1])
        result["price"] = current_price

        result["sma_20"] = round(float(sma_20.iloc[-1]), 2) if sma_20 is not None and len(sma_20.dropna()) > 0 else None
        result["sma_50"] = round(float(sma_50.iloc[-1]), 2) if sma_50 is not None and len(sma_50.dropna()) > 0 else None
        result["sma_200"] = round(float(sma_200.iloc[-1]), 2) if sma_200 is not None and len(sma_200.dropna()) > 0 else None

        # Price vs SMAs (% difference)
        if result["sma_20"]:
            result["price_vs_sma20"] = round(((current_price - result["sma_20"]) / result["sma_20"]) * 100, 2)
        if result["sma_50"]:
            result["price_vs_sma50"] = round(((current_price - result["sma_50"]) / result["sma_50"]) * 100, 2)
        if result["sma_200"]:
            result["price_vs_sma200"] = round(((current_price - result["sma_200"]) / result["sma_200"]) * 100, 2)

        # Golden/Death Cross
        if result.get("sma_50") and result.get("sma_200"):
            result["golden_cross"] = result["sma_50"] > result["sma_200"]
            result["death_cross"] = result["sma_50"] < result["sma_200"]

        # === RSI (14-period Wilder's Smoothing) ===
        rsi = _rsi(close, 14)
        result["rsi_14"] = round(float(rsi.iloc[-1]), 1) if rsi is not None and not pd.isna(rsi.iloc[-1]) else None

        rsi_label = "neutral"
        if result.get("rsi_14"):
            if result["rsi_14"] >= 70:
                rsi_label = "överköpt"
            elif result["rsi_14"] >= 60:
                rsi_label = "starkt"
            elif result["rsi_14"] <= 30:
                rsi_label = "översålt"
            elif result["rsi_14"] <= 40:
                rsi_label = "svagt"
        result["rsi_label"] = rsi_label

        # === MACD (12, 26, 9) ===
        macd_line, macd_signal, macd_hist = _macd(close, 12, 26, 9)
        if macd_line is not None and len(macd_line.dropna()) > 0:
            result["macd"] = {
                "line": round(float(macd_line.iloc[-1]), 2),
                "signal": round(float(macd_signal.iloc[-1]), 2),
                "histogram": round(float(macd_hist.iloc[-1]), 2),
                "bullish": float(macd_hist.iloc[-1]) > 0,
            }

            # MACD crossover detection (last 3 days)
            if len(macd_hist) >= 3:
                prev_hist = float(macd_hist.iloc[-2])
                curr_hist = float(macd_hist.iloc[-1])
                if prev_hist <= 0 and curr_hist > 0:
                    result["macd"]["crossover"] = "bullish_cross"
                elif prev_hist >= 0 and curr_hist < 0:
                    result["macd"]["crossover"] = "bearish_cross"
                else:
                    result["macd"]["crossover"] = "none"

        # === BOLLINGER BANDS (20, 2) ===
        bb_lower, bb_mid, bb_upper = _bbands(close, 20, 2)
        if bb_upper is not None and len(bb_upper.dropna()) > 0 and not pd.isna(bb_upper.iloc[-1]):
            bb_u = float(bb_upper.iloc[-1])
            bb_l = float(bb_lower.iloc[-1])
            bb_m = float(bb_mid.iloc[-1])
            bb_width = ((bb_u - bb_l) / bb_m) * 100

            result["bollinger"] = {
                "upper": round(bb_u, 2),
                "lower": round(bb_l, 2),
                "width_pct": round(bb_width, 1),
                "position": "upper" if current_price > bb_u else "lower" if current_price < bb_l else "middle",
            }

        # === ATR (14-period True Range) ===
        atr = _atr(high, low, close, 14)
        if atr is not None and len(atr.dropna()) > 0 and not pd.isna(atr.iloc[-1]):
            atr_val = float(atr.iloc[-1])
            result["atr_14"] = round(atr_val, 2)
            result["atr_pct"] = round((atr_val / current_price) * 100, 2)

        # === VOLUME ANALYSIS ===
        if len(volume) >= 20:
            vol_sma = _sma(volume, 20)
            if vol_sma is not None and not pd.isna(vol_sma.iloc[-1]):
                vol_20_avg = float(vol_sma.iloc[-1])
                vol_current = float(volume.iloc[-1])
                if vol_20_avg > 0:
                    result["volume_vs_avg"] = round(((vol_current - vol_20_avg) / vol_20_avg) * 100, 1)

        # === RETURNS ===
        if len(close) >= 2:
            result["daily_return"] = round(((float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2])) * 100, 2)
        if len(close) >= 5:
            result["weekly_return"] = round(((float(close.iloc[-1]) - float(close.iloc[-5])) / float(close.iloc[-5])) * 100, 2)
        if len(close) >= 21:
            result["monthly_return"] = round(((float(close.iloc[-1]) - float(close.iloc[-21])) / float(close.iloc[-21])) * 100, 2)

        # === RECENT PRICE HISTORY (last 5 daily returns) ===
        if len(close) >= 6:
            recent = close.pct_change().iloc[-5:] * 100
            result["daily_returns_5d"] = [round(float(r), 2) for r in recent]

        # === TREND CLASSIFICATION ===
        trend_signals = 0
        if result.get("price_vs_sma20", 0) > 0: trend_signals += 1
        if result.get("price_vs_sma50", 0) > 0: trend_signals += 1
        if result.get("rsi_14", 50) > 50: trend_signals += 1
        if result.get("macd", {}).get("bullish"): trend_signals += 1

        if trend_signals >= 3:
            result["trend"] = "bullish"
        elif trend_signals <= 1:
            result["trend"] = "bearish"
        else:
            result["trend"] = "neutral"

        # Cache result
        _indicator_cache[ticker] = result
        _cache_time = now

        logger.info(f"  📐 {ticker}: RSI={result.get('rsi_14', '?')}, "
                     f"SMA20={result.get('price_vs_sma20', '?')}%, "
                     f"MACD={'↑' if result.get('macd', {}).get('bullish') else '↓'}, "
                     f"Trend={result.get('trend', '?')}")

        return result

    except Exception as e:
        logger.warning(f"  ❌ Indicator calculation failed for {ticker}: {e}")
        return {}



def format_indicators_for_prompt(indicators: dict) -> str:
    """Format indicators as a readable text block for agent prompts."""
    if not indicators:
        return "Tekniska indikatorer: Ej tillgängliga."

    parts = ["TEKNISKA INDIKATORER (verklig data, ej uppskattningar):"]

    # RSI
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        label = indicators.get("rsi_label", "")
        parts.append(f"  RSI(14): {rsi} ({label})")

    # Moving averages
    for sma, label in [("sma_20", "SMA20"), ("sma_50", "SMA50"), ("sma_200", "SMA200")]:
        val = indicators.get(sma)
        vs_key = f"price_vs_{sma.replace('_', '')}"
        vs = indicators.get(vs_key)
        if val is not None:
            pos = "över" if vs and vs > 0 else "under"
            parts.append(f"  {label}: {val:,.2f} (pris {vs:+.1f}% {pos})" if vs else f"  {label}: {val:,.2f}")

    # Cross signals
    if indicators.get("golden_cross"):
        parts.append("  ✅ Golden Cross aktiv (SMA50 > SMA200)")
    elif indicators.get("death_cross"):
        parts.append("  ⚠️ Death Cross aktiv (SMA50 < SMA200)")

    # MACD
    macd = indicators.get("macd")
    if macd:
        cross = macd.get("crossover", "none")
        cross_text = " (BULL CROSS!)" if cross == "bullish_cross" else " (BEAR CROSS!)" if cross == "bearish_cross" else ""
        parts.append(f"  MACD: {macd['line']:+.2f} (signal: {macd['signal']:+.2f}, "
                     f"histogram: {macd['histogram']:+.2f}, "
                     f"{'positiv' if macd['bullish'] else 'negativ'}){cross_text}")

    # Bollinger
    bb = indicators.get("bollinger")
    if bb:
        pos_text = {"upper": "ÖVER övre band", "lower": "UNDER nedre band", "middle": "inom banden"}.get(bb["position"], "")
        parts.append(f"  Bollinger: {bb['lower']:,.0f} – {bb['upper']:,.0f} (bredd: {bb['width_pct']:.1f}%, pris {pos_text})")

    # ATR
    atr = indicators.get("atr_14")
    atr_pct = indicators.get("atr_pct")
    if atr is not None:
        parts.append(f"  ATR(14): {atr:,.2f} ({atr_pct:.2f}% av pris, volatilitet)")

    # Volume
    vol = indicators.get("volume_vs_avg")
    if vol is not None:
        vol_text = "över" if vol > 0 else "under"
        parts.append(f"  Volym: {vol:+.1f}% {vol_text} 20d-medel")

    # Returns
    returns = []
    if indicators.get("daily_return") is not None:
        returns.append(f"dag: {indicators['daily_return']:+.2f}%")
    if indicators.get("weekly_return") is not None:
        returns.append(f"vecka: {indicators['weekly_return']:+.2f}%")
    if indicators.get("monthly_return") is not None:
        returns.append(f"månad: {indicators['monthly_return']:+.2f}%")
    if returns:
        parts.append(f"  Avkastning: {', '.join(returns)}")

    # Trend
    trend = indicators.get("trend")
    if trend:
        emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➡️"}.get(trend, "")
        parts.append(f"  Övergripande trend: {emoji} {trend.upper()}")

    return "\n".join(parts)


def clear_cache():
    """Clear the indicator cache."""
    global _indicator_cache, _cache_time
    _indicator_cache = {}
    _cache_time = 0
