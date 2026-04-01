"""
News aggregator - fetches from multiple RSS feeds and analyzes sentiment.
"""

import feedparser
import httpx
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("aether.news")

# Financial news RSS feeds — all free, no API key
RSS_FEEDS = [
    # Global financial
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml", "source": "BBC Business"},
    {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "source": "CNBC"},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "source": "Reuters"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "source": "NY Times"},
    {"url": "https://www.ft.com/?format=rss", "source": "Financial Times"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "source": "CNBC Finance"},
    # Markets & investing
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "source": "MarketWatch"},
    {"url": "https://finance.yahoo.com/news/rssindex", "source": "Yahoo Finance"},
    {"url": "https://www.investing.com/rss/news.rss", "source": "Investing.com"},
    # Asset-specific Google News
    {"url": "https://news.google.com/rss/search?q=bitcoin+cryptocurrency+market&hl=en-US&gl=US&ceid=US:en", "source": "Google News Crypto"},
    {"url": "https://news.google.com/rss/search?q=gold+oil+commodities+market&hl=en-US&gl=US&ceid=US:en", "source": "Google News Commodities"},
    {"url": "https://news.google.com/rss/search?q=federal+reserve+interest+rates+economy&hl=en-US&gl=US&ceid=US:en", "source": "Google News Macro"},
]

# Keywords for sentiment classification
POSITIVE_KEYWORDS = [
    "rally", "surge", "gain", "rise", "jump", "soar", "record high", "bullish",
    "growth", "expand", "profit", "boom", "optimis", "recover", "uppgång",
    "stiger", "rekord", "vinst", "köp", "buy", "upgrade", "beat", "exceed",
]

NEGATIVE_KEYWORDS = [
    "crash", "fall", "drop", "plunge", "decline", "slump", "bearish", "recession",
    "loss", "crisis", "fear", "concern", "risk", "cut", "downgrade", "miss",
    "war", "inflation", "sjunker", "faller", "förlust", "sälj", "sell",
    "tariff", "sanction", "layoff", "bankrupt",
]

# Keywords for category classification
CATEGORY_KEYWORDS = {
    "Krypto": ["bitcoin", "crypto", "btc", "ethereum", "blockchain", "coinbase"],
    "Aktier": ["stock", "equity", "s&p", "nasdaq", "dow", "aktie", "share", "ipo"],
    "Råvaror": ["gold", "guld", "oil", "olja", "silver", "commodity", "copper", "opec"],
    "Räntor": ["rate", "fed", "ecb", "bond", "yield", "treasury", "ränta", "inflation"],
    "Valuta": ["dollar", "euro", "forex", "currency", "yen", "valuta", "fx"],
    "Makro": ["gdp", "pmi", "employment", "jobs", "trade", "economy", "central bank"],
}


def classify_sentiment(text: str) -> str:
    """Keyword-based sentiment classification (fast first-pass)."""
    text_lower = text.lower()
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def _is_ambiguous(text: str) -> bool:
    """Check if both positive and negative keywords are present."""
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    return pos > 0 and neg > 0


# LLM-verified sentiment for ambiguous cases
_SENTIMENT_PROMPT = """Du avgör sentiment i finansnyheter. Svara med ETT ord: positive, negative, eller neutral.
Tolka ur marknadens perspektiv: räntesänkningar = positive, handelskrig = negative, osv."""

_pending_llm_sentiments: list[dict] = []


async def verify_ambiguous_sentiments(news_items: list[dict]) -> list[dict]:
    """Post-process: verify sentiment for ambiguous news items using LLM."""
    from llm_provider import call_llm

    verified = 0
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('summary', '')}"
        if not _is_ambiguous(text):
            continue

        try:
            response = await call_llm(
                "gemini", _SENTIMENT_PROMPT,
                f"Sentiment för: \"{item['title']}\"",
                temperature=0.0, max_tokens=20
            )
            if response:
                clean = response.strip().lower().rstrip(".")
                if clean in ("positive", "negative", "neutral"):
                    item["sentiment"] = clean
                    item["sentiment_method"] = "llm_verified"
                    verified += 1
        except Exception:
            pass

    if verified:
        logger.info(f"  🧠 LLM verified sentiment for {verified} ambiguous items")
    return news_items


