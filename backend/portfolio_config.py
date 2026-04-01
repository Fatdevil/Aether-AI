# ============================================================
# FIL: backend/portfolio_config.py (NY FIL)
# Core-Satellite portföljkonfiguration
#
# PRINCIP: Inte alla tillgångar är lika. Några är "alltid ha"
# (kärna), några är "AI väljer" (satellit), och några är
# "säkerhetsbuffert" (kassa).
#
# VARFÖR:
# 1. Courtage-effektivitet: Kärna i 0%-fonder, satelliter större
# 2. AI fokuserar på det den är bra på (5-8 satelliter, inte 19)
# 3. Regimskifte ändrar ALLOKERING, inte INNEHAV
# 4. Trailing stop har något att reducera TILL (kassa)
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---- TILLGÅNGSKATEGORIER ----

@dataclass
class CorePosition:
    """Strategisk position - alltid i portföljen, ändras bara vid regimskifte"""
    asset_id: str
    name: str
    avanza_instrument: str       # Vad du faktiskt köper på Avanza
    courtage_pct: float          # Avanza courtage
    category: str                # "equity", "safe_haven", "cash_alt", "diversifier"
    default_weight_pct: float    # Normalvikt i portföljen
    regime_weights: Dict[str, float] = field(default_factory=dict)


@dataclass
class SatelliteCandidate:
    """Taktisk position - AI väljer om den ska vara aktiv"""
    asset_id: str
    name: str
    avanza_instrument: str
    courtage_pct: float
    category: str                # "geopolitik", "momentum", "contrarian", etc
    min_score_to_activate: float # Minimum finalScore för att aktivera
    min_consensus: float         # Minimum Tango consensus (0-1)
    max_weight_pct: float        # Max allokering
    triggers: List[str] = field(default_factory=list)


# ============================================================
# KÄRNA-POSITIONER (60-70%)
# Avanza-fonder med 0 kr courtage där möjligt
# ============================================================

CORE_POSITIONS = [
    CorePosition(
        asset_id="global-equity",
        name="Global Aktieexponering",
        avanza_instrument="Avanza Global (0 kr courtage)",
        courtage_pct=0.0,
        category="equity",
        default_weight_pct=25.0,
        regime_weights={"risk-on": 30, "neutral": 25, "risk-off": 15, "crisis": 8},
    ),
    CorePosition(
        asset_id="sp500",
        name="USA Large Cap",
        avanza_instrument="Avanza USA / iShares S&P 500",
        courtage_pct=0.0,
        category="equity",
        default_weight_pct=15.0,
        regime_weights={"risk-on": 20, "neutral": 15, "risk-off": 8, "crisis": 5},
    ),
    CorePosition(
        asset_id="gold",
        name="Guld (krisförsäkring)",
        avanza_instrument="Xetra-Gold 4GLD / Guld-ETF",
        courtage_pct=0.0015,
        category="safe_haven",
        default_weight_pct=15.0,
        regime_weights={"risk-on": 10, "neutral": 15, "risk-off": 25, "crisis": 30},
    ),
    CorePosition(
        asset_id="kort-ranta",
        name="Kort Ränta (kassaalt)",
        avanza_instrument="Spiltan Räntefond Kort (0 kr courtage)",
        courtage_pct=0.0,
        category="cash_alt",
        default_weight_pct=10.0,
        regime_weights={"risk-on": 5, "neutral": 10, "risk-off": 20, "crisis": 25},
    ),
    CorePosition(
        asset_id="region-em",
        name="Tillväxtmarknader",
        avanza_instrument="Avanza Emerging Markets (0 kr courtage)",
        courtage_pct=0.0,
        category="diversifier",
        default_weight_pct=5.0,
        regime_weights={"risk-on": 8, "neutral": 5, "risk-off": 2, "crisis": 2},
    ),
]


# ============================================================
# SATELLIT-KANDIDATER (20-30%)
# AI väljer 3-5 av dessa baserat på signaler
# ============================================================

