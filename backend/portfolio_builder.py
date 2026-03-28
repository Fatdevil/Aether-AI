# ============================================================
# FIL: backend/portfolio_builder.py (NY FIL)
# Bygger Core-Satellite-portfölj från AI-signaler
#
# ERSÄTTER INTE portfolio_optimizer.py - arbetar OVANPÅ den.
# portfolio_optimizer.py gör fortfarande MPT-matematik.
# portfolio_builder.py bestämmer VILKA tillgångar som ska
# optimeras och i vilka proportioner.
# ============================================================

import logging
from typing import Dict, List, Optional

from portfolio_config import (
    CORE_POSITIONS, SATELLITE_CANDIDATES, CASH_CONFIG,
    MAX_ACTIVE_SATELLITES, REBALANCE_THRESHOLD_PCT,
    PORTFOLIO_TIERS, TIER_CORE_CONFIGS, TIER_SATELLITE_RULES,
    get_tier, PortfolioTier,
)

logger = logging.getLogger("aether.portfolio_builder")


class CoreSatelliteBuilder:
    """
    Bygger portfölj i tre lager:
    1. KÄRNA (60-70%): Strategiska positioner, ändras vid regimskifte
    2. SATELLIT (20-30%): Taktiska positioner, AI-styrd rotation
    3. KASSA (10-20%): Säkerhetsbuffert, ökas vid osäkerhet
    """

    def build_portfolio(
        self,
        portfolio_value: float,
        regime: str,
        final_scores: dict = None,
        consensus: dict = None,
        conviction_ratio: float = 0.7,
        convex_positions: list = None,
        trailing_stop_active: bool = False,
        broker_id: str = "avanza",
    ) -> dict:
        """
        HUVUDMETOD: Bygg portfölj anpassad till belopp + regim.

        portfolio_value: Hur mycket pengar användaren vill placera.
        Systemet väljer automatiskt rätt struktur:
          < 200k   -> 3 fonder, ingen AI-rotation
          200k-2M  -> Full Core-Satellite (5+4)
          2M-10M   -> Utökad med multi-instrument kärna
          > 10M    -> Alternativa tillgångar, tail hedge
        """
        # Steg 0: Bestäm tier
        tier = get_tier(portfolio_value)
        regime_key = self._normalize_regime(regime)

        # Map tier.mode to tier_key for config lookup
        tier_key_map = {
            "SIMPLE": "micro",
            "CORE_SATELLITE": "standard",
            "CORE_SATELLITE_PLUS": "large",
            "FULL": "institutional",
        }
        tier_key = tier_key_map.get(tier.mode, "standard")

        logger.info(f"  💼 Portfolio tier: {tier.name} ({portfolio_value:,.0f} kr) -> {tier.mode}")

        # Steg 1: KÄRNA (tier-specifik)
        core_config = TIER_CORE_CONFIGS[tier_key]

        core_alloc = []
        for pos in core_config["positions"]:
            weight = pos["regime_weights"].get(regime_key, 15)

            if trailing_stop_active:
                # Check if this is an equity-like position
                is_equity = pos["asset_id"] in ("sp500", "region-em") or "equity" in pos["asset_id"]
                is_defensive = "gold" in pos["asset_id"] or pos["asset_id"] == "kort-ranta" or pos["asset_id"] == "us-tips"
                if is_equity:
                    weight *= 0.6  # Reducera aktier 40%
                elif is_defensive:
                    weight *= 1.3  # Öka defensivt 30%

            value_sek = portfolio_value * weight / 100

            # Get broker-specific instrument if available
            instrument = pos["instrument"]
            courtage = pos["courtage"]
            try:
                from broker_config import get_instrument
                inst_info = get_instrument(pos["asset_id"], broker_id)
                if inst_info:
                    instrument = inst_info.get("instrument", instrument)
            except ImportError:
                pass

            core_alloc.append({
                "asset_id": pos["asset_id"],
                "name": pos["name"],
                "weight": round(weight, 1),
                "value_sek": round(value_sek, 0),
                "instrument": instrument,
                "courtage_pct": courtage,
                "courtage_sek": round(value_sek * courtage, 0),
                "layer": "CORE",
            })

        core_total = sum(c["weight"] for c in core_alloc)

        # Steg 2: KASSA
        cash_target = core_config["cash_regime"].get(regime_key, 15)
        if conviction_ratio < 0.5:
            cash_target = min(cash_target + 10, 45)
        if trailing_stop_active:
            cash_target = min(cash_target + 15, 50)
        cash_value = portfolio_value * cash_target / 100

        # Steg 3: SATELLIT (bara om tier tillåter)
        satellite_rules = TIER_SATELLITE_RULES[tier_key]
        satellites = []
        satellite_total = 0

        if satellite_rules["enabled"] and final_scores:
            satellite_budget = max(0, 100 - core_total - cash_target)
            satellites = self._select_satellites_tiered(
                tier_key=tier_key,
                budget_pct=satellite_budget,
                portfolio_value=portfolio_value,
                final_scores=final_scores or {},
                consensus=consensus or {},
                conviction_ratio=conviction_ratio,
                convex_positions=convex_positions or [],
                broker_id=broker_id,
            )
            satellite_total = sum(s["weight"] for s in satellites)

        actual_cash = max(5, 100 - core_total - satellite_total)

        # Steg 4: Beräkna totala courtage
        total_courtage = sum(c["courtage_sek"] for c in core_alloc)
        total_courtage += sum(s.get("courtage_sek", 0) for s in satellites)

        # Steg 5: Skatteinfo
        isk_skatt_ar = max(0, portfolio_value - 300_000) * 0.01065

        return {
            # Tier-info
            "tier": {
                "name": tier.name,
                "mode": tier.mode,
                "description": tier.description,
                "rebalance_frequency": tier.rebalance_frequency,
                "ai_depth": tier.ai_depth,
                "tax_note": tier.tax_note,
            },
            # Portfölj
            "portfolio_value": portfolio_value,
            "core": core_alloc,
            "satellites": satellites,
            "cash": {
                "weight": round(actual_cash, 1),
                "value_sek": round(portfolio_value * actual_cash / 100, 0),
                "instrument": "Spiltan Räntefond Kort / Likvida medel",
            },
            # Summering
            "core_total_pct": round(core_total, 1),
            "satellite_total_pct": round(satellite_total, 1),
            "cash_pct": round(actual_cash, 1),
            "total_positions": len(core_alloc) + len(satellites),
            "regime": regime_key,
            "conviction": conviction_ratio,
            # Kostnader
            "estimated_courtage_sek": round(total_courtage, 0),
            "isk_skatt_ar_sek": round(isk_skatt_ar, 0),
            "skattefritt_kvar_sek": max(0, 300_000 - portfolio_value),
            # Meta
            "trailing_stop_active": trailing_stop_active,
        }

    def _select_satellites_tiered(
        self, tier_key, budget_pct, portfolio_value,
        final_scores, consensus, conviction_ratio, convex_positions,
        broker_id="avanza",
    ):
        """Välj satelliter med tier-specifika regler."""
        rules = TIER_SATELLITE_RULES[tier_key]
        if not rules["enabled"]:
            return []

        candidates = []
        for sat in SATELLITE_CANDIDATES:
            if sat.asset_id not in rules["candidates"]:
                continue

            score = final_scores.get(sat.asset_id, 0)
            cons = consensus.get(sat.asset_id, {})
            cons_frac = cons.get("consensus_fraction", 0) if isinstance(cons, dict) else 0

            if abs(score) < rules["min_score"]:
                continue
            if cons_frac < rules["min_consensus"]:
                continue

            priority = abs(score) * max(cons_frac, 0.1) * conviction_ratio

            for cp in convex_positions:
                if cp.get("asset") == sat.asset_id:
                    priority *= 1.3

            base_size = budget_pct / rules["max_satellites"]
            adjusted = min(base_size * cons_frac * conviction_ratio, rules["max_single_pct"])
            adjusted = max(1.0, adjusted)
            value_sek = portfolio_value * adjusted / 100

            # Likviditetskontroll för stora portföljer
            if tier_key in ("large", "institutional") and value_sek > 500_000:
                adjusted *= 0.8
                value_sek = portfolio_value * adjusted / 100

            # Get broker-specific instrument
            instrument = sat.avanza_instrument
            courtage_pct = sat.courtage_pct
            try:
                from broker_config import get_instrument
                inst_info = get_instrument(sat.asset_id, broker_id)
                if inst_info:
                    instrument = inst_info.get("instrument", instrument)
            except ImportError:
                pass

            direction = "LONG" if score > 0 else "SHORT_SIGNAL"

            candidates.append({
                "asset_id": sat.asset_id,
                "name": sat.name,
                "weight": round(adjusted, 1),
                "value_sek": round(value_sek, 0),
                "instrument": instrument,
                "courtage_pct": courtage_pct,
                "courtage_sek": round(value_sek * courtage_pct, 0),
                "layer": "SATELLITE",
                "direction": direction,
                "score": round(score, 1),
                "consensus": round(cons_frac, 2),
                "priority": round(priority, 2),
                "reason": self._build_reason(sat, score, cons_frac, convex_positions),
            })

        # Sortera: högst prioritet först
        candidates.sort(key=lambda x: x["priority"], reverse=True)

        # Välj topp N
        selected = candidates[:rules["max_satellites"]]

        # Skala vikter så de ryms inom budget
        total_selected = sum(s["weight"] for s in selected)
        if total_selected > budget_pct and budget_pct > 0:
            scale = budget_pct / total_selected
            for s in selected:
                s["weight"] = round(s["weight"] * scale, 1)
                s["value_sek"] = round(portfolio_value * s["weight"] / 100, 0)
                s["courtage_sek"] = round(s["value_sek"] * s["courtage_pct"], 0)

        return selected

    def _build_reason(self, sat, score, consensus, convex) -> str:
        """Bygg lättläst motivering för satellitval."""
        parts = [f"Score {score:+.1f}, konsensus {consensus:.0%}"]
        if any(cp.get("asset") == sat.asset_id for cp in convex):
            parts.append("konvex position (tjänar i flertalet scenarion)")
        if "causal" in sat.triggers:
            parts.append("kausal kedja aktiv")
        if "narrative" in sat.triggers:
            parts.append("narrativ-signal")
        return ". ".join(parts)

    def _normalize_regime(self, regime: str) -> str:
        """Normalisera regim-namn till konfigurationens format."""
        r = regime.lower().strip()
        regime_map = {
            "risk_on": "risk-on", "risk-on": "risk-on",
            "leaning-risk-on": "risk-on",
            "risk_off": "risk-off", "risk-off": "risk-off",
            "leaning-risk-off": "risk-off",
            "neutral": "neutral", "transition": "neutral",
            "crisis": "crisis",
        }
        return regime_map.get(r, "neutral")

    def compare_with_current(
        self,
        new_portfolio: dict,
        current_weights: dict,
        portfolio_value: float,
    ) -> list:
        """
        Jämför ny allokering med nuvarande och generera trades.
        Filtrerar bort trades under REBALANCE_THRESHOLD_PCT.
        """
        trades = []
        new_weights = {}

        # Bygg flat weight-map från core + satellites
        for pos in new_portfolio.get("core", []):
            new_weights[pos["asset_id"]] = pos["weight"]
        for sat in new_portfolio.get("satellites", []):
            new_weights[sat["asset_id"]] = sat["weight"]
        new_weights["kassa"] = new_portfolio.get("cash_pct", 15)

        all_assets = set(list(new_weights.keys()) + list(current_weights.keys()))

        for asset in all_assets:
            current = current_weights.get(asset, 0)
            target = new_weights.get(asset, 0)
            diff = target - current

            if abs(diff) < REBALANCE_THRESHOLD_PCT:
                continue

            trade_value = abs(diff / 100) * portfolio_value
            fee_rate = 0.0015  # Default ETF courtage
            try:
                from transaction_filter import get_fee_rate
                fee_rate = get_fee_rate(asset)
            except Exception:
                pass
            fee_cost = trade_value * fee_rate

            trades.append({
                "asset": asset,
                "action": "KÖP" if diff > 0 else "SÄLJ",
                "current_pct": round(current, 1),
                "target_pct": round(target, 1),
                "diff_pct": round(diff, 1),
                "trade_value_sek": round(trade_value, 0),
                "fee_sek": round(fee_cost, 0),
                "layer": "CORE" if any(p.asset_id == asset for p in CORE_POSITIONS) else "SATELLITE",
            })

        trades.sort(key=lambda x: abs(x["diff_pct"]), reverse=True)
        return trades