def classify_category(text: str) -> str:
    """Classify news into a market category."""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text_lower)

    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else "Makro"


def fetch_all_news(max_per_feed: int = 5) -> list:
    """Fetch and parse news from RSS feeds + Marketaux API."""
    all_news = []

    # Source 1: RSS feeds (always free)
    for feed_config in RSS_FEEDS:
        try:
            logger.info(f"  Fetching RSS: {feed_config['source']}...")
            feed = feedparser.parse(feed_config["url"])

            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                summary = entry.get("summary", entry.get("description", ""))
                # Clean HTML from summary
                if summary:
                    summary = BeautifulSoup(summary, "html.parser").get_text().strip()
                    # Truncate long summaries
                    if len(summary) > 300:
                        summary = summary[:297] + "..."

                published = entry.get("published", entry.get("updated", ""))
                pub_time = _parse_time(published)

                full_text = f"{title} {summary}"

                news_item = {
                    "id": f"{feed_config['source']}-{hash(title) % 10000}",
                    "title": title,
                    "source": feed_config["source"],
                    "time": _format_relative_time(pub_time) if pub_time else "Nyss",
                    "timestamp": pub_time.isoformat() if pub_time else datetime.now(timezone.utc).isoformat(),
                    "sentiment": classify_sentiment(full_text),
                    "category": classify_category(full_text),
                    "summary": summary or "Ingen sammanfattning tillgänglig.",
                    "url": entry.get("link", ""),
                    "tickers": [],
                    "data_source": "rss",
                }
                all_news.append(news_item)

        except Exception as e:
            logger.warning(f"  ❌ Failed to fetch {feed_config['source']}: {e}")

    # Source 2: Marketaux API (free tier: 100 req/day, ticker-linked!)
    marketaux_news = _fetch_marketaux()
    all_news.extend(marketaux_news)

    # Sort by timestamp descending
    all_news.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Deduplicate by title similarity
    seen_titles = set()
    deduplicated = []
    for item in all_news:
        title_key = re.sub(r'[^a-z0-9]', '', item["title"].lower())[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduplicated.append(item)

    rss_count = sum(1 for n in deduplicated if n.get("data_source") == "rss")
    mx_count = sum(1 for n in deduplicated if n.get("data_source") == "marketaux")
    logger.info(f"  📰 Fetched {len(deduplicated)} unique news items ({rss_count} RSS + {mx_count} Marketaux)")
    return deduplicated[:50]  # Cap at 50 items


async def get_news_scout(news_items: list[dict]) -> dict:
    """
    Scout step: Gemini Flash reads all headlines and returns:
      - top_5: list of most market-moving stories with impact text
      - digest: short paragraph summarising today's market narrative

    Cost: ~$0.002 per call. Run once per analysis cycle.
    Returns empty result if LLM unavailable.
    """
    if not news_items:
        return {"top_5": [], "digest": ""}

    headlines = "\n".join(
        f"[{i+1}] {n['title']} ({n.get('source','')}, {n.get('time','')})"
        for i, n in enumerate(news_items[:40])
    )

    prompt = f"""Du är en finansanalytiker. Analysera dessa nyhetsrubriker och identifiera vilka som påverkar globala finansmarknader mest.

RUBRIKER:
{headlines}

Returnera JSON:
{{
  "top_5": [
    {{
      "index": 1,
      "headline": "...",
      "impact_score": 9,
      "affected_assets": ["btc", "sp500"],
      "impact_sv": "En mening på enkel svenska: vad händer och vad det betyder för investerare."
    }}
  ],
  "digest": "2-3 meningar: Nutidens viktigaste marknadsberättelse att känna till."
}}

Regler:
- impact_score: 1-10 (10 = högst marknadspåverkan)
- impact_sv: konkret, inga klichéer, förklara EFFEKTEN (inte bara händelsen)
- Bara JSON, inget annat"""

    try:
        from llm_provider import call_llm_tiered, parse_llm_json
        resp, provider = await call_llm_tiered(
            tier=0,
            system_prompt="Du är finansanalytiker. Svara ENBART med JSON.",
            user_prompt=prompt,
            temperature=0.2,
            max_tokens=1200,
        )
        parsed = parse_llm_json(resp)
        if parsed and parsed.get("top_5"):
            # Stamp impact_sv back onto source news items
            top_headlines = {item["headline"]: item["impact_sv"] for item in parsed["top_5"]}
            for news in news_items:
                title = news["title"]
                if title in top_headlines:
                    news["impact_sv"] = top_headlines[title]
                    news["is_top_story"] = True
            logger.info(f"  🔍 News Scout: {len(parsed['top_5'])} top stories identified via {provider}")
            return parsed
    except Exception as e:
        logger.warning(f"  News Scout failed: {e}")

    return {"top_5": [], "digest": ""}


def _fetch_marketaux() -> list:
    """Fetch financial news from Marketaux API.

    SOFT-DISABLED: Only runs if MARKETAUX_ENABLED=true env var is set.
    Default is disabled — replaced by free RSS + Google News feeds.
    Set MARKETAUX_ENABLED=true in Railway if you want to re-enable.
    """
    import os
    if os.getenv("MARKETAUX_ENABLED", "false").lower() != "true":
        return []  # Disabled by default — save $49/mån
    api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        return []

    news_items = []

    # Tickers we actively monitor in Aether AI
    TRACKED_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL", "AMZN",
                        "BTC", "ETH", "XAU", "XAG", "CL", "SPY"]

    try:
        logger.info("  Fetching Marketaux API (Standard plan)...")
        with httpx.Client(timeout=20.0) as client:

            # Request 1: Global financial news (English)
            _fetch_mx_page(client, api_key, {
                "language": "en",
                "filter_entities": "true",
                "must_have_entities": "true",
                "limit": 50,
            }, news_items)

            # Request 2: Swedish financial news
            _fetch_mx_page(client, api_key, {
                "language": "sv",
                "filter_entities": "true",
                "limit": 20,
            }, news_items)

            # Request 3: News for tracked symbols
            _fetch_mx_page(client, api_key, {
                "symbols": ",".join(TRACKED_SYMBOLS),
                "filter_entities": "true",
                "limit": 50,
            }, news_items)

        logger.info(f"  📡 Marketaux: {len(news_items)} articles fetched")

    except Exception as e:
        logger.warning(f"  ❌ Marketaux error: {e}")

    return news_items


