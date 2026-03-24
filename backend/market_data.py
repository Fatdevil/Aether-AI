"""
Market data fetcher - gets real prices via yfinance
"""

import yfinance as yf
import logging
from datetime import datetime, timezone
from typing import Optional
from technical_indicators import calculate_indicators, format_indicators_for_prompt

logger = logging.getLogger("aether.market")

# Ticker mapping for all our tracked assets
ASSET_TICKERS = {
    "btc": {"ticker": "BTC-USD", "name": "Bitcoin", "category": "Krypto", "currency": "$"},
    "global-equity": {"ticker": "ACWI", "name": "Globala Aktier (ACWI)", "category": "Aktier", "currency": "$"},
    "sp500": {"ticker": "^GSPC", "name": "S&P 500", "category": "Aktier", "currency": "$"},
    "gold": {"ticker": "GC=F", "name": "Guld (XAU)", "category": "Råvaror", "currency": "$"},
    "silver": {"ticker": "SI=F", "name": "Silver (XAG)", "category": "Råvaror", "currency": "$"},
    "eurusd": {"ticker": "EURUSD=X", "name": "EUR/USD", "category": "Valuta", "currency": ""},
    "oil": {"ticker": "BZ=F", "name": "Råolja (Brent)", "category": "Råvaror", "currency": "$"},
    "us10y": {"ticker": "^TNX", "name": "US 10Y Räntor", "category": "Räntor", "currency": "%"},
}


def fetch_all_prices() -> dict:
    """Fetch current prices and daily change for all assets."""
    results = {}

    tickers_list = [v["ticker"] for v in ASSET_TICKERS.values()]
    logger.info(f"Fetching prices for {len(tickers_list)} tickers...")

    try:
        # Batch download for efficiency
        data = yf.download(tickers_list, period="5d", group_by="ticker", progress=False)

        for asset_id, info in ASSET_TICKERS.items():
            ticker = info["ticker"]
            try:
                if len(tickers_list) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else None

                if ticker_data is not None and not ticker_data.empty:
                    # Get last 2 available closes
                    closes = ticker_data["Close"].dropna()
                    if len(closes) >= 2:
                        current_price = float(closes.iloc[-1])
                        prev_price = float(closes.iloc[-2])
                        change_pct = ((current_price - prev_price) / prev_price) * 100

                        results[asset_id] = {
                            "price": current_price,
                            "prev_price": prev_price,
                            "change_pct": round(change_pct, 2),
                            "currency": info["currency"],
                            "updated": datetime.now(timezone.utc).isoformat(),
                        }
                        # Calculate technical indicators
                        try:
                            indicators = calculate_indicators(ticker, asset_id)
                            results[asset_id]["indicators"] = indicators
                            results[asset_id]["indicators_text"] = format_indicators_for_prompt(indicators)
                        except Exception as e:
                            logger.warning(f"  ⚠️ Indicator calc failed for {asset_id}: {e}")
                            results[asset_id]["indicators"] = {}
                            results[asset_id]["indicators_text"] = ""
                        logger.info(f"  ✅ {info['name']}: {info['currency']}{current_price:.2f} ({change_pct:+.2f}%)")
                    elif len(closes) == 1:
                        current_price = float(closes.iloc[-1])
                        results[asset_id] = {
                            "price": current_price,
                            "prev_price": current_price,
                            "change_pct": 0.0,
                            "currency": info["currency"],
                            "updated": datetime.now(timezone.utc).isoformat(),
                        }
                        logger.info(f"  ⚠️ {info['name']}: {info['currency']}{current_price:.2f} (single data point)")
                else:
                    logger.warning(f"  ❌ No data for {ticker}")
                    results[asset_id] = _fallback_price(asset_id, info)

            except Exception as e:
                logger.warning(f"  ❌ Error for {ticker}: {e}")
                results[asset_id] = _fallback_price(asset_id, info)

    except Exception as e:
        logger.error(f"Batch download failed: {e}")
        # Use individual fetches as fallback
        for asset_id, info in ASSET_TICKERS.items():
            try:
                t = yf.Ticker(info["ticker"])
                hist = t.history(period="5d")
                if not hist.empty:
                    closes = hist["Close"].dropna()
                    if len(closes) >= 2:
                        current_price = float(closes.iloc[-1])
                        prev_price = float(closes.iloc[-2])
                        change_pct = ((current_price - prev_price) / prev_price) * 100
                        results[asset_id] = {
                            "price": current_price,
                            "prev_price": prev_price,
                            "change_pct": round(change_pct, 2),
                            "currency": info["currency"],
                            "updated": datetime.now(timezone.utc).isoformat(),
                        }
                        logger.info(f"  ✅ (fallback) {info['name']}: {info['currency']}{current_price:.2f}")
                    else:
                        results[asset_id] = _fallback_price(asset_id, info)
                else:
                    results[asset_id] = _fallback_price(asset_id, info)
            except Exception as e2:
                logger.warning(f"  ❌ Individual fetch failed for {info['ticker']}: {e2}")
                results[asset_id] = _fallback_price(asset_id, info)

    return results


def fetch_price_history(asset_id: str, period: str = "6mo") -> list:
    """Fetch historical price data for scenario chart."""
    info = ASSET_TICKERS.get(asset_id)
    if not info:
        return []

    try:
        t = yf.Ticker(info["ticker"])
        hist = t.history(period=period)
        if hist.empty:
            return []

        # Resample to monthly for scenario chart
        monthly = hist["Close"].resample("ME").last().dropna()
        return [
            {"date": d.strftime("%Y-%m"), "price": round(float(p), 2)}
            for d, p in monthly.items()
        ]
    except Exception as e:
        logger.warning(f"History fetch failed for {asset_id}: {e}")
        return []


def _fallback_price(asset_id: str, info: dict) -> dict:
    """Return a reasonable fallback price when data is unavailable."""
    fallbacks = {
        "btc": 85000, "global-equity": 120, "sp500": 5300,
        "gold": 2400, "silver": 30, "eurusd": 1.09,
        "oil": 75, "us10y": 4.2,
    }
    price = fallbacks.get(asset_id, 0)
    return {
        "price": price,
        "prev_price": price,
        "change_pct": 0.0,
        "currency": info["currency"],
        "updated": datetime.now(timezone.utc).isoformat(),
        "is_fallback": True,
    }