SATELLITE_CANDIDATES = [
    SatelliteCandidate(
        asset_id="oil",
        name="Råolja / Energi",
        avanza_instrument="iShares Oil & Gas (IOGP) / Brent-ETF",
        courtage_pct=0.0015,
        category="geopolitik",
        min_score_to_activate=3.0,
        min_consensus=0.6,
        max_weight_pct=10.0,
        triggers=["causal", "narrative", "actor_sim"],
    ),
    SatelliteCandidate(
        asset_id="sector-energy",
        name="Energisektor (XLE)",
        avanza_instrument="Energy Select SPDR (XLE)",
        courtage_pct=0.0015,
        category="sektor_rotation",
        min_score_to_activate=2.5,
        min_consensus=0.5,
        max_weight_pct=8.0,
        triggers=["causal", "lead_lag"],
    ),
    SatelliteCandidate(
        asset_id="sector-defense",
        name="Försvar (ITA/DFEN)",
        avanza_instrument="VanEck Defense / iShares US Aerospace",
        courtage_pct=0.0015,
        category="geopolitik",
        min_score_to_activate=2.0,
        min_consensus=0.4,
        max_weight_pct=8.0,
        triggers=["causal", "narrative"],
    ),
    SatelliteCandidate(
        asset_id="btc",
        name="Bitcoin",
        avanza_instrument="Bitcoin Tracker One (Avanza) / BTC-ETN",
        courtage_pct=0.0015,
        category="momentum",
        min_score_to_activate=4.0,
        min_consensus=0.7,
        max_weight_pct=7.0,
        triggers=["lead_lag", "narrative", "convexity"],
    ),
    SatelliteCandidate(
        asset_id="silver",
        name="Silver",
        avanza_instrument="WisdomTree Physical Silver",
        courtage_pct=0.0015,
        category="safe_haven_satellite",
        min_score_to_activate=2.5,
        min_consensus=0.5,
        max_weight_pct=6.0,
        triggers=["lead_lag"],
    ),
    SatelliteCandidate(
        asset_id="sector-tech",
        name="Tech (XLK)",
        avanza_instrument="Technology Select SPDR (XLK)",
        courtage_pct=0.0015,
        category="sektor_rotation",
        min_score_to_activate=3.0,
        min_consensus=0.6,
        max_weight_pct=10.0,
        triggers=["lead_lag", "narrative"],
    ),
    SatelliteCandidate(
        asset_id="sector-finance",
        name="Finans (XLF)",
        avanza_instrument="Financial Select SPDR (XLF)",
        courtage_pct=0.0015,
        category="sektor_rotation",
        min_score_to_activate=2.5,
        min_consensus=0.5,
        max_weight_pct=7.0,
        triggers=["lead_lag", "causal"],
    ),
    SatelliteCandidate(
        asset_id="region-india",
        name="Indien (INDA)",
        avanza_instrument="iShares MSCI India",
        courtage_pct=0.0015,
        category="tillvaxt",
        min_score_to_activate=3.0,
        min_consensus=0.5,
        max_weight_pct=5.0,
        triggers=["narrative", "lead_lag"],
    ),
]


# ============================================================
# KASSA-LAGER (10-20%)
# ============================================================

CASH_CONFIG = {
    "instrument": "Spiltan Räntefond Kort / Likvida medel",
    "courtage_pct": 0.0,
    "min_pct": 10.0,
    "max_pct": 40.0,
    "regime_targets": {
        "risk-on": 10.0,
        "neutral": 15.0,
        "risk-off": 25.0,
        "crisis": 40.0,
    },
}

MAX_ACTIVE_SATELLITES = 4
REBALANCE_THRESHOLD_PCT = 3.0


# ============================================================
# TURBO: BORTTAGET som default.
# ============================================================
TURBO_ENABLED = False
TURBO_MAX_PCT = 5.0
TURBO_REQUIREMENTS = {
    "min_consensus": 1.0,
    "max_vix": 18.0,
    "min_confirmation_days": 3,
}


