# ============================================================
# FIL: backend/tax_optimizer.py (KORRIGERAD VERSION)
# Svensk skatteoptimering 2026 — Korrekta siffror
#
# KORREKTA SIFFROR:
#   Statslåneränta 30 nov 2025: 2.55%
#   Schablonintäkt: 2.55% + 1.0% = 3.55%
#   Effektiv ISK-skatt: 3.55% * 30% = 1.065% av kapital
#   Skattefri grundnivå 2026: 300 000 kr per person
#   Breakeven vs depå: 3.55% avkastning (INTE 13.3%!)
#
# Källor: Riksgälden 28 nov 2025, Morningstar, Carnegie
# ============================================================

from typing import Dict, List, Optional
from dataclasses import dataclass

# ---- 2026 SKATTEPARAMETRAR ----
STATSLANERANTA_2026 = 0.0255
ISK_TILLAGG = 0.01
ISK_GOLV = 0.0125
ISK_SCHABLONRANTA = max(STATSLANERANTA_2026 + ISK_TILLAGG, ISK_GOLV)  # 3.55%
KAPITALSKATT = 0.30
ISK_EFFEKTIV_SKATT = ISK_SCHABLONRANTA * KAPITALSKATT  # 1.065%
SKATTEFRI_GRUNDNIVA = 300_000
DEPA_VINSTSKATT = 0.30
DEPA_UTDELNINGSSKATT = 0.30

# KF har samma schablonberäkning som ISK
KF_AVKASTNINGSSKATT = ISK_SCHABLONRANTA * KAPITALSKATT  # 1.065%
KF_HAR_SKATTEFRI_GRUNDNIVA = True  # Från 2025 gäller grundnivån även KF

# Breakeven: ISK bättre än depå när avkastning > effektiv skatt / kapitalskatt
BREAKEVEN_AVKASTNING = ISK_EFFEKTIV_SKATT / KAPITALSKATT  # 3.55%


@dataclass
class TaxResult:
    asset: str
    value: float
    recommended_account: str
    isk_tax_kr: float
    depa_tax_kr: float
    yearly_saving_kr: float
    reasoning: str


