# ============================================================
# FIL: backend/broker_config.py (NY FIL)
# Mäklar-konfiguration: Avanza + Nordnet
# Användaren väljer mäklare -> rätt courtage och instrument
#
# Båda mäklarna har VALUTAVÄXLINGSAVGIFT 0.25% på utlandshandel
# som läggs ovanpå courtaget. Viktigt för USD-ETF:er.
# ============================================================

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("aether.broker")


@dataclass
class CourtageTier:
    """En courtageklass/prisnivå"""
    name: str
    max_order_sek: float
    fixed_fee_sek: float
    variable_pct: float
    min_fee_sek: float


@dataclass
class BrokerConfig:
    """Komplett mäklarkonfiguration"""
    name: str
    id: str
    fx_fee_pct: float
    fonder_courtage: float
    egna_fonder: List[str] = field(default_factory=list)
    courtage_tiers_se: List[CourtageTier] = field(default_factory=list)
    courtage_tiers_us: List[CourtageTier] = field(default_factory=list)
    notes: str = ""


# ============================================================
# AVANZA
# ============================================================

AVANZA = BrokerConfig(
    name="Avanza",
    id="avanza",
    fx_fee_pct=0.25,
    fonder_courtage=0.0,
    egna_fonder=[
        "Avanza Zero", "Avanza Global", "Avanza USA",
        "Avanza Europa", "Avanza Emerging Markets",
        "Avanza 75", "Avanza 50",
    ],
    courtage_tiers_se=[
        CourtageTier("Start",   50000,    0,    0.0,     0),
        CourtageTier("Mini",    15600,    0,    0.25,    1),
        CourtageTier("Small",   26000,   39,    0.15,   39),
        CourtageTier("Medium", 100000,   69,    0.069,  69),
        CourtageTier("Fast",   999999,   99,    0.0,    99),
    ],
    courtage_tiers_us=[
        CourtageTier("Mini",    15600,    0,    0.25,    1),
        CourtageTier("Small",   26000,   39,    0.15,   39),
        CourtageTier("Medium", 100000,   69,    0.069,  69),
        CourtageTier("Fast",   999999,   99,    0.0,    99),
    ],
    notes="Avanza-egna fonder (Global, USA, EM) = 0 kr courtage + 0 kr fondavgift. "
          "Bästa val för kärnpositioner. Valutaväxling 0.25% på utlandshandel.",
)


# ============================================================
# NORDNET
# ============================================================

NORDNET = BrokerConfig(
    name="Nordnet",
    id="nordnet",
    fx_fee_pct=0.25,
    fonder_courtage=0.0,
    egna_fonder=[
        "Nordnet Indexfond Sverige",
        "Nordnet Indexfond Global",
    ],
    courtage_tiers_se=[
        CourtageTier("Kom-igång", 50000,  0,    0.0,     0),
        CourtageTier("Mini",     15600,   0,    0.25,    1),
        CourtageTier("Liten",    46000,   0,    0.15,   39),
        CourtageTier("Mellan",  143478,   0,    0.069,  69),
        CourtageTier("Fast",   999999,   99,    0.0,    99),
    ],
    courtage_tiers_us=[
        CourtageTier("Mini",    15600,    0,    0.25,    9),
        CourtageTier("Liten",   46000,    0,    0.15,   49),
        CourtageTier("Mellan", 143478,    0,    0.069,  69),
        CourtageTier("Fast",   999999,   99,    0.0,    99),
    ],
    notes="Nordnet har automatisk courtageklass (behövs ej välja manuellt). "
          "Nordnet Indexfond Sverige/Global är gratis. Valutaväxling 0.25%. "
          "Private Banking (>2M): 0.05-0.055% Norden, 0.045-0.069% utland.",
)


BROKERS = {"avanza": AVANZA, "nordnet": NORDNET}


def get_broker(broker_id: str) -> BrokerConfig:
    """Hämta mäklarkonfiguration."""
    return BROKERS.get(broker_id.lower(), AVANZA)


