# ============================================================
# FIL: backend/predictive/causal_engine.py
# Kausal kedjeanalys: Händelse → Effekt → Sekundär → Tertiär
# Med sannolikheter, tidsramar och marknadspåverkan per länk
#
# ARKITEKTUR:
# 1. Event Detection: Identifiera triggande händelser
# 2. Chain Builder: AI bygger orsakskedjor (3-5 steg djupa)
# 3. Probability Propagation: Beräkna kumulativ sannolikhet
# 4. Market Impact: Kvantifiera påverkan per tillgång
# 5. Portfolio Action: Konkreta rekommendationer
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

CHAIN_HISTORY_FILE = "data/causal_chains.json"


class ImpactType(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SPECULATIVE = "SPECULATIVE"


@dataclass
class CausalLink:
    """En länk i en orsakskedja"""
    cause: str
    effect: str
    probability: float
    time_horizon_days: int
    impact_type: str
    magnitude: float
    confidence: str
    affected_assets: List[str]
    asset_impacts: Dict[str, float]
    reasoning: str
    reversible: bool = True
    historical_precedent: str = ""


@dataclass
class CausalChain:
    """En komplett orsakskedja från trigger till sluteffekt"""
    id: str
    trigger_event: str
    trigger_date: str
    links: List[CausalLink]
    cumulative_probability: float
    total_time_horizon_days: int
    net_portfolio_impact: Dict[str, float]
    chain_confidence: str
    status: str = "ACTIVE"
    created_at: str = ""
    invalidated_reason: str = ""


class CausalChainEngine:
    """
    Bygger och hanterar kausala orsakskedjor.

    Workflow:
    1. Mata in en händelse (t.ex. "Hormuz stängd")
    2. AI bygger kedjan steg för steg
    3. Varje steg har sannolikhet och tidsram
    4. Kumulativ sannolikhet beräknas
    5. Marknadspåverkan kvantifieras per tillgång
    6. Kedjan övervakas och uppdateras
    """

    def __init__(self):
        self.active_chains: List[CausalChain] = []
        self.archived_chains: List[CausalChain] = []
        self._load()

    def _load(self):
        raw_data = None
        try:
            from db import kv_get
            raw_data = kv_get("causal_chains")
        except Exception:
            pass
        if not raw_data and os.path.exists(CHAIN_HISTORY_FILE):
            try:
                with open(CHAIN_HISTORY_FILE, "r") as f:
                    raw_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load causal chains: {e}")
        if raw_data:
            try:
                for chain_data in raw_data.get("active", []):
                    links = [CausalLink(**l) for l in chain_data.pop("links", [])]
                    self.active_chains.append(CausalChain(**chain_data, links=links))
                for chain_data in raw_data.get("archived", []):
                    links = [CausalLink(**l) for l in chain_data.pop("links", [])]
                    self.archived_chains.append(CausalChain(**chain_data, links=links))
            except Exception as e:
                logger.error(f"Failed to parse causal chains: {e}")

    def _save(self):
        data = {
            "active": [asdict(c) for c in self.active_chains[-100:]],
            "archived": [asdict(c) for c in self.archived_chains[-200:]]
        }
        try:
            from db import kv_set
            kv_set("causal_chains", data)
        except Exception:
            os.makedirs(os.path.dirname(CHAIN_HISTORY_FILE), exist_ok=True)
            with open(CHAIN_HISTORY_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)

    def build_chain_prompt(self, event: str, context: str = "") -> str:
        """Genererar prompt för AI att bygga en kausal kedja."""
        return f"""Du är en kausal analysexpert. Givet en händelse, bygg en orsakskedja
med 3-5 steg. Varje steg måste ha sannolikhet, tidsram och marknadspåverkan.

HÄNDELSE: {event}
{"KONTEXT: " + context if context else ""}

Svara ENBART med JSON:
{{
    "trigger": "{event}",
    "chain": [
        {{
            "cause": "Beskrivning av orsak",
            "effect": "Beskrivning av effekt",
            "probability": 0.80,
            "time_days": 7,
            "impact_type": "NEGATIVE",
            "magnitude": 0.7,
            "confidence": "HIGH",
            "affected_assets": ["OIL", "SP500", "GOLD"],
            "asset_impacts": {{"OIL": 15.0, "SP500": -3.0, "GOLD": 5.0}},
            "reasoning": "Kort förklaring max 20 ord",
            "reversible": true,
            "historical_precedent": "Liknande händelse X år Y"
        }}
    ],
    "overall_conviction": "HÖG/MEDEL/LÅG",
    "time_to_clarity_days": 14
}}

REGLER:
- Sannolikheter: 0.0-1.0, realistiska (inte allt är 0.5)
- asset_impacts: i PROCENT (positiv = uppgång, negativ = nedgång)
- magnitude: 0.0-1.0 (hur stor påverkan relativt)
- Minst 3 steg i huvudkedjan
- Var SPECIFIK med tillgångar och siffror
- BARA JSON"""

    def parse_chain_response(self, response: Dict, event: str) -> CausalChain:
        """Parsar AI-svar till CausalChain-objekt"""
        chain_data = response.get("chain", [])
        links = []

        for link_data in chain_data:
            links.append(CausalLink(
                cause=link_data.get("cause", ""),
                effect=link_data.get("effect", ""),
                probability=float(link_data.get("probability", 0.5)),
                time_horizon_days=int(link_data.get("time_days", 7)),
                impact_type=link_data.get("impact_type", "UNCERTAIN"),
                magnitude=float(link_data.get("magnitude", 0.5)),
                confidence=link_data.get("confidence", "MEDIUM"),
                affected_assets=link_data.get("affected_assets", []),
                asset_impacts=link_data.get("asset_impacts", {}),
                reasoning=link_data.get("reasoning", ""),
                reversible=link_data.get("reversible", True),
                historical_precedent=link_data.get("historical_precedent", "")
            ))

        # Beräkna kumulativ sannolikhet
        cum_prob = 1.0
        for link in links:
            cum_prob *= link.probability

        # Total tidshorisont
        total_time = sum(link.time_horizon_days for link in links)

        # Netto marknadspåverkan per tillgång
        net_impact = {}
        for link in links:
            for asset, impact in link.asset_impacts.items():
                if asset not in net_impact:
                    net_impact[asset] = 0
                net_impact[asset] += impact * link.probability

        # Kedjans totala konfidens
        confidences = [link.confidence for link in links]
        if "SPECULATIVE" in confidences:
            chain_conf = "LOW"
        elif confidences.count("HIGH") >= len(confidences) * 0.6:
            chain_conf = "HIGH"
        elif confidences.count("LOW") >= len(confidences) * 0.4:
            chain_conf = "LOW"
        else:
            chain_conf = "MEDIUM"

        chain = CausalChain(
            id=f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            trigger_event=event,
            trigger_date=datetime.now().strftime("%Y-%m-%d"),
            links=links,
            cumulative_probability=round(cum_prob, 4),
            total_time_horizon_days=total_time,
            net_portfolio_impact={k: round(v, 2) for k, v in net_impact.items()},
            chain_confidence=chain_conf,
            created_at=datetime.now().isoformat()
        )

        self.active_chains.append(chain)
        self._save()
        return chain

    def get_portfolio_implications(self, min_probability: float = 0.10) -> Dict:
        """Aggregerar alla aktiva kedjors påverkan per tillgång."""
        implications = {}

        for chain in self.active_chains:
            if chain.status != "ACTIVE":
                continue
            if chain.cumulative_probability < min_probability:
                continue

            for asset, impact in chain.net_portfolio_impact.items():
                if asset not in implications:
                    implications[asset] = []
                implications[asset].append({
                    "chain_id": chain.id,
                    "trigger": chain.trigger_event,
                    "impact_pct": impact,
                    "probability": chain.cumulative_probability,
                    "time_days": chain.total_time_horizon_days,
                    "confidence": chain.chain_confidence,
                    "expected_impact": round(impact * chain.cumulative_probability, 3)
                })

        # Summera förväntad påverkan per tillgång
        summary = {}
        for asset, impacts in implications.items():
            total_expected = sum(i["expected_impact"] for i in impacts)
            bullish = [i for i in impacts if i["impact_pct"] > 0]
            bearish = [i for i in impacts if i["impact_pct"] < 0]

            summary[asset] = {
                "total_expected_impact_pct": round(total_expected, 2),
                "n_bullish_chains": len(bullish),
                "n_bearish_chains": len(bearish),
                "strongest_bullish": max(bullish, key=lambda x: x["expected_impact"]) if bullish else None,
                "strongest_bearish": min(bearish, key=lambda x: x["expected_impact"]) if bearish else None,
                "net_direction": "BULL" if total_expected > 1 else "BEAR" if total_expected < -1 else "NEUTRAL",
                "all_chains": impacts
            }

        sorted_summary = dict(sorted(
            summary.items(),
            key=lambda x: abs(x[1]["total_expected_impact_pct"]),
            reverse=True
        ))

        return {
            "as_of": datetime.now().isoformat(),
            "active_chains": len([c for c in self.active_chains if c.status == "ACTIVE"]),
            "assets": sorted_summary,
            "top_action": self._recommend_top_action(sorted_summary)
        }

    def _recommend_top_action(self, summary: Dict) -> list:
        """Rekommendation baserad på aggregerade kedjor"""
        if not summary:
            return [{"action": "HOLD", "reasoning": "Inga aktiva kedjor"}]

        most_bullish = max(summary.items(), key=lambda x: x[1]["total_expected_impact_pct"])
        most_bearish = min(summary.items(), key=lambda x: x[1]["total_expected_impact_pct"])

        actions = []
        if most_bullish[1]["total_expected_impact_pct"] > 2:
            actions.append({
                "action": "ÖKA",
                "asset": most_bullish[0],
                "expected_gain": most_bullish[1]["total_expected_impact_pct"],
                "reasoning": f"Kausala kedjor pekar på +{most_bullish[1]['total_expected_impact_pct']:.1f}% förväntad rörelse"
            })
        if most_bearish[1]["total_expected_impact_pct"] < -2:
            actions.append({
                "action": "MINSKA",
                "asset": most_bearish[0],
                "expected_loss": most_bearish[1]["total_expected_impact_pct"],
                "reasoning": f"Kausala kedjor pekar på {most_bearish[1]['total_expected_impact_pct']:.1f}% förväntad rörelse"
            })

        return actions if actions else [{"action": "HOLD", "reasoning": "Inga starka kausala signaler"}]

    def invalidate_chain(self, chain_id: str, reason: str):
        """Invalidera en kedja"""
        for chain in self.active_chains:
            if chain.id == chain_id:
                chain.status = "INVALIDATED"
                chain.invalidated_reason = reason
                self.archived_chains.append(chain)
        self.active_chains = [c for c in self.active_chains if c.id != chain_id]
        self._save()

    def confirm_chain(self, chain_id: str):
        """Bekräfta att en kedja inträdde korrekt"""
        for chain in self.active_chains:
            if chain.id == chain_id:
                chain.status = "CONFIRMED"
                self.archived_chains.append(chain)
        self.active_chains = [c for c in self.active_chains if c.id != chain_id]
        self._save()

    def expire_old_chains(self, max_age_days: int = 60):
        """Ta bort kedjor vars tidshorisont passerat"""
        now = datetime.now()
        expired = []
        remaining = []
        for chain in self.active_chains:
            created = datetime.fromisoformat(chain.created_at) if chain.created_at else now
            age = (now - created).days
            if age > chain.total_time_horizon_days + 7:
                chain.status = "EXPIRED"
                expired.append(chain)
            else:
                remaining.append(chain)
        self.archived_chains.extend(expired)
        self.active_chains = remaining
        self._save()
        return len(expired)

    def get_chain_accuracy(self) -> Dict:
        """Hur ofta har kedjorna stämt?"""
        confirmed = [c for c in self.archived_chains if c.status == "CONFIRMED"]
        invalidated = [c for c in self.archived_chains if c.status == "INVALIDATED"]
        total = len(confirmed) + len(invalidated)

        if total < 5:
            return {"status": "OTILLRÄCKLIG_DATA", "min_needed": 5, "current": total}

        accuracy = len(confirmed) / total

        conf_acc = {}
        for conf_level in ["HIGH", "MEDIUM", "LOW"]:
            conf_chains = [c for c in (confirmed + invalidated) if c.chain_confidence == conf_level]
            conf_confirmed = [c for c in conf_chains if c.status == "CONFIRMED"]
            if len(conf_chains) >= 3:
                conf_acc[conf_level] = round(len(conf_confirmed) / len(conf_chains), 3)

        return {
            "total_evaluated": total,
            "confirmed": len(confirmed),
            "invalidated": len(invalidated),
            "accuracy": round(accuracy, 3),
            "per_confidence": conf_acc,
            "is_calibrated": conf_acc.get("HIGH", 0) >= conf_acc.get("MEDIUM", 0) >= conf_acc.get("LOW", 0) if len(conf_acc) >= 2 else False
        }
