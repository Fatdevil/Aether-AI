# ============================================================
# FIL: backend/predictive/prediction_markets.py (NY FIL — Fas 8)
#
# PREDICTION MARKET INTELLIGENCE
# Hämtar odds från Polymarket. Detekterar oddsförändringar.
# Matar signaler till Political Intelligence + Supervisor.
#
# PRINCIP: Odds-NIVÅN är konsensus. Odds-RÖRELSEN är signal.
# En rörelse på +15pp på 48h = någon vet något vi inte vet.
#
# API: Polymarket Gamma API — helt öppen, gratis, ingen auth
# URL: https://gamma-api.polymarket.com
# Rate limit: 4000 req/10s (mer än tillräckligt)
# ============================================================

import httpx
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("aether.prediction_markets")

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATA_FILE = os.path.join(DATA_DIR, "prediction_markets.json")
os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================
# KONFIGURATION: Vilka marknader vi bevakar
# ============================================================

MARKET_SEARCH_TERMS = [
    # Geopolitik
    "Iran", "war", "military strike", "tariff", "trade war",
    "sanctions", "China Taiwan", "NATO", "Middle East",
    # Ekonomi + Fed
    "Fed rate", "interest rate", "recession", "inflation",
    "S&P 500", "stock market", "crash",
    # Energi
    "oil price", "OPEC", "natural gas",
    # Krypto
    "Bitcoin", "crypto regulation",
    # Politik
    "Trump", "election", "impeach",
]


@dataclass
class MarketSnapshot:
    """En ögonblicksbild av en prediction market."""
    market_id: str
    question: str
    category: str
    yes_price: float        # 0.0-1.0 (= sannolikhet)
    no_price: float
    volume_24h: float
    liquidity: float
    end_date: str
    timestamp: str


@dataclass
class OddsMovement:
    """En detekterad oddsförändring."""
    market_id: str
    question: str
    category: str
    old_price: float
    new_price: float
    change_pp: float        # Förändring i procentenheter
    change_period_hours: float
    direction: str          # "UP" eller "DOWN"
    significance: str       # "MINOR" / "NOTABLE" / "MAJOR" / "EXTREME"
    volume_24h: float
    timestamp: str
    affected_assets: List[str] = field(default_factory=list)
    market_implication: str = ""


# ============================================================
# MAPPNING: Prediction market → tillgångsklasser
# ============================================================

KEYWORD_ASSET_MAP = {
    # Geopolitik
    "iran":         {"assets": ["OIL", "GOLD", "XLE", "VIX"],   "direction_if_yes": "RISK_OFF"},
    "bomb":         {"assets": ["OIL", "GOLD", "XLE", "VIX"],   "direction_if_yes": "RISK_OFF"},
    "war":          {"assets": ["OIL", "GOLD", "VIX"],          "direction_if_yes": "RISK_OFF"},
    "military":     {"assets": ["OIL", "GOLD", "VIX"],          "direction_if_yes": "RISK_OFF"},
    "tariff":       {"assets": ["SP500", "EEM", "EURUSD", "XLK", "OMXS30"], "direction_if_yes": "BEARISH_EQUITY"},
    "trade war":    {"assets": ["SP500", "EEM", "EURUSD", "XLK"], "direction_if_yes": "BEARISH_EQUITY"},
    "sanctions":    {"assets": ["OIL", "GOLD", "EEM"],          "direction_if_yes": "MIXED"},
    "china taiwan": {"assets": ["SP500", "XLK", "EEM", "VIX", "GOLD"], "direction_if_yes": "CRISIS"},
    # Ekonomi
    "recession":    {"assets": ["SP500", "XLK", "HYG", "GOLD", "TLT"], "direction_if_yes": "RISK_OFF"},
    "rate cut":     {"assets": ["SP500", "GOLD", "BTC", "US10Y", "XLF"], "direction_if_yes": "BULLISH"},
    "rate hike":    {"assets": ["SP500", "GOLD", "BTC", "US10Y"], "direction_if_yes": "BEARISH"},
    "crash":        {"assets": ["SP500", "VIX", "GOLD", "TLT"], "direction_if_yes": "CRISIS"},
    "inflation":    {"assets": ["GOLD", "OIL", "US10Y"],        "direction_if_yes": "INFLATION"},
    # Energi
    "oil price":    {"assets": ["OIL", "XLE"],                  "direction_if_yes": "BULLISH_OIL"},
    "opec":         {"assets": ["OIL", "XLE"],                  "direction_if_yes": "BULLISH_OIL"},
    # Krypto
    "bitcoin":      {"assets": ["BTC"],                         "direction_if_yes": "BULLISH_CRYPTO"},
    # Politik
    "trump":        {"assets": ["SP500", "GOLD", "EURUSD"],     "direction_if_yes": "UNCERTAINTY"},
}