def calculate_courtage(
    broker_id: str,
    order_value_sek: float,
    market: str = "se",
    is_fund: bool = False,
    fund_name: str = "",
) -> Dict:
    """
    Beräkna exakt courtage för en given order.
    Returns: {"courtage_sek": X, "fx_fee_sek": Y, "total_sek": Z, "tier": "..."}
    """
    broker = get_broker(broker_id)

    # Fonder = 0 kr courtage
    if is_fund:
        return {
            "courtage_sek": 0, "fx_fee_sek": 0, "total_sek": 0,
            "tier": "Fond", "broker": broker.name,
            "note": "Fonder har 0 kr courtage",
        }

    # Välj rätt tier-lista
    tiers = broker.courtage_tiers_se if market == "se" else broker.courtage_tiers_us

    # Hitta rätt tier baserat på ordersumma
    courtage = 0
    tier_name = ""
    for tier in tiers:
        if order_value_sek <= tier.max_order_sek:
            if tier.fixed_fee_sek > 0 and tier.variable_pct == 0:
                courtage = tier.fixed_fee_sek
            else:
                variable = order_value_sek * tier.variable_pct / 100
                courtage = max(tier.min_fee_sek, variable)
            tier_name = tier.name
            break

    if not tier_name:
        courtage = tiers[-1].fixed_fee_sek or tiers[-1].min_fee_sek
        tier_name = tiers[-1].name

    # Valutaväxling (bara utland)
    fx_fee = 0
    if market != "se":
        fx_fee = order_value_sek * broker.fx_fee_pct / 100

    total = courtage + fx_fee

    return {
        "courtage_sek": round(courtage, 2),
        "fx_fee_sek": round(fx_fee, 2),
        "total_sek": round(total, 2),
        "tier": tier_name,
        "broker": broker.name,
        "note": f"{tier_name}: {courtage:.0f} kr" + (f" + FX {fx_fee:.0f} kr" if fx_fee > 0 else ""),
    }


# ============================================================
# INSTRUMENT-MAPPNING PER MÄKLARE
# ============================================================