def _fetch_mx_page(client, api_key: str, params: dict, results: list):
    """Fetch one page of Marketaux news and append parsed items."""
    try:
        params["api_token"] = api_key
        response = client.get("https://api.marketaux.com/v1/news/all", params=params)
        if response.status_code != 200:
            logger.warning(f"  Marketaux returned {response.status_code}")
            return

        data = response.json()
        articles = data.get("data", [])

        for article in articles:
            title = article.get("title", "").strip()
            if not title:
                continue

            # Extract tickers and entity sentiment from entities
            tickers = []
            entity_sentiments = []
            entities = article.get("entities", [])
            for entity in entities:
                symbol = entity.get("symbol", "")
                if symbol:
                    tickers.append(symbol)
                # Entity-level sentiment (more precise than article-level)
                e_sentiment = entity.get("sentiment_score")
                if e_sentiment is not None:
                    entity_sentiments.append({
                        "symbol": symbol,
                        "score": e_sentiment,
                        "name": entity.get("name", ""),
                        "match_score": entity.get("match_score", 0),
                    })

            # Determine article sentiment
            sentiment = "neutral"
            sentiment_score = 0.0

            # Prefer entity-level sentiment (most precise)
            if entity_sentiments:
                avg_score = sum(e["score"] for e in entity_sentiments) / len(entity_sentiments)
                sentiment_score = avg_score
                if avg_score > 0.15:
                    sentiment = "positive"
                elif avg_score < -0.15:
                    sentiment = "negative"
            else:
                # Fallback to keyword-based
                sentiment = classify_sentiment(title)

            pub = article.get("published_at", "")
            pub_time = _parse_time(pub) if pub else None

            description = article.get("description", "") or ""
            if len(description) > 300:
                description = description[:297] + "..."

            lang = article.get("language", "en")

            results.append({
                "id": f"mx-{hash(title) % 100000}",
                "title": title,
                "source": article.get("source", "Marketaux"),
                "time": _format_relative_time(pub_time) if pub_time else "Nyss",
                "timestamp": pub_time.isoformat() if pub_time else datetime.now(timezone.utc).isoformat(),
                "sentiment": sentiment,
                "sentiment_score": round(sentiment_score, 3),
                "category": classify_category(title + " " + description),
                "summary": description or title,
                "url": article.get("url", ""),
                "tickers": tickers[:5],
                "entity_sentiments": entity_sentiments[:5],
                "data_source": "marketaux",
                "language": lang,
            })

    except Exception as e:
        logger.warning(f"  ❌ Marketaux page error: {e}")