DIRECTION_INVERT = {
    "RISK_OFF": "RISK_ON", "RISK_ON": "RISK_OFF",
    "BEARISH_EQUITY": "BULLISH_EQUITY", "BULLISH_EQUITY": "BEARISH_EQUITY",
    "CRISIS": "RELIEF", "RELIEF": "CRISIS",
    "BULLISH": "BEARISH", "BEARISH": "BULLISH",
    "BULLISH_OIL": "BEARISH_OIL", "BEARISH_OIL": "BULLISH_OIL",
    "BULLISH_CRYPTO": "BEARISH_CRYPTO", "BEARISH_CRYPTO": "BULLISH_CRYPTO",
    "INFLATION": "DISINFLATION", "DISINFLATION": "INFLATION",
}


class PredictionMarketIntelligence:
    """
    Hämtar och analyserar prediction market-odds från Polymarket.
    Körs var 6:e timme som del av L3 PREDICTIVE.

    Tre signaltyper:
    1. Pipeline signals — oddsrörelser → Supervisor
    2. Political confirmations — jämför med Political Intelligence
    3. Contrarian signals — extrema odds = kontrarian-varning
    """

    def __init__(self):
        self.snapshots: Dict[str, List[MarketSnapshot]] = {}
        self.movements: List[OddsMovement] = []
        self.last_analysis: Optional[Dict] = None
        self._load()

    def _load(self):
        """Ladda sparade movements från disk."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    data = json.load(f)
                    self.movements = [
                        OddsMovement(**m) for m in data.get("movements", [])[-200:]
                    ]
                    # Återskapa snapshots från movements
                    for m in self.movements:
                        if m.market_id not in self.snapshots:
                            self.snapshots[m.market_id] = []
                        self.snapshots[m.market_id].append(MarketSnapshot(
                            market_id=m.market_id, question=m.question,
                            category=m.category, yes_price=m.new_price,
                            no_price=round(1 - m.new_price, 4),
                            volume_24h=m.volume_24h, liquidity=0,
                            end_date="", timestamp=m.timestamp,
                        ))
            except Exception as e:
                logger.warning(f"PM data load failed: {e}")

    def _save(self):
        """Spara movements till disk."""
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({
                    "movements": [
                        {k: v for k, v in m.__dict__.items()}
                        for m in self.movements[-200:]
                    ],
                    "last_update": datetime.now().isoformat(),
                }, f, default=str, indent=2)
        except Exception as e:
            logger.warning(f"PM data save failed: {e}")

    # ================================================================
    # STEG 1: Hämta marknader från Polymarket Gamma API
    # ================================================================

    async def fetch_relevant_markets(self, max_markets: int = 30) -> List[Dict]:
        """
        Sök Polymarket Gamma API efter marknadsrelevanta marknader.
        Gamma API är helt öppet — ingen API-nyckel behövs.
        """
        markets = []
        seen_ids = set()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for term in MARKET_SEARCH_TERMS:
                try:
                    resp = await client.get(
                        f"{GAMMA_API}/markets",
                        params={
                            "tag": term,
                            "active": "true",
                            "closed": "false",
                            "limit": 5,
                            "order": "volume24hr",
                            "ascending": "false",
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list):
                            for m in data:
                                mid = m.get("conditionId") or m.get("id", "")
                                if mid and mid not in seen_ids:
                                    seen_ids.add(mid)
                                    markets.append(self._parse_market(m))

                    if len(markets) >= max_markets:
                        break

                except httpx.TimeoutException:
                    logger.debug(f"Timeout searching '{term}'")
                except Exception as e:
                    logger.debug(f"Search '{term}' failed: {e}")
                    continue

            # Hämta även top-volymmarknader
            try:
                resp = await client.get(
                    f"{GAMMA_API}/markets",
                    params={
                        "active": "true", "closed": "false",
                        "limit": 10, "order": "volume24hr", "ascending": "false",
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for m in data:
                            mid = m.get("conditionId") or m.get("id", "")
                            if mid and mid not in seen_ids:
                                seen_ids.add(mid)
                                markets.append(self._parse_market(m))
            except Exception:
                pass

        logger.info(f"📊 Fetched {len(markets)} prediction markets from Polymarket")
        return markets[:max_markets]

    def _parse_market(self, raw: Dict) -> Dict:
        """Parsa Polymarket Gamma API-svar till vårt format."""
        question = raw.get("question", raw.get("title", ""))

        # Priset är YES-tokenets pris (0-1)
        yes_price = 0.5
        try:
            prices = raw.get("outcomePrices", raw.get("bestAsk", []))
            if isinstance(prices, str):
                prices = json.loads(prices)
            if isinstance(prices, list) and len(prices) >= 1:
                yes_price = float(prices[0])
        except Exception:
            pass

        return {
            "market_id": raw.get("conditionId") or raw.get("id", ""),
            "question": question,
            "category": raw.get("category", raw.get("groupItemTitle", "")),
            "yes_price": yes_price,
            "no_price": round(1 - yes_price, 4),
            "volume_24h": float(raw.get("volume24hr", 0) or 0),
            "liquidity": float(raw.get("liquidity", 0) or 0),
            "end_date": raw.get("endDateIso", raw.get("endDate", "")),
            "description": raw.get("description", "")[:200],
            "tags": raw.get("tags", []),
            "slug": raw.get("slug", ""),
        }

    # ================================================================
    # STEG 2: Detektera oddsrörelser
    # ================================================================

    def detect_movements(self, current_markets: List[Dict]) -> List[OddsMovement]:
        """
        Jämför nya odds med sparade snapshots.
        Flagga signifikanta rörelser (NOTABLE/MAJOR/EXTREME).

        Trösklar (procentenheter):
          <3pp  = MINOR (ignorera)
          3-8pp = NOTABLE (logga, låg vikt)
          8-15pp = MAJOR (signal till Supervisor + Political Intelligence)
          >15pp = EXTREME (kritisk signal)
        """
        new_movements = []

        for market in current_markets:
            mid = market["market_id"]
            question = market["question"]
            new_price = market["yes_price"]

            # Hämta tidigare snapshot
            if mid in self.snapshots and self.snapshots[mid]:
                old_snapshot = self.snapshots[mid][0]
                old_price = old_snapshot.yes_price
                hours_diff = max(1, (
                    datetime.now() - datetime.fromisoformat(old_snapshot.timestamp)
                ).total_seconds() / 3600)
            else:
                # Första gången — spara baseline
                self.snapshots[mid] = [MarketSnapshot(
                    market_id=mid, question=question,
                    category=market.get("category", ""),
                    yes_price=new_price, no_price=round(1 - new_price, 4),
                    volume_24h=market.get("volume_24h", 0),
                    liquidity=market.get("liquidity", 0),
                    end_date=market.get("end_date", ""),
                    timestamp=datetime.now().isoformat(),
                )]
                continue

            change_pp = (new_price - old_price) * 100
            abs_change = abs(change_pp)

            if abs_change < 3:
                significance = "MINOR"
            elif abs_change < 8:
                significance = "NOTABLE"
            elif abs_change < 15:
                significance = "MAJOR"
            else:
                significance = "EXTREME"

            # Bara spara NOTABLE+
            if significance != "MINOR":
                affected, implication = self._map_to_assets(question, change_pp > 0)

                movement = OddsMovement(
                    market_id=mid, question=question,
                    category=market.get("category", ""),
                    old_price=old_price, new_price=new_price,
                    change_pp=round(change_pp, 1),
                    change_period_hours=round(hours_diff, 1),
                    direction="UP" if change_pp > 0 else "DOWN",
                    significance=significance,
                    volume_24h=market.get("volume_24h", 0),
                    timestamp=datetime.now().isoformat(),
                    affected_assets=affected,
                    market_implication=implication,
                )
                new_movements.append(movement)
                self.movements.append(movement)

                emoji = {"NOTABLE": "📋", "MAJOR": "⚡", "EXTREME": "🚨"}.get(significance, "")
                logger.info(
                    f"  {emoji} PM: '{question[:55]}...' "
                    f"{old_price:.0%}→{new_price:.0%} ({change_pp:+.1f}pp) [{significance}]"
                )

            # Uppdatera snapshot (behåll äldsta som baseline)
            self.snapshots[mid].append(MarketSnapshot(
                market_id=mid, question=question,
                category=market.get("category", ""),
                yes_price=new_price, no_price=round(1 - new_price, 4),
                volume_24h=market.get("volume_24h", 0),
                liquidity=market.get("liquidity", 0),
                end_date=market.get("end_date", ""),
                timestamp=datetime.now().isoformat(),
            ))
            # Max 48 snapshots per marknad
            if len(self.snapshots[mid]) > 48:
                self.snapshots[mid] = self.snapshots[mid][-48:]

        self._save()
        return new_movements

    def _map_to_assets(self, question: str, is_yes_rising: bool) -> Tuple[List[str], str]:
        """Mappa en prediction market-fråga till tillgångsklasser."""
        q_lower = question.lower()
        affected = []
        implications = []

        for keyword, mapping in KEYWORD_ASSET_MAP.items():
            if keyword in q_lower:
                affected.extend(mapping["assets"])
                direction = mapping["direction_if_yes"]
                if not is_yes_rising:
                    direction = DIRECTION_INVERT.get(direction, direction)
                implications.append(f"{keyword}: {direction}")

        return list(set(affected)), "; ".join(implications) if implications else "Okänd påverkan"

    # ================================================================
    # STEG 3: Generera signaler för pipeline
    # ================================================================

    def get_pipeline_signals(self) -> List[Dict]:
        """
        Returnerar signaler för Supervisor baserat på oddsrörelser.
        Bara NOTABLE+ rörelser de senaste 48 timmarna.
        """
        signals = []
        cutoff = datetime.now() - timedelta(hours=48)

        recent = [
            m for m in self.movements
            if datetime.fromisoformat(m.timestamp) > cutoff
            and m.significance in ("NOTABLE", "MAJOR", "EXTREME")
        ]

        for m in recent:
            strength = {
                "NOTABLE": "LOW", "MAJOR": "MEDIUM", "EXTREME": "HIGH",
            }.get(m.significance, "LOW")

            signals.append({
                "source": "prediction_market",
                "market_question": m.question,
                "signal": f"ODDS_{m.direction}_{m.significance}",
                "strength": strength,
                "change_pp": m.change_pp,
                "current_probability": m.new_price,
                "affected_assets": m.affected_assets,
                "implication": m.market_implication,
                "message": (
                    f"Polymarket: '{m.question[:50]}...' "
                    f"odds {m.old_price:.0%}→{m.new_price:.0%} "
                    f"({m.change_pp:+.1f}pp / {m.change_period_hours:.0f}h). "
                    f"Påverkar: {', '.join(m.affected_assets[:4])}"
                ),
            })

        return signals

    def get_political_confirmations(self) -> List[Dict]:
        """
        Jämför odds med Political Intelligence-prediktioner.
        Om båda pekar åt samma håll = stärkt signal.
        Om de divergerar = någon har fel — värdefullt i sig.
        """
        confirmations = []
        cutoff = datetime.now() - timedelta(hours=72)

        recent = [
            m for m in self.movements
            if datetime.fromisoformat(m.timestamp) > cutoff
            and m.significance in ("MAJOR", "EXTREME")
        ]

        for m in recent:
            confirmations.append({
                "market_question": m.question,
                "odds_direction": m.direction,
                "odds_probability": m.new_price,
                "change_pp": m.change_pp,
                "significance": m.significance,
                "affected_assets": m.affected_assets,
                "use_case": "COMPARE_WITH_POLITICAL_INTELLIGENCE",
            })

        return confirmations

    def get_contrarian_signals(self) -> List[Dict]:
        """
        Extrema odds = alla är överens = kontrarian-signal.

        >85%: Fullt prissatt — om det INTE sker → marknaden överraskas.
        <8%:  Helt bortprisat — om det SKER → chock.
        """
        signals = []

        for mid, snapshots in self.snapshots.items():
            if not snapshots:
                continue
            latest = snapshots[-1]
            price = latest.yes_price

            if price > 0.85:
                signals.append({
                    "type": "FULLY_PRICED",
                    "question": latest.question,
                    "probability": price,
                    "message": (
                        f"'{latest.question[:50]}...' på {price:.0%}. "
                        f"Fullt prissatt. Om det INTE sker: marknaden överraskas."
                    ),
                    "contrarian_action": "HEDGE_AGAINST_CONSENSUS",
                })

            elif price < 0.08 and latest.volume_24h > 10000:
                signals.append({
                    "type": "RISK_DISMISSED",
                    "question": latest.question,
                    "probability": price,
                    "message": (
                        f"'{latest.question[:50]}...' på bara {price:.0%}. "
                        f"Marknaden prisar bort risk helt. Om det sker: chock."
                    ),
                    "contrarian_action": "TAIL_RISK_AWARENESS",
                })

        return signals

    # ================================================================
    # HUVUDMETOD: Daglig analys (körs i L3 PREDICTIVE)
    # ================================================================

    async def run_daily_analysis(self) -> Dict:
        """
        Körs var 6:e timme i Pipeline B.
        1. Hämta 30 relevanta marknader
        2. Detektera oddsrörelser
        3. Generera tre typer av signaler
        """
        # Steg 1: Hämta marknader
        markets = await self.fetch_relevant_markets()

        # Steg 2: Detektera rörelser
        movements = self.detect_movements(markets)

        # Steg 3: Signaler
        pipeline_signals = self.get_pipeline_signals()
        political_confirms = self.get_political_confirmations()
        contrarian = self.get_contrarian_signals()

        self.last_analysis = {
            "timestamp": datetime.now().isoformat(),
            "markets_tracked": len(markets),
            "movements_detected": len(movements),
            "major_movements": [
                {
                    "question": m.question[:80],
                    "change": f"{m.old_price:.0%}→{m.new_price:.0%} ({m.change_pp:+.1f}pp)",
                    "significance": m.significance,
                    "affected": m.affected_assets[:3],
                }
                for m in movements if m.significance in ("MAJOR", "EXTREME")
            ],
            "pipeline_signals": pipeline_signals,
            "political_confirmations": political_confirms,
            "contrarian_signals": contrarian,
            "top_markets": [
                {
                    "question": m["question"][:80],
                    "probability": f"{m['yes_price']:.0%}",
                    "volume_24h": m.get("volume_24h", 0),
                }
                for m in sorted(markets, key=lambda x: x.get("volume_24h", 0), reverse=True)[:10]
            ],
        }

        logger.info(
            f"🎰 Prediction markets: {len(markets)} tracked, "
            f"{len(movements)} movements, "
            f"{len(pipeline_signals)} signals, "
            f"{len(contrarian)} contrarian"
        )

        return self.last_analysis

    def get_dashboard(self) -> Dict:
        """Hämta senaste data för dashboard-visning."""
        cutoff_48h = datetime.now() - timedelta(hours=48)
        recent = [m for m in self.movements if datetime.fromisoformat(m.timestamp) > cutoff_48h]

        return {
            "total_markets_tracked": len(self.snapshots),
            "movements_48h": len(recent),
            "major_movements_48h": [
                {
                    "question": m.question[:80],
                    "change": f"{m.old_price:.0%}→{m.new_price:.0%} ({m.change_pp:+.1f}pp)",
                    "significance": m.significance,
                    "affected_assets": m.affected_assets,
                }
                for m in recent if m.significance in ("MAJOR", "EXTREME")
            ],
            "contrarian_signals": self.get_contrarian_signals(),
            "pipeline_signals_active": len(self.get_pipeline_signals()),
            "last_analysis": self.last_analysis.get("timestamp") if self.last_analysis else None,
        }