# ============================================================
# TIER-SYSTEM: Rätt portfölj baserat på belopp
# ============================================================

@dataclass
class PortfolioTier:
    """Konfiguration per portföljstorlek"""
    name: str
    min_value: float
    max_value: float
    mode: str                    # SIMPLE / CORE_SATELLITE / CORE_SATELLITE_PLUS / FULL
    description: str
    max_positions: int
    satellite_enabled: bool
    max_satellites: int
    rebalance_frequency: str     # quarterly / monthly / bi_weekly / weekly
    multi_instrument_core: bool
    alternatives_enabled: bool
    tail_hedge_enabled: bool
    liquidity_check: bool
    min_trade_value_sek: float
    ai_depth: str                # "minimal" / "standard" / "deep"
    tax_note: str


PORTFOLIO_TIERS = {
    "micro": PortfolioTier(
        name="Mikro",
        min_value=0,
        max_value=200_000,
        mode="SIMPLE",
        description="Förenklad portfölj. 3 fonder, kvartalsvis rebalansering. AI används bara för regimdetektering.",
        max_positions=3,
        satellite_enabled=False,
        max_satellites=0,
        rebalance_frequency="quarterly",
        multi_instrument_core=False,
        alternatives_enabled=False,
        tail_hedge_enabled=False,
        liquidity_check=False,
        min_trade_value_sek=5000,
        ai_depth="minimal",
        tax_note="Helt skattefritt på ISK (under 300 000 kr grundnivå 2026).",
    ),
    "standard": PortfolioTier(
        name="Standard",
        min_value=200_000,
        max_value=2_000_000,
        mode="CORE_SATELLITE",
        description="Full Core-Satellite. 5 kärnpositioner + 3-4 AI-styrda satelliter. Månadsvis rebalansering.",
        max_positions=9,
        satellite_enabled=True,
        max_satellites=4,
        rebalance_frequency="monthly",
        multi_instrument_core=False,
        alternatives_enabled=False,
        tail_hedge_enabled=False,
        liquidity_check=False,
        min_trade_value_sek=3000,
        ai_depth="standard",
        tax_note="ISK för allt. Delvis skattefritt (300k grundnivå). Effektiv skatt 1.065% på överstigande.",
    ),
    "large": PortfolioTier(
        name="Stor",
        min_value=2_000_000,
        max_value=10_000_000,
        mode="CORE_SATELLITE_PLUS",
        description="Utökad Core-Satellite. Kärna delad över flera instrument. Fler satelliter. Varannan-vecka rebalansering.",
        max_positions=14,
        satellite_enabled=True,
        max_satellites=6,
        rebalance_frequency="bi_weekly",
        multi_instrument_core=True,
        alternatives_enabled=False,
        tail_hedge_enabled=True,
        liquidity_check=True,
        min_trade_value_sek=10000,
        ai_depth="deep",
        tax_note="ISK + överväg KF för del av kapitalet. ISK-skatt ~21 300 kr/år per miljon.",
    ),
    "institutional": PortfolioTier(
        name="Institutionell",
        min_value=10_000_000,
        max_value=float("inf"),
        mode="FULL",
        description="Full plattform. Alternativa tillgångar, tail hedge, likviditetskontroll, multi-instrument kärna.",
        max_positions=20,
        satellite_enabled=True,
        max_satellites=8,
        rebalance_frequency="weekly",
        multi_instrument_core=True,
        alternatives_enabled=True,
        tail_hedge_enabled=True,
        liquidity_check=True,
        min_trade_value_sek=25000,
        ai_depth="deep",
        tax_note="ISK + KF + Depå mix. Överväg holdingbolag för skatteeffektivitet.",
    ),
}


def get_tier(portfolio_value: float) -> PortfolioTier:
    """Returnera rätt tier baserat på portföljvärde."""
    for tier_id, tier in PORTFOLIO_TIERS.items():
        if tier.min_value <= portfolio_value < tier.max_value:
            return tier
    return PORTFOLIO_TIERS["standard"]


