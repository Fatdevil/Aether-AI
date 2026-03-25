# ============================================================
# FIL: backend/currency_hedge.py
# Beräknar valutaexponering och föreslår hedging
# Kritiskt för svensk investerare med USD-tillgångar
# ============================================================

from typing import Dict, List
from dataclasses import dataclass

# Vilken valuta varje tillgång handlas i
ASSET_CURRENCY = {
    "SP500": "USD", "ACWI": "USD", "XLF": "USD", "XLE": "USD",
    "XLK": "USD", "XLV": "USD", "ITA": "USD", "SSO": "USD",
    "QLD": "USD", "BTC": "USD", "OIL": "USD",
    "GOLD": "USD", "SILVER": "USD",
    "EEM": "USD", "VGK": "EUR", "EWJ": "JPY", "INDA": "USD",
    "EURUSD": "EUR", "US10Y": "USD",
    # Aether asset IDs
    "sp500": "USD", "global-equity": "USD", "btc": "USD",
    "gold": "USD", "silver": "USD", "oil": "USD", "us10y": "USD",
    "eurusd": "EUR",
    # Svenska tillgångar
    "SAAB_B": "SEK", "OMXS30": "SEK", "AVANZA_GLOBAL": "SEK",
    "SPILTAN_KORT": "SEK",
}

# Avanza-hedgade versioner (om tillgängliga)
HEDGED_ALTERNATIVES = {
    "SP500": {"hedged": "SPDR S&P 500 SEK-H", "unhedged": "iShares S&P 500"},
    "sp500": {"hedged": "SPDR S&P 500 SEK-H", "unhedged": "iShares S&P 500"},
    "GOLD": {"hedged": "Xetra-Gold (EUR-noterad)", "unhedged": "SPDR Gold USD"},
    "gold": {"hedged": "Xetra-Gold (EUR-noterad)", "unhedged": "SPDR Gold USD"},
}


@dataclass
class CurrencyExposure:
    currency: str
    weight_pct: float
    assets: List[str]
    risk_comment: str


class CurrencyHedgeCalculator:
    def __init__(self, fx_rates: Dict[str, float] = None):
        """
        fx_rates: {"USDSEK": 10.45, "EURSEK": 11.20, "JPYSEK": 0.068}
        """
        self.fx_rates = fx_rates or {"USDSEK": 10.45, "EURSEK": 11.20, "JPYSEK": 0.068}

    def analyze_exposure(self, portfolio_weights: Dict[str, float]) -> Dict:
        """Beräkna total valutaexponering per valuta."""
        exposures = {}

        for asset, weight in portfolio_weights.items():
            if weight <= 0:
                continue
            currency = ASSET_CURRENCY.get(asset, "USD")
            if currency not in exposures:
                exposures[currency] = {"weight": 0, "assets": []}
            exposures[currency]["weight"] += weight
            exposures[currency]["assets"].append(asset)

        result = []
        for currency, data in exposures.items():
            risk = "INGEN" if currency == "SEK" else (
                "HÖG" if data["weight"] > 40 else
                "MEDEL" if data["weight"] > 20 else "LÅG"
            )
            result.append(CurrencyExposure(
                currency=currency,
                weight_pct=round(data["weight"], 1),
                assets=data["assets"],
                risk_comment=f"{risk} valutarisk" if currency != "SEK" else "Ingen valutarisk"
            ))

        result.sort(key=lambda x: x.weight_pct, reverse=True)

        total_foreign = sum(e.weight_pct for e in result if e.currency != "SEK")

        # Hedge-rekommendation
        recommendations = []
        if total_foreign > 60:
            recommendations.append({
                "action": "KRITISKT",
                "message": f"{total_foreign:.0f}% utländsk valutaexponering. En 5% SEK-förstärkning kostar {total_foreign * 0.05:.1f}% av portföljen. Överväg valutahedgade ETFer.",
                "suggested_hedge_pct": min(total_foreign * 0.5, 40)
            })
        elif total_foreign > 40:
            recommendations.append({
                "action": "BEVAKA",
                "message": f"{total_foreign:.0f}% utländsk exponering. Hanterbart men påverkar vid stora valutarörelser.",
                "suggested_hedge_pct": total_foreign * 0.3
            })

        # USD-specifik analys
        usd_exp = sum(e.weight_pct for e in result if e.currency == "USD")
        if usd_exp > 50:
            recommendations.append({
                "action": "USD-KONCENTRATION",
                "message": f"{usd_exp:.0f}% USD-exponering. Om USD/SEK faller 10% förlorar du {usd_exp * 0.10:.1f}% av portföljvärdet.",
                "alternatives": [HEDGED_ALTERNATIVES.get(a, {}).get("hedged") for a in
                    [e.assets[0] for e in result if e.currency == "USD"] if a in HEDGED_ALTERNATIVES]
            })

        return {
            "exposures": [{"currency": e.currency, "weight_pct": e.weight_pct,
                          "assets": e.assets, "risk": e.risk_comment} for e in result],
            "total_foreign_pct": round(total_foreign, 1),
            "total_sek_pct": round(100 - total_foreign, 1),
            "recommendations": recommendations,
            "fx_impact_table": self._fx_impact(result, total_foreign)
        }

    def _fx_impact(self, exposures, total_foreign):
        """Vad händer vid olika valutascenarier?"""
        usd_exp = sum(e.weight_pct for e in exposures if e.currency == "USD")
        scenarios = [
            {"name": "SEK +5%", "impact_pct": round(-total_foreign * 0.05, 2)},
            {"name": "SEK +10%", "impact_pct": round(-total_foreign * 0.10, 2)},
            {"name": "SEK -5%", "impact_pct": round(total_foreign * 0.05, 2)},
            {"name": "SEK -10%", "impact_pct": round(total_foreign * 0.10, 2)},
            {"name": "USD-kris -15%", "impact_pct": round(-usd_exp * 0.15, 2)},
        ]
        return scenarios
