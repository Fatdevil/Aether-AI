"""
User Portfolio - Custom portfolio management with image parsing.
Allows users to input their holdings manually or upload a screenshot from their broker.
Compares against AI's optimal portfolio.
"""

import os
import json
import logging
import sqlite3
import base64
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.user_portfolio")


def _get_db():
    from analysis_store import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT DEFAULT 'Min Portfölj',
            holdings TEXT NOT NULL,  -- JSON array
            total_value REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


async def parse_portfolio_image(image_data: bytes, filename: str = "portfolio.png") -> dict:
    """Use Gemini Vision to extract portfolio holdings from a screenshot."""
    try:
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            return {"error": "GOOGLE_API_KEY not configured", "holdings": []}

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)

        # Determine mime type
        ext = filename.lower().split(".")[-1]
        mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")

        prompt = """Analysera denna bild av en portfölj/depå. Extrahera ALLA innehav (aktier, fonder, ETF:er).

Returnera resultatet som JSON med denna struktur:
{
    "holdings": [
        {
            "name": "Företagsnamn eller Fondnamn",
            "ticker": "TICKER om synlig, annars null",
            "isin": "ISIN om synlig, annars null",
            "value": 12345.67,
            "weight_pct": 25.5,
            "shares": 100,
            "currency": "SEK"
        }
    ],
    "total_value": 123456.78,
    "currency": "SEK",
    "broker": "Avanza/Nordnet/annat om identifierbart"
}

Om du inte kan läsa detaljer, gissa baserat på vad som syns. Ticker ska vara i yfinance-format (t.ex. AAPL, MSFT, SEB-A.ST för svenska aktier)."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ]
        )

        # Parse response
        text = response.text
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        logger.info(f"📸 Parsed {len(result.get('holdings', []))} holdings from image")
        return result

    except Exception as e:
        logger.error(f"Failed to parse portfolio image: {e}")
        return {"error": str(e), "holdings": []}


async def search_ticker(query: str) -> list[dict]:
    """Search for a stock/fund ticker. Includes common Swedish funds."""
    import yfinance as yf

    query_lower = query.lower().strip()
    results = []

    # Common Swedish funds (not usually on yfinance by ticker)
    SWEDISH_FUNDS = [
        {"name": "Avanza Zero", "ticker": None, "isin": "SE0001732728", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Avanza Global", "ticker": None, "isin": "SE0014805311", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Avanza USA", "ticker": None, "isin": "SE0011281427", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Avanza Europa", "ticker": None, "isin": "SE0011281435", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Avanza Emerging Markets", "ticker": None, "isin": "SE0011281443", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Länsförsäkringar Global Indexnära", "ticker": None, "isin": "SE0000810780", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Swedbank Robur Ny Teknik", "ticker": None, "isin": "SE0000709116", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Swedbank Robur Technology", "ticker": None, "isin": "SE0000540656", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Swedbank Robur Globalfond", "ticker": None, "isin": "SE0000540672", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "SEB Sverige Indexfond", "ticker": None, "isin": "SE0000433716", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "SEB Hållbar Sverige Indexnära", "ticker": None, "isin": "SE0009574731", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Handelsbanken Global Index Criteria", "ticker": None, "isin": "SE0012481125", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Handelsbanken Sverige Index Criteria", "ticker": None, "isin": "SE0012481133", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Spiltan Aktiefond Investmentbolag", "ticker": None, "isin": "SE0001598199", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Spiltan Globalfond Investmentbolag", "ticker": None, "isin": "SE0014805378", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "AMF Räntefond Kort", "ticker": None, "isin": "SE0001185000", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "AMF Aktiefond Småbolag", "ticker": None, "isin": "SE0000739949", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Öhman Global Growth", "ticker": None, "isin": "SE0001165168", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "DNB Teknologi", "ticker": None, "isin": "NO0010011108", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Carnegie Strategifond", "ticker": None, "isin": "SE0000429720", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Lannebo Teknik", "ticker": None, "isin": "SE0000740871", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Lannebo Sverige Plus", "ticker": None, "isin": "SE0009806367", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "TIN Ny Teknik", "ticker": None, "isin": "SE0015244173", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Didner & Gerge Aktiefond", "ticker": None, "isin": "SE0000428839", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "Enter Sverige", "ticker": None, "isin": "SE0000828659", "type": "FUND", "price": None, "currency": "SEK"},
        {"name": "XACT OMXS30", "ticker": "XACT-OMXS30.ST", "isin": "SE0000696476", "type": "ETF", "price": None, "currency": "SEK"},
        {"name": "XACT Bull", "ticker": "XACT-BULL.ST", "isin": "SE0001732702", "type": "ETF", "price": None, "currency": "SEK"},
        {"name": "XACT Bear", "ticker": "XACT-BEAR.ST", "isin": "SE0001732694", "type": "ETF", "price": None, "currency": "SEK"},
    ]

    # Search Swedish funds first (fuzzy match on name)
    for fund in SWEDISH_FUNDS:
        if query_lower in fund["name"].lower() or (fund.get("isin") and query_lower in fund["isin"].lower()):
            results.append({**fund, "exchange": "Stockholm"})

    # Try yfinance for stocks
    candidates = [query.upper()]

    # Add Swedish exchange suffixes for Swedish stock names
    if not any(c in query.upper() for c in ['.', '-']):
        candidates.extend([
            f"{query.upper()}.ST",
            f"{query.upper()}-A.ST",
            f"{query.upper()}-B.ST",
        ])

    for ticker_str in candidates:
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            if info and info.get("regularMarketPrice"):
                # Avoid duplicates
                if not any(r.get("ticker") == ticker_str for r in results):
                    results.append({
                        "ticker": ticker_str,
                        "name": info.get("longName") or info.get("shortName", ticker_str),
                        "price": info.get("regularMarketPrice", 0),
                        "currency": info.get("currency", "USD"),
                        "type": info.get("quoteType", "EQUITY"),
                        "exchange": info.get("exchange", ""),
                    })
        except Exception:
            continue

    return results[:8]  # Max 8 results


async def fetch_holdings_data(holdings: list[dict]) -> list[dict]:
    """Fetch current price data for user holdings."""
    import yfinance as yf

    enriched = []
    for h in holdings:
        ticker_str = h.get("ticker")
        if not ticker_str:
            enriched.append({**h, "current_price": None, "change_pct": None})
            continue

        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            price = info.get("regularMarketPrice", 0)
            prev_close = info.get("previousClose", price)
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

            enriched.append({
                **h,
                "current_price": price,
                "change_pct": round(change_pct, 2),
                "name": h.get("name") or info.get("longName", ticker_str),
                "currency": h.get("currency") or info.get("currency", "USD"),
            })
        except Exception:
            enriched.append({**h, "current_price": None, "change_pct": None})

    return enriched


def save_portfolio(name: str, holdings: list[dict], total_value: float = 0) -> int:
    """Save user portfolio to database."""
    conn = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Calculate total if not provided
    if total_value <= 0:
        total_value = sum(h.get("value", 0) for h in holdings)

    cursor = conn.execute(
        "INSERT INTO user_portfolios (name, holdings, total_value, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, json.dumps(holdings), total_value, now, now)
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    logger.info(f"💼 Saved portfolio '{name}' with {len(holdings)} holdings (id={pid})")
    return pid


def get_portfolios() -> list[dict]:
    """Get all user portfolios."""
    conn = _get_db()
    rows = conn.execute("SELECT * FROM user_portfolios ORDER BY updated_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        r["holdings"] = json.loads(r["holdings"])
        result.append(r)
    return result


def get_portfolio(portfolio_id: int) -> Optional[dict]:
    """Get a specific portfolio."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM user_portfolios WHERE id = ?", (portfolio_id,)).fetchone()
    conn.close()
    if row:
        r = dict(row)
        r["holdings"] = json.loads(r["holdings"])
        return r
    return None


