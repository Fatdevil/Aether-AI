"""
News aggregator - fetches from multiple RSS feeds and analyzes sentiment.
"""

import feedparser
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


def fetch_all_news(max_per_feed: int = 3) -> list:
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
    logger.info(f"  📰 Fetched {len(deduplicated)} unique news items (RSS)")
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