# ============================================================
# TIER-SPECIFIKA KÄRN-KONFIGURATIONER
# ============================================================

TIER_CORE_CONFIGS = {
    "micro": {
        "positions": [
            {"asset_id": "global-equity", "name": "Global Aktie",
             "instrument": "Avanza Global", "courtage": 0.0,
             "regime_weights": {"risk-on": 55, "neutral": 45, "risk-off": 25, "crisis": 15}},
            {"asset_id": "gold", "name": "Guld",
             "instrument": "Xetra-Gold 4GLD", "courtage": 0.0015,
             "regime_weights": {"risk-on": 10, "neutral": 15, "risk-off": 30, "crisis": 35}},
            {"asset_id": "kort-ranta", "name": "Kort Ränta",
             "instrument": "Spiltan Räntefond Kort", "courtage": 0.0,
             "regime_weights": {"risk-on": 15, "neutral": 20, "risk-off": 30, "crisis": 40}},
        ],
        "cash_regime": {"risk-on": 10, "neutral": 15, "risk-off": 15, "crisis": 10},
    },
    "standard": {
        "positions": [
            {"asset_id": "global-equity", "name": "Global Aktie",
             "instrument": "Avanza Global", "courtage": 0.0,
             "regime_weights": {"risk-on": 30, "neutral": 25, "risk-off": 15, "crisis": 8}},
            {"asset_id": "sp500", "name": "USA Large Cap",
             "instrument": "Avanza USA", "courtage": 0.0,
             "regime_weights": {"risk-on": 20, "neutral": 15, "risk-off": 8, "crisis": 5}},
            {"asset_id": "gold", "name": "Guld",
             "instrument": "Xetra-Gold 4GLD", "courtage": 0.0015,
             "regime_weights": {"risk-on": 10, "neutral": 15, "risk-off": 25, "crisis": 30}},
            {"asset_id": "kort-ranta", "name": "Kort Ränta",
             "instrument": "Spiltan Räntefond Kort", "courtage": 0.0,
             "regime_weights": {"risk-on": 5, "neutral": 10, "risk-off": 20, "crisis": 25}},
            {"asset_id": "region-em", "name": "Tillväxtmarknader",
             "instrument": "Avanza Emerging Markets", "courtage": 0.0,
             "regime_weights": {"risk-on": 8, "neutral": 5, "risk-off": 2, "crisis": 2}},
        ],
        "cash_regime": {"risk-on": 10, "neutral": 15, "risk-off": 25, "crisis": 40},
    },
    "large": {
        "positions": [
            {"asset_id": "global-equity-1", "name": "Global Aktie (Avanza)",
             "instrument": "Avanza Global", "courtage": 0.0,
             "regime_weights": {"risk-on": 18, "neutral": 15, "risk-off": 8, "crisis": 5}},
            {"asset_id": "global-equity-2", "name": "Global Aktie (Länsförsäkringar)",
             "instrument": "Länsförsäkringar Global Indexnära", "courtage": 0.0,
             "regime_weights": {"risk-on": 12, "neutral": 10, "risk-off": 5, "crisis": 3}},
            {"asset_id": "sp500", "name": "USA Large Cap",
             "instrument": "Avanza USA", "courtage": 0.0,
             "regime_weights": {"risk-on": 15, "neutral": 12, "risk-off": 6, "crisis": 4}},
            {"asset_id": "gold-1", "name": "Guld (ETF)",
             "instrument": "Xetra-Gold 4GLD", "courtage": 0.0015,
             "regime_weights": {"risk-on": 5, "neutral": 8, "risk-off": 15, "crisis": 18}},
            {"asset_id": "gold-2", "name": "Guld (Fond)",
             "instrument": "AuAg Gold Mining ETF", "courtage": 0.0015,
             "regime_weights": {"risk-on": 3, "neutral": 5, "risk-off": 8, "crisis": 10}},
            {"asset_id": "kort-ranta", "name": "Kort Ränta",
             "instrument": "Spiltan Räntefond Kort", "courtage": 0.0,
             "regime_weights": {"risk-on": 3, "neutral": 8, "risk-off": 15, "crisis": 20}},
            {"asset_id": "region-em", "name": "Tillväxtmarknader",
             "instrument": "Avanza Emerging Markets", "courtage": 0.0,
             "regime_weights": {"risk-on": 7, "neutral": 5, "risk-off": 2, "crisis": 1}},
            {"asset_id": "us-tips", "name": "Inflationsskydd (TIPS)",
             "instrument": "iShares TIPS Bond ETF", "courtage": 0.0015,
             "regime_weights": {"risk-on": 2, "neutral": 4, "risk-off": 8, "crisis": 6}},
        ],
        "cash_regime": {"risk-on": 8, "neutral": 12, "risk-off": 20, "crisis": 30},
    },
    "institutional": {
        "positions": [
            {"asset_id": "global-equity-1", "name": "Global Aktie (Avanza)",
             "instrument": "Avanza Global", "courtage": 0.0,
             "regime_weights": {"risk-on": 15, "neutral": 12, "risk-off": 6, "crisis": 4}},
            {"asset_id": "global-equity-2", "name": "Global Aktie (Länsförsäkringar)",
             "instrument": "Länsförsäkringar Global Indexnära", "courtage": 0.0,
             "regime_weights": {"risk-on": 10, "neutral": 8, "risk-off": 4, "crisis": 2}},
            {"asset_id": "sp500", "name": "USA Large Cap",
             "instrument": "Avanza USA", "courtage": 0.0,
             "regime_weights": {"risk-on": 12, "neutral": 10, "risk-off": 5, "crisis": 3}},
            {"asset_id": "gold-1", "name": "Guld (ETF)",
             "instrument": "Xetra-Gold 4GLD", "courtage": 0.0015,
             "regime_weights": {"risk-on": 4, "neutral": 6, "risk-off": 12, "crisis": 15}},
            {"asset_id": "gold-2", "name": "Guld (Fond/Mining)",
             "instrument": "AuAg Gold Mining ETF", "courtage": 0.0015,
             "regime_weights": {"risk-on": 2, "neutral": 4, "risk-off": 6, "crisis": 8}},
            {"asset_id": "kort-ranta", "name": "Kort Ränta",
             "instrument": "Spiltan Räntefond Kort", "courtage": 0.0,
             "regime_weights": {"risk-on": 2, "neutral": 5, "risk-off": 10, "crisis": 15}},
            {"asset_id": "region-em", "name": "Tillväxtmarknader",
             "instrument": "Avanza Emerging Markets", "courtage": 0.0,
             "regime_weights": {"risk-on": 6, "neutral": 4, "risk-off": 2, "crisis": 1}},
            {"asset_id": "us-tips", "name": "Inflationsskydd (TIPS)",
             "instrument": "iShares TIPS Bond ETF", "courtage": 0.0015,
             "regime_weights": {"risk-on": 2, "neutral": 3, "risk-off": 6, "crisis": 5}},
            {"asset_id": "reits", "name": "Fastigheter (REITs)",
             "instrument": "iShares Global REIT ETF", "courtage": 0.0015,
             "regime_weights": {"risk-on": 5, "neutral": 4, "risk-off": 2, "crisis": 1}},
            {"asset_id": "tail-hedge", "name": "Tail Risk Hedge",
             "instrument": "VIX-relaterat instrument / optioner",
             "courtage": 0.005,
             "regime_weights": {"risk-on": 1, "neutral": 2, "risk-off": 4, "crisis": 5}},
        ],
        "cash_regime": {"risk-on": 6, "neutral": 10, "risk-off": 18, "crisis": 25},
    },
}