def fetch_trending_entities(api_key: str = None) -> list:
    """Fetch trending entities from Marketaux (Standard plan)."""
    import os
    if not api_key:
        api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        return []

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                "https://api.marketaux.com/v1/entity/trending/aggregation",
                params={
                    "api_token": api_key,
                    "language": "en",
                    "min_doc_count": 5,
                    "published_after": (datetime.now(timezone.utc).replace(hour=0, minute=0)).strftime("%Y-%m-%dT%H:%M"),
                    "limit": 20,
                },
            )
            if response.status_code != 200:
                return []

            data = response.json()
            entities = data.get("data", [])

            trending = []
            for e in entities:
                trending.append({
                    "symbol": e.get("key", ""),
                    "mentions": e.get("total_documents", 0),
                    "sentiment_avg": round(e.get("sentiment_avg", 0) or 0, 3),
                    "score": round(e.get("score", 0) or 0, 2),
                })

            logger.info(f"  🔥 Trending: {len(trending)} entities")
            return trending

    except Exception as e:
        logger.warning(f"  ❌ Trending fetch error: {e}")
        return []


def fetch_entity_sentiment_stats(symbols: list[str], days: int = 7, api_key: str = None) -> dict:
    """Fetch sentiment time series for given symbols (Standard plan)."""
    import os
    if not api_key:
        api_key = os.getenv("MARKETAUX_API_KEY", "")
    if not api_key:
        return {}

    try:
        published_after = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d")

        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                "https://api.marketaux.com/v1/entity/stats/intraday",
                params={
                    "api_token": api_key,
                    "symbols": ",".join(symbols[:20]),
                    "interval": "day",
                    "published_after": published_after,
                    "language": "en",
                },
            )
            if response.status_code != 200:
                return {}

            data = response.json()
            time_series = data.get("data", [])

            # Restructure: { symbol: [{date, sentiment_avg, total_documents}, ...] }
            result = {}
            for day_data in time_series:
                date = day_data.get("date", "")
                for entity in day_data.get("data", []):
                    symbol = entity.get("key", "")
                    if symbol not in result:
                        result[symbol] = []
                    result[symbol].append({
                        "date": date[:10],
                        "sentiment_avg": round(entity.get("sentiment_avg", 0) or 0, 3),
                        "mentions": entity.get("total_documents", 0),
                    })

            logger.info(f"  📊 Sentiment stats: {len(result)} symbols, {days}d")
            return result

    except Exception as e:
        logger.warning(f"  ❌ Sentiment stats error: {e}")
        return {}


def _parse_time(time_str: str) -> Optional[datetime]:
    """Parse various RSS time formats."""
    if not time_str:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _format_relative_time(dt: datetime) -> str:
    """Format as '2 timmar sedan' style."""
    now = datetime.now(timezone.utc)
    diff = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt

    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Nyss"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins} min sedan"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} {'timme' if hours == 1 else 'timmar'} sedan"
    else:
        days = seconds // 86400
        return f"{days} {'dag' if days == 1 else 'dagar'} sedan"