def delete_portfolio(portfolio_id: int) -> bool:
    """Delete a portfolio."""
    conn = _get_db()
    conn.execute("DELETE FROM user_portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    conn.close()
    return True


async def compare_portfolios(user_holdings: list[dict], ai_portfolio: dict) -> dict:
    """Compare user portfolio against AI's optimal portfolio."""
    try:
        # Get AI allocations (from data_service.get_portfolio())
        ai_allocations = ai_portfolio.get("allocations", [])

        # Calculate basic metrics
        user_total = sum(h.get("value", 0) for h in user_holdings)

        # Overlap analysis
        user_names = set(h.get("name", "").lower() for h in user_holdings if h.get("name"))
        user_tickers = set(h.get("ticker", "").split(".")[0].lower() for h in user_holdings if h.get("ticker"))
        ai_ids = set(a.get("assetId", "").lower() for a in ai_allocations)
        ai_names = set(a.get("name", "").lower() for a in ai_allocations)

        overlap_tickers = list(user_tickers & ai_ids)
        overlap_names = [n for n in user_names if any(n in ai_n for ai_n in ai_names)]
        all_overlap = list(set(overlap_tickers + overlap_names))

        # Simple volatility estimate from price data (if available)
        user_volatility = 0
        try:
            import yfinance as yf
            import numpy as np

            tickers_with_weights = [
                (h.get("ticker"), h.get("weight_pct", 0) / 100)
                for h in user_holdings if h.get("ticker")
            ]

            if tickers_with_weights:
                returns_list = []
                for ticker_str, weight in tickers_with_weights[:5]:  # Limit for speed
                    try:
                        data = yf.download(ticker_str, period="30d", progress=False)
                        if data is not None and not data.empty and len(data) > 5:
                            close_col = data["Close"]
                            if hasattr(close_col, 'iloc'):
                                rets = close_col.pct_change().dropna()
                                returns_list.append((rets.values.flatten().tolist(), weight))
                    except Exception:
                        continue

                if returns_list:
                    min_len = min(len(r[0]) for r in returns_list)
                    if min_len > 3:
                        weighted = []
                        for day in range(min_len):
                            day_ret = sum(r[0][day] * r[1] for r in returns_list)
                            weighted.append(day_ret)
                        user_volatility = round(float(np.std(weighted) * np.sqrt(252) * 100), 2)
        except Exception:
            pass

        # Active AI allocations
        active_ai = [a for a in ai_allocations if a.get("weight", 0) > 0]

        comparison = {
            "user_holdings_count": len(user_holdings),
            "user_total_value": user_total,
            "user_volatility_annual": user_volatility,
            "ai_holdings_count": len(active_ai),
            "overlap_tickers": all_overlap,
            "overlap_count": len(all_overlap),
            "diversification_score": min(100, len(user_holdings) * 12),
            "recommendations": [],
        }

        # Generate recommendations
        if len(user_holdings) < 3:
            comparison["recommendations"].append("⚠️ Din portfölj har mycket få innehav. Överväg diversifiering med fler tillgångsslag.")
        elif len(user_holdings) < 5:
            comparison["recommendations"].append("📊 Din portfölj har få innehav. Överväg att lägga till fler för bättre riskspridning.")
        if user_volatility > 25:
            comparison["recommendations"].append("⚠️ Hög volatilitet ({:.1f}%/år). Överväg att lägga till defensiva tillgångar som guld eller räntefonder.".format(user_volatility))
        if len(all_overlap) == 0 and len(active_ai) > 0:
            comparison["recommendations"].append("📊 Ingen överlapp med AI-portföljen. AI rekommenderar: " + ", ".join(a['name'] for a in active_ai[:3]))
        if user_volatility > 0 and user_volatility < 10:
            comparison["recommendations"].append("✅ Låg volatilitet ({:.1f}%/år) – konservativ portfölj.".format(user_volatility))
        if len(active_ai) > 0:
            top_ai = [f"{a['name']} ({a['weight']}%)" for a in sorted(active_ai, key=lambda x: x.get('weight', 0), reverse=True)[:3]]
            comparison["recommendations"].append("🤖 AI:s topp-allokering: " + ", ".join(top_ai))

        return comparison

    except Exception as e:
        logger.error(f"Compare failed: {e}")
        return {
            "user_holdings_count": len(user_holdings),
            "user_total_value": sum(h.get("value", 0) for h in user_holdings),
            "user_volatility_annual": 0,
            "ai_holdings_count": 0,
            "overlap_tickers": [],
            "overlap_count": 0,
            "diversification_score": min(100, len(user_holdings) * 12),
            "recommendations": ["⚠️ Kunde inte beräkna full jämförelse. Kontrollera att tickers är korrekta."],
        }


async def calculate_efficient_frontier(
    user_holdings: list[dict],
    ai_allocations: list[dict],
) -> dict:
    """Calculate efficient frontier using Monte Carlo simulation.
    Returns frontier points + positions for user and AI portfolios.
    """
    import yfinance as yf
    import numpy as np

    try:
        # Collect all unique tickers from both portfolios
        user_tickers = [h.get("ticker") for h in user_holdings if h.get("ticker")]
        ai_ticker_map = {
            "btc": "BTC-USD", "gold": "GC=F", "silver": "SI=F",
            "oil": "BZ=F", "sp500": "^GSPC", "global-equity": "ACWI",
            "eurusd": "EURUSD=X", "us10y": "^TNX",
        }
        ai_tickers = [ai_ticker_map.get(a.get("assetId", ""), "") for a in ai_allocations if a.get("weight", 0) > 0]
        ai_tickers = [t for t in ai_tickers if t]

        all_tickers = list(set(user_tickers + ai_tickers))
        if len(all_tickers) < 2:
            return {"frontier": [], "user_position": None, "ai_position": None}

        # Download 1 YEAR of data (more representative than 90d)
        data = yf.download(all_tickers, period="1y", progress=False)
        if data is None or data.empty:
            return {"frontier": [], "user_position": None, "ai_position": None}

        # Get close prices
        if "Close" in data.columns:
            close = data["Close"]
        else:
            return {"frontier": [], "user_position": None, "ai_position": None}

        # Drop any columns with too many NaN
        close = close.dropna(axis=1, thresh=int(len(close) * 0.7))
        close = close.dropna()

        if close.shape[1] < 2 or len(close) < 30:
            return {"frontier": [], "user_position": None, "ai_position": None}

        # Calculate daily returns
        returns = close.pct_change().dropna()
        n_assets = returns.shape[1]
        tickers_in_data = list(returns.columns) if hasattr(returns.columns, 'tolist') else list(returns.columns)

        # Flatten multi-index columns if needed
        if hasattr(tickers_in_data[0], '__len__') and not isinstance(tickers_in_data[0], str):
            tickers_in_data = [t[0] if isinstance(t, tuple) else t for t in tickers_in_data]

        # CAPM expected returns instead of backward-looking mean
        # E(Ri) = Rf + βi * (E(Rm) - Rf)
        risk_free = 0.04  # ~4% annual risk-free rate
        market_premium = 0.06  # ~6% equity risk premium
        market_returns = returns.mean(axis=1)  # Equal-weight proxy for market
        market_var = market_returns.var()

        expected_returns = np.zeros(n_assets)
        for i in range(n_assets):
            if market_var > 0:
                beta = returns.iloc[:, i].cov(market_returns) / market_var
                expected_returns[i] = risk_free + beta * market_premium
            else:
                expected_returns[i] = risk_free

        cov_matrix = returns.cov().values * 252

        # Monte Carlo: generate random portfolios
        n_simulations = 500
        frontier_points = []

        for _ in range(n_simulations):
            weights = np.random.dirichlet(np.ones(n_assets))
            port_return = np.dot(weights, expected_returns) * 100  # %
            port_risk = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * 100  # %
            frontier_points.append({
                "risk": round(float(port_risk), 2),
                "return": round(float(port_return), 2),
            })

        # Sort by risk and extract efficient frontier (upper envelope)
        frontier_points.sort(key=lambda p: p["risk"])

        # Extract efficient frontier (only keep points with highest return for each risk level)
        efficient = []
        risk_bins = {}
        for p in frontier_points:
            bin_key = round(p["risk"])
            if bin_key not in risk_bins or p["return"] > risk_bins[bin_key]["return"]:
                risk_bins[bin_key] = p
        efficient = sorted(risk_bins.values(), key=lambda p: p["risk"])

        # Calculate user portfolio position
        user_position = None
        try:
            user_weights = np.zeros(n_assets)
            # Build case-insensitive ticker lookup
            ticker_lookup = {}
            for i, t in enumerate(tickers_in_data):
                ticker_lookup[str(t).upper()] = i
                # Also map without suffix (.ST, .L, etc.)
                base = str(t).split('.')[0].upper()
                if base not in ticker_lookup:
                    ticker_lookup[base] = i

            # Calculate weights - if weight_pct is 0 for all, use value-weighted or equal
            has_weights = any(h.get("weight_pct", 0) > 0 for h in user_holdings)
            total_value = sum(h.get("value", 0) for h in user_holdings) if not has_weights else 0

            matched = 0
            for h in user_holdings:
                ticker = h.get("ticker")
                if not ticker:
                    continue

                # Try exact match first, then uppercase, then base ticker
                t_upper = ticker.upper()
                idx = None
                if t_upper in ticker_lookup:
                    idx = ticker_lookup[t_upper]
                elif ticker in ticker_lookup:
                    idx = ticker_lookup[ticker]

                if idx is not None:
                    if has_weights:
                        user_weights[idx] = h.get("weight_pct", 0) / 100
                    elif total_value > 0:
                        user_weights[idx] = h.get("value", 0) / total_value
                    else:
                        user_weights[idx] = 1.0 / len(user_holdings)
                    matched += 1

            logger.info(f"  📊 User position: matched {matched}/{len(user_holdings)} tickers")

            # Normalize
            if user_weights.sum() > 0:
                user_weights = user_weights / user_weights.sum()
                u_ret = np.dot(user_weights, expected_returns) * 100
                u_risk = np.sqrt(np.dot(user_weights.T, np.dot(cov_matrix, user_weights))) * 100
                user_position = {"risk": round(float(u_risk), 2), "return": round(float(u_ret), 2), "label": "Din Portfölj"}
        except Exception as e:
            logger.warning(f"User position calc failed: {e}")

        # Calculate AI portfolio position
        ai_position = None
        try:
            ai_weights = np.zeros(n_assets)
            total_ai_weight = sum(a.get("weight", 0) for a in ai_allocations)
            for a in ai_allocations:
                mapped = ai_ticker_map.get(a.get("assetId", ""), "")
                if mapped and mapped in tickers_in_data and total_ai_weight > 0:
                    idx = tickers_in_data.index(mapped)
                    ai_weights[idx] = a.get("weight", 0) / total_ai_weight
            if ai_weights.sum() > 0:
                ai_weights = ai_weights / ai_weights.sum()
                a_ret = np.dot(ai_weights, expected_returns) * 100
                a_risk = np.sqrt(np.dot(ai_weights.T, np.dot(cov_matrix, ai_weights))) * 100
                ai_position = {"risk": round(float(a_risk), 2), "return": round(float(a_ret), 2), "label": "AI-Portfölj"}
        except Exception:
            pass

        return {
            "frontier": frontier_points,
            "efficient": efficient,
            "user_position": user_position,
            "ai_position": ai_position,
            "assets_used": tickers_in_data,
        }

    except Exception as e:
        logger.error(f"Efficient frontier calculation failed: {e}")
        return {"frontier": [], "efficient": [], "user_position": None, "ai_position": None}