# ============================================================
# TIER-SPECIFIKA SATELLIT-REGLER
# ============================================================

TIER_SATELLITE_RULES = {
    "micro": {
        "enabled": False,
        "max_satellites": 0,
        "max_single_pct": 0,
        "min_score": 0,
        "min_consensus": 0,
        "candidates": [],
        "note": "Inga satelliter under 200k. Kärna räcker.",
    },
    "standard": {
        "enabled": True,
        "max_satellites": 4,
        "max_single_pct": 10,
        "min_score": 3.0,
        "min_consensus": 0.6,
        "candidates": ["oil", "sector-energy", "sector-defense", "btc",
                       "silver", "sector-tech", "sector-finance", "region-india"],
    },
    "large": {
        "enabled": True,
        "max_satellites": 6,
        "max_single_pct": 8,
        "min_score": 2.5,
        "min_consensus": 0.5,
        "candidates": ["oil", "sector-energy", "sector-defense", "btc", "silver",
                       "sector-tech", "sector-finance", "region-india",
                       "sector-health", "region-europe", "region-japan"],
    },
    "institutional": {
        "enabled": True,
        "max_satellites": 8,
        "max_single_pct": 6,
        "min_score": 2.0,
        "min_consensus": 0.4,
        "candidates": ["oil", "sector-energy", "sector-defense", "btc", "silver",
                       "sector-tech", "sector-finance", "region-india",
                       "sector-health", "region-europe", "region-japan",
                       "eurusd", "us10y"],
    },
}