class SwedishTaxOptimizer:
    """
    Rekommenderar optimal kontoplacering per tillgång.

    REGLER 2026:
    - ISK: Schablonskatt 1.065% på kapital över 300 000 kr. Ingen skatt på vinst.
    - KF:  Samma schablon. Ingen deklaration per affär. Ingen rösträtt.
    - Depå: 30% skatt på REALISERAD vinst + utdelning. Förluster avdragsgilla.

    ISK BÄST NÄR:
    - Förväntad avkastning > 3.55% (breakeven)
    - Sparande under 300 000 kr (helt skattefritt på ISK!)
    - Långsiktigt sparande (schablon vs 30% på vinst)

    DEPÅ BÄST NÄR:
    - Förlustposition (avdrag)
    - Kort innehavstid med låg avkastning
    - Stor orealiserad vinst (flytt utlöser skatt)
    """

    def __init__(self):
        self.isk_schablon = ISK_SCHABLONRANTA
        self.isk_effektiv = ISK_EFFEKTIV_SKATT
        self.breakeven = BREAKEVEN_AVKASTNING
        self.grundniva = SKATTEFRI_GRUNDNIVA

    def analyze_portfolio(
        self,
        holdings: List[Dict],
        total_isk_value: float = 0
    ) -> Dict:
        """
        holdings: [
            {
                "asset": "Saab B",
                "value": 80000,
                "gain_pct": 45,
                "annual_return_est": 0.10,
                "dividend_yield": 0.02,
                "current_account": "ISK",
                "holding_period_months": 24
            }
        ]
        total_isk_value: Totalt ISK-värde för grundnivå-beräkning
        """
        results = []
        total_portfolio = sum(h["value"] for h in holdings)

        if total_isk_value <= 0:
            total_isk_value = total_portfolio

        # Grundnivå: första 300 000 kr är skattefritt
        skattefritt_kvar = max(0, self.grundniva)

        for holding in holdings:
            asset = holding["asset"]
            value = holding["value"]
            gain_pct = holding.get("gain_pct", 0) / 100
            annual_ret = holding.get("annual_return_est", 0.08)
            div_yield = holding.get("dividend_yield", 0.0)
            current_account = holding.get("current_account", "ISK")
            months_held = holding.get("holding_period_months", 12)
            gain_kr = value * gain_pct / (1 + gain_pct) if gain_pct != -1 else 0

            # --- ISK-SKATT ---
            if skattefritt_kvar >= value:
                isk_tax = 0
                skattefritt_kvar -= value
                isk_note = "Helt skattefritt (inom 300 000 kr grundnivå)"
            elif skattefritt_kvar > 0:
                taxable_isk = value - skattefritt_kvar
                isk_tax = taxable_isk * self.isk_effektiv
                isk_note = f"{skattefritt_kvar:.0f} kr skattefritt, {taxable_isk:.0f} kr beskattas"
                skattefritt_kvar = 0
            else:
                isk_tax = value * self.isk_effektiv
                isk_note = f"Full schablonskatt {self.isk_effektiv*100:.3f}%"

            # --- DEPÅ-SKATT ---
            depa_annual_tax = value * div_yield * DEPA_UTDELNINGSSKATT
            depa_with_gain = value * max(annual_ret, 0) * DEPA_VINSTSKATT

            # --- REKOMMENDATION ---
            if isk_tax == 0:
                best = "ISK"
                reasoning = f"Skattefritt på ISK 2026 (inom 300 000 kr grundnivå). Ingen anledning att använda depå."
                saving = depa_with_gain

            elif gain_pct < 0 and current_account == "DEPA":
                best = "DEPÅ (BEHÅLL)"
                reasoning = f"Förlust {gain_pct*100:.0f}%. Sälj på depå för skatteavdrag ({abs(gain_kr)*0.30:.0f} kr tillbaka)."
                saving = abs(gain_kr) * 0.30

            elif gain_pct > 0.5 and current_account == "DEPA":
                flytt_skatt = gain_kr * DEPA_VINSTSKATT
                yearly_diff = depa_with_gain - isk_tax
                years_to_recoup = flytt_skatt / max(yearly_diff, 1) if yearly_diff > 0 else 999
                if years_to_recoup > 5:
                    best = "DEPÅ (FLYTTA EJ)"
                    reasoning = f"Stor vinst ({gain_pct*100:.0f}%). Flytt kostar {flytt_skatt:.0f} kr i skatt. Tar {years_to_recoup:.0f} år att tjäna tillbaka. Behåll på depå."
                    saving = flytt_skatt
                else:
                    best = "ISK (FLYTTA)"
                    reasoning = f"Flytt kostar {flytt_skatt:.0f} kr men tjänst in på {years_to_recoup:.1f} år via lägre löpande skatt."
                    saving = max(0, depa_with_gain - isk_tax)

            elif annual_ret > self.breakeven:
                best = "ISK"
                reasoning = f"Förväntad avkastning {annual_ret*100:.1f}% > breakeven {self.breakeven*100:.2f}%. ISK sparar {depa_with_gain - isk_tax:.0f} kr/år."
                saving = max(0, depa_with_gain - isk_tax)

            elif annual_ret < self.breakeven and annual_ret > 0:
                best = "DEPÅ"
                reasoning = f"Förväntad avkastning {annual_ret*100:.1f}% < breakeven {self.breakeven*100:.2f}%. Depå sparar {isk_tax - depa_with_gain:.0f} kr/år."
                saving = max(0, isk_tax - depa_with_gain)

            else:
                best = "ISK"
                reasoning = "Standardval. ISK enklare att deklarera och skatteeffektivt för de flesta."
                saving = max(0, depa_with_gain - isk_tax)

            results.append(TaxResult(
                asset=asset,
                value=value,
                recommended_account=best,
                isk_tax_kr=round(isk_tax, 0),
                depa_tax_kr=round(depa_with_gain, 0),
                yearly_saving_kr=round(saving, 0),
                reasoning=reasoning
            ))

        total_isk_tax = sum(r.isk_tax_kr for r in results)
        total_depa_tax = sum(r.depa_tax_kr for r in results)
        total_saving = sum(r.yearly_saving_kr for r in results)

        return {
            "tax_year": 2026,
            "parameters": {
                "statslaneranta": f"{STATSLANERANTA_2026*100:.2f}%",
                "schablonintakt": f"{ISK_SCHABLONRANTA*100:.2f}%",
                "effektiv_isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.3f}%",
                "skattefri_grundniva": f"{SKATTEFRI_GRUNDNIVA:,.0f} kr",
                "breakeven_avkastning": f"{BREAKEVEN_AVKASTNING*100:.2f}%",
                "depa_vinstskatt": f"{DEPA_VINSTSKATT*100:.0f}%"
            },
            "recommendations": [
                {
                    "asset": r.asset,
                    "value_kr": r.value,
                    "recommended": r.recommended_account,
                    "isk_tax_kr": r.isk_tax_kr,
                    "depa_tax_kr": r.depa_tax_kr,
                    "yearly_saving_kr": r.yearly_saving_kr,
                    "reasoning": r.reasoning
                }
                for r in results
            ],
            "summary": {
                "total_portfolio_kr": total_portfolio,
                "total_isk_tax_kr": round(total_isk_tax, 0),
                "total_depa_tax_kr": round(total_depa_tax, 0),
                "total_yearly_saving_kr": round(total_saving, 0),
                "skattefritt_utnyttjat_kr": min(total_portfolio, SKATTEFRI_GRUNDNIVA),
            },
            "general_rules": [
                f"Under 300 000 kr: ISK alltid (skattefritt 2026)",
                f"Över 300 000 kr: ISK bättre om avkastning > {BREAKEVEN_AVKASTNING*100:.2f}%",
                f"Förlustpositioner: Depå (skatteavdrag vid försäljning)",
                f"Stor vinst på depå: Flytta EJ om skattekostnad tar >5 år att tjäna tillbaka",
                f"Utdelningsaktier på ISK: Utdelning beskattas INTE separat (bara schablon)",
                f"ISK-skatt betalas även vid negativ avkastning — risk!",
            ],
            "breakeven_table": [
                {"avkastning": "-5%",  "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "0% + avdrag", "bast": "DEPÅ"},
                {"avkastning": "0%",   "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "0%",    "bast": "DEPÅ"},
                {"avkastning": "2%",   "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "0.60%", "bast": "DEPÅ"},
                {"avkastning": f"{BREAKEVEN_AVKASTNING*100:.2f}%", "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "bast": "LIKA"},
                {"avkastning": "8%",   "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "2.40%", "bast": "ISK"},
                {"avkastning": "15%",  "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "4.50%", "bast": "ISK"},
                {"avkastning": "25%",  "isk_skatt": f"{ISK_EFFEKTIV_SKATT*100:.2f}%", "depa_skatt": "7.50%", "bast": "ISK"},
            ]
        }

    def quick_check(self, value: float, expected_return: float) -> str:
        """Snabbkoll: ISK eller depå?"""
        if value <= SKATTEFRI_GRUNDNIVA:
            return f"ISK (skattefritt under {SKATTEFRI_GRUNDNIVA/1000:.0f}k kr)"
        if expected_return > BREAKEVEN_AVKASTNING:
            saving = value * (expected_return * KAPITALSKATT - ISK_EFFEKTIV_SKATT)
            return f"ISK (sparar {saving:.0f} kr/år vs depå)"
        elif expected_return < 0:
            return "DEPÅ (förlust = skatteavdrag)"
        else:
            extra_cost = value * (ISK_EFFEKTIV_SKATT - expected_return * KAPITALSKATT)
            return f"DEPÅ (ISK kostar {extra_cost:.0f} kr/år mer)"
