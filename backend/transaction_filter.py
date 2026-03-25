# ============================================================
# FIL: backend/transaction_filter.py
# Filtrera bort trades där courtage överstiger förväntat värde
# ============================================================

from typing import Dict, List, Tuple

# Avanza courtage (approximation)
AVANZA_FEES = {
    "SE": 0.00069,     # Svenska aktier: 0.069%
    "US": 0.0015,      # USA-aktier: 0.15%
    "ETF_SE": 0.0,     # Avanza-egna ETF:er: 0 kr
    "ETF_INT": 0.0015, # Internationella ETF:er
    "FUND": 0.0,       # Fonder: 0 kr courtage
    "DEFAULT": 0.001,  # Fallback: 0.1%
}

ASSET_FEE_MAP = {
    # Fonder
    "Avanza Global": "FUND",
    "Spiltan Räntefond Kort": "FUND",
    # Svenska aktier
    "Saab B": "SE",
    # USA-aktier
    "NVIDIA": "US",
    "Microsoft": "US",
    "Lockheed Martin": "US",
    # Internationella ETF:er
    "Xetra-Gold 4GLD": "ETF_INT",
    "iShares Oil Gas": "ETF_INT",
    "VanEck Defense": "ETF_INT",
    "WisdomTree Silver": "ETF_INT",
    "S&P 500 2x (SSO)": "ETF_INT",
    "Nasdaq 2x (QLD)": "ETF_INT",
    # ETF:er som trackas i systemet
    "Globala Aktier (ACWI)": "ETF_INT",
    "Tillväxtmarknader (EEM)": "ETF_INT",
    "Europa (VGK)": "ETF_INT",
    "Japan (EWJ)": "ETF_INT",
    "Indien (INDA)": "ETF_INT",
    "Finans (XLF)": "ETF_INT",
    "Energi (XLE)": "ETF_INT",
    "Tech (XLK)": "ETF_INT",
    "Hälsa (XLV)": "ETF_INT",
    "Försvar (ITA)": "ETF_INT",
    # Krypto
    "Bitcoin": "DEFAULT",
}


def get_fee_rate(asset_name: str) -> float:
    """Hämta courtagesats för en tillgång"""
    fee_type = ASSET_FEE_MAP.get(asset_name, "DEFAULT")
    return AVANZA_FEES.get(fee_type, AVANZA_FEES["DEFAULT"])


def filter_rebalancing(
    current_weights: Dict[str, float],
    target_weights: Dict[str, float],
    portfolio_value: float,
    min_improvement_multiplier: float = 2.0
) -> Dict[str, Dict]:
    """
    Filtrera bort trades där courtage > förväntad förbättring.
    Returns trades som ska genomföras + blockerade trades.
    """
    trades = {}

    for asset in set(list(current_weights.keys()) + list(target_weights.keys())):
        current = current_weights.get(asset, 0)
        target = target_weights.get(asset, 0)
        diff_pct = target - current

        if abs(diff_pct) < 0.5:  # Ignorera < 0.5% förändringar
            continue

        trade_value = abs(diff_pct / 100) * portfolio_value
        fee_rate = get_fee_rate(asset)
        fee_cost = trade_value * fee_rate

        # Uppskattat förbättringsvärde (förenklat: proportionellt mot viktsförskjutning)
        estimated_improvement = trade_value * 0.005  # ~0.5% förbättring

        should_trade = estimated_improvement >= fee_cost * min_improvement_multiplier

        trades[asset] = {
            "action": "KÖP" if diff_pct > 0 else "SÄLJ",
            "current_pct": round(current, 2),
            "target_pct": round(target, 2),
            "diff_pct": round(diff_pct, 2),
            "trade_value_sek": round(trade_value, 0),
            "fee_cost_sek": round(fee_cost, 2),
            "should_trade": should_trade,
            "reason": "OK" if should_trade else f"Courtage {fee_cost:.0f} kr överstiger gräns"
        }

    return trades