# ============================================================
# Constant Maps shifted from MPT layer (portfolio_optimizer)
# ============================================================

ASSET_TICKER_MAP = {
    'btc': 'BTC-USD', 'gold': 'GC=F', 'silver': 'SI=F', 'oil': 'BZ=F',
    'sp500': '^GSPC', 'global-equity': 'ACWI', 'eurusd': 'EURUSD=X', 'us10y': '^TNX',
    'sector-finance': 'XLF', 'sector-energy': 'XLE', 'sector-tech': 'XLK',
    'sector-health': 'XLV', 'sector-defense': 'ITA', 'region-em': 'EEM',
    'region-europe': 'VGK', 'region-japan': 'EWJ', 'region-india': 'INDA',
    'leveraged-sp500': 'SSO', 'leveraged-nasdaq': 'QLD'
}

ASSET_NAMES = {
    'btc': 'Bitcoin', 'gold': 'Guld (XAU)', 'silver': 'Silver (XAG)', 'oil': 'Råolja (Brent)',
    'sp500': 'S&P 500', 'global-equity': 'Globala Aktier (ACWI)', 'eurusd': 'EUR/USD', 'us10y': 'US 10Y Räntor',
    'sector-finance': 'Finans (XLF)', 'sector-energy': 'Energi (XLE)', 'sector-tech': 'Tech (XLK)',
    'sector-health': 'Hälsa (XLV)', 'sector-defense': 'Försvar (ITA)', 'region-em': 'Tillväxtmarknader (EEM)',
    'region-europe': 'Europa (VGK)', 'region-japan': 'Japan (EWJ)', 'region-india': 'Indien (INDA)',
    'leveraged-sp500': 'S&P 500 2x (SSO)', 'leveraged-nasdaq': 'Nasdaq 2x (QLD)'
}

ASSET_COLORS = {
    'btc': '#f7931a', 'global-equity': '#4facfe', 'sp500': '#6c5ce7',
    'gold': '#ffd700', 'silver': '#c0c0c0', 'eurusd': '#00f2fe',
    'oil': '#636e72', 'us10y': '#9d4edd',
    'sector-finance': '#2ecc71', 'sector-energy': '#e67e22',
    'sector-tech': '#3498db', 'sector-health': '#e74c3c',
    'sector-defense': '#95a5a6',
    'region-em': '#e84393', 'region-europe': '#0984e3',
    'region-japan': '#fd79a8', 'region-india': '#00cec9',
    'leveraged-sp500': '#ff6b6b', 'leveraged-nasdaq': '#ffa502'
}