INSTRUMENT_MAP = {
    "global-equity": {
        "avanza": {"instrument": "Avanza Global", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Nordnet Indexfond Global", "ticker": None, "market": "se", "is_fund": True},
    },
    "global-equity-1": {
        "avanza": {"instrument": "Avanza Global", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Nordnet Indexfond Global", "ticker": None, "market": "se", "is_fund": True},
    },
    "global-equity-2": {
        "avanza": {"instrument": "Länsförsäkringar Global Indexnära", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Handelsbanken Global Index Criteria", "ticker": None, "market": "se", "is_fund": True},
    },
    "sp500": {
        "avanza": {"instrument": "Avanza USA", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Handelsbanken USA Index", "ticker": None, "market": "se", "is_fund": True},
    },
    "gold": {
        "avanza": {"instrument": "Xetra-Gold (4GLD)", "ticker": "4GLD.DE", "market": "eu", "is_fund": False},
        "nordnet": {"instrument": "Xetra-Gold (4GLD)", "ticker": "4GLD.DE", "market": "eu", "is_fund": False},
    },
    "gold-1": {
        "avanza": {"instrument": "Xetra-Gold (4GLD)", "ticker": "4GLD.DE", "market": "eu", "is_fund": False},
        "nordnet": {"instrument": "Xetra-Gold (4GLD)", "ticker": "4GLD.DE", "market": "eu", "is_fund": False},
    },
    "gold-2": {
        "avanza": {"instrument": "AuAg Gold Mining ETF", "ticker": None, "market": "se", "is_fund": False},
        "nordnet": {"instrument": "AuAg Gold Mining ETF", "ticker": None, "market": "se", "is_fund": False},
    },
    "kort-ranta": {
        "avanza": {"instrument": "Spiltan Räntefond Kort", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Spiltan Räntefond Kort", "ticker": None, "market": "se", "is_fund": True},
    },
    "region-em": {
        "avanza": {"instrument": "Avanza Emerging Markets", "ticker": None, "market": "se", "is_fund": True},
        "nordnet": {"instrument": "Nordnet Indexfond Tillväxtmarknader", "ticker": None, "market": "se", "is_fund": True},
    },
    "oil": {
        "avanza": {"instrument": "iShares Oil & Gas (IOGP)", "ticker": "IOGP.L", "market": "eu", "is_fund": False},
        "nordnet": {"instrument": "iShares Oil & Gas (IOGP)", "ticker": "IOGP.L", "market": "eu", "is_fund": False},
    },
    "sector-energy": {
        "avanza": {"instrument": "Energy Select SPDR (XLE)", "ticker": "XLE", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "Energy Select SPDR (XLE)", "ticker": "XLE", "market": "us", "is_fund": False},
    },
    "sector-defense": {
        "avanza": {"instrument": "VanEck Defense (DFEN)", "ticker": "DFEN", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "VanEck Defense (DFEN)", "ticker": "DFEN", "market": "us", "is_fund": False},
    },
    "btc": {
        "avanza": {"instrument": "Bitcoin Tracker One", "ticker": "BITCOIN_XBT.ST", "market": "se", "is_fund": False},
        "nordnet": {"instrument": "CoinShares Physical BTC", "ticker": "BITC.ST", "market": "se", "is_fund": False},
    },
    "silver": {
        "avanza": {"instrument": "WisdomTree Physical Silver", "ticker": "PHAG.L", "market": "eu", "is_fund": False},
        "nordnet": {"instrument": "WisdomTree Physical Silver", "ticker": "PHAG.L", "market": "eu", "is_fund": False},
    },
    "sector-tech": {
        "avanza": {"instrument": "Technology Select SPDR (XLK)", "ticker": "XLK", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "Technology Select SPDR (XLK)", "ticker": "XLK", "market": "us", "is_fund": False},
    },
    "sector-finance": {
        "avanza": {"instrument": "Financial Select SPDR (XLF)", "ticker": "XLF", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "Financial Select SPDR (XLF)", "ticker": "XLF", "market": "us", "is_fund": False},
    },
    "region-india": {
        "avanza": {"instrument": "iShares MSCI India (INDA)", "ticker": "INDA", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "iShares MSCI India (INDA)", "ticker": "INDA", "market": "us", "is_fund": False},
    },
    "us-tips": {
        "avanza": {"instrument": "iShares TIPS Bond ETF", "ticker": "TIP", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "iShares TIPS Bond ETF", "ticker": "TIP", "market": "us", "is_fund": False},
    },
    "reits": {
        "avanza": {"instrument": "iShares Global REIT ETF", "ticker": "REET", "market": "us", "is_fund": False},
        "nordnet": {"instrument": "iShares Global REIT ETF", "ticker": "REET", "market": "us", "is_fund": False},
    },
    "tail-hedge": {
        "avanza": {"instrument": "VIX-relaterat instrument", "ticker": None, "market": "us", "is_fund": False},
        "nordnet": {"instrument": "VIX-relaterat instrument", "ticker": None, "market": "us", "is_fund": False},
    },
}


def get_instrument(asset_id: str, broker_id: str) -> Dict:
    """Hämta rätt instrument för en tillgång på en specifik mäklare."""
    asset_map = INSTRUMENT_MAP.get(asset_id, {})
    broker_info = asset_map.get(broker_id)
    if not broker_info:
        other = asset_map.get("avanza") or asset_map.get("nordnet")
        if other:
            return other
    return broker_info or {"instrument": asset_id, "ticker": None, "market": "us", "is_fund": False}


def calculate_portfolio_courtage(
    broker_id: str,
    positions: List[Dict],
) -> Dict:
    """Beräkna total courtage för en hel portfölj-rebalansering."""
    total_courtage = 0
    total_fx = 0
    details = []

    for pos in positions:
        asset_id = pos.get("asset_id", "")
        value = pos.get("value_sek", 0)
        if value <= 0:
            continue

        inst = get_instrument(asset_id, broker_id)
        fee = calculate_courtage(
            broker_id=broker_id,
            order_value_sek=value,
            market=inst.get("market", "se"),
            is_fund=inst.get("is_fund", False),
        )

        total_courtage += fee["courtage_sek"]
        total_fx += fee["fx_fee_sek"]
        details.append({
            "asset": asset_id,
            "instrument": inst.get("instrument", ""),
            "value_sek": value,
            **fee,
        })

    return {
        "broker": get_broker(broker_id).name,
        "total_courtage_sek": round(total_courtage, 0),
        "total_fx_fee_sek": round(total_fx, 0),
        "total_cost_sek": round(total_courtage + total_fx, 0),
        "details": details,
    }
