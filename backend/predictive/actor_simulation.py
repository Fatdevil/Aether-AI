# ============================================================
# FIL: backend/predictive/actor_simulation.py
# 10 marknadsarketyper som reagerar på händelser
# och vars INTERAKTION avslöjar panikdynamik och stödnivåer
# ============================================================

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
import logging

logger = logging.getLogger(__name__)

SIMULATION_FILE = "data/actor_simulations.json"

MARKET_ARCHETYPES = [
    {
        "id": "central_bank",
        "name": "Centralbanker (Fed/ECB/Riksbanken)",
        "risk_appetite": 1,
        "time_horizon": "12-36 månader",
        "primary_concern": "Inflation, finansiell stabilitet, sysselsättning",
        "reaction_to_crisis": "Först avvaktande, sedan kraftfull. Laggar alltid 2-8 veckor.",
        "herd_tendency": 0.2,
    },
    {
        "id": "pension_fund",
        "name": "Pensionsfonder (AP-fonder, Vanguard)",
        "risk_appetite": 3,
        "time_horizon": "5-20 år",
        "primary_concern": "Långsiktig real avkastning, ALM-matchning",
        "reaction_to_crisis": "Extremt långsamma. Rebalanserar TILL aktier vid krascher.",
        "herd_tendency": 0.1,
    },
    {
        "id": "hedge_fund",
        "name": "Hedgefonder (Bridgewater, Citadel)",
        "risk_appetite": 8,
        "time_horizon": "1 dag - 6 månader",
        "primary_concern": "Alpha, Sharpe, absolut avkastning",
        "reaction_to_crisis": "Snabba. Kan vara kontrarianer ELLER förstärkare.",
        "herd_tendency": 0.4,
    },
    {
        "id": "retail_sweden",
        "name": "Svenska småsparare (Avanza/Nordnet)",
        "risk_appetite": 5,
        "time_horizon": "1 månad - 5 år",
        "primary_concern": "Kursutveckling, nyhetsrubriker, ISK-sparande",
        "reaction_to_crisis": "Först förnekar, sedan paniksäljer 2-4 veckor för sent.",
        "herd_tendency": 0.8,
    },
    {
        "id": "oil_trader",
        "name": "Energitraders / Oljemarknad",
        "risk_appetite": 7,
        "time_horizon": "1 dag - 3 månader",
        "primary_concern": "Utbud/efterfrågan, lager, Hormuz, OPEC",
        "reaction_to_crisis": "OMEDELBAR. Geopolitisk risk prissätts inom timmar.",
        "herd_tendency": 0.5,
    },
    {
        "id": "gold_bug",
        "name": "Guldköpare / Safe haven",
        "risk_appetite": 3,
        "time_horizon": "6 månader - 10 år",
        "primary_concern": "Inflation, valutaförsvagning, systemrisk",
        "reaction_to_crisis": "Köper OMEDELBART vid oro. Skapar initial prisrush.",
        "herd_tendency": 0.6,
    },
    {
        "id": "quant_algo",
        "name": "Kvantitativa/Algoritmiska traders",
        "risk_appetite": 6,
        "time_horizon": "Millisekunder - 1 månad",
        "primary_concern": "Statistiska anomalier, momentum, mean-reversion",
        "reaction_to_crisis": "OMEDELBAR men MEKANISK. Kan förstärka nedgångar via stop-losses.",
        "herd_tendency": 0.3,
    },
    {
        "id": "corporate_treasury",
        "name": "Företags-treasuries (Volvo, Ericsson)",
        "risk_appetite": 2,
        "time_horizon": "3-12 månader",
        "primary_concern": "Valutaexponering, riskhantering, kassa",
        "reaction_to_crisis": "Ökar hedging, drar in kreditlinjer, minskar capex",
        "herd_tendency": 0.3,
    },
    {
        "id": "geopolitical_analyst",
        "name": "Geopolitiska analytiker",
        "risk_appetite": 4,
        "time_horizon": "1-12 månader",
        "primary_concern": "Konflikteskalering, sanktioner, regimförändringar",
        "reaction_to_crisis": "Framförhållning: ser signaler 1-4 veckor före marknaden",
        "herd_tendency": 0.3,
    },
    {
        "id": "etf_flows",
        "name": "ETF-flöden / Passiva investerare",
        "risk_appetite": 5,
        "time_horizon": "Kontinuerligt (monthly savings)",
        "primary_concern": "Indexreplikering, tracking error",
        "reaction_to_crisis": "Vecka 1: fortsätter köpa. Vecka 2-4: outflows.",
        "herd_tendency": 0.9,
    },
]


@dataclass
class ActorReaction:
    actor_id: str
    actor_name: str
    reaction: str
    action: str
    intensity: float
    timing: str
    affected_assets: List[str]
    asset_impacts: Dict[str, float]
    second_order: str
    confidence: float


@dataclass
class InteractionEffect:
    trigger_actor: str
    affected_actor: str
    effect: str
    amplifies_or_dampens: str
    magnitude: float


@dataclass
class SimulationResult:
    id: str
    event: str
    timestamp: str
    reactions: List[ActorReaction]
    interactions: List[InteractionEffect]
    consensus_direction: str
    panic_risk: float
    support_level_assets: Dict[str, str]
    tipping_point: str
    net_asset_impact: Dict[str, float]
    key_insight: str


class MarketActorSimulation:
    def __init__(self):
        self.archetypes = MARKET_ARCHETYPES
        self.simulations: List[SimulationResult] = []
        self._load()

    def _load(self):
        """Load previous simulations from PostgreSQL KV store."""
        try:
            from db import kv_get
            data = kv_get("actor_simulations")
            if data:
                self.simulations = [SimulationResult(**s) for s in data[-50:]]
                logger.info(f"📦 Loaded {len(self.simulations)} actor simulations from DB")
                return
        except Exception as e:
            logger.warning(f"⚠️ KV load actor_simulations failed: {e}")
        # Fallback to file
        if os.path.exists(SIMULATION_FILE):
            try:
                with open(SIMULATION_FILE, "r") as f:
                    data = json.load(f)
                    self.simulations = [SimulationResult(**s) for s in data[-50:]]
                    logger.info(f"📁 Loaded {len(self.simulations)} actor simulations from file (fallback)")
            except Exception as e:
                logger.error(f"Failed to load actor simulations: {e}")

    def build_simulation_prompt(self, event: str, context: str = "") -> str:
        actor_descriptions = ""
        for a in self.archetypes:
            actor_descriptions += f"\n{a['name']} (risk: {a['risk_appetite']}/10, horisont: {a['time_horizon']})\n"
            actor_descriptions += f"  Fokus: {a['primary_concern']}\n"
            actor_descriptions += f"  Krisreaktion: {a['reaction_to_crisis']}\n"
            actor_descriptions += f"  Flocktendens: {a['herd_tendency']}/1.0\n"

        return f"""Du är en marknads-simulator. Simulera hur 10 olika marknadsaktörer
reagerar på en händelse, och hur deras reaktioner PÅVERKAR VARANDRA.

HÄNDELSE: {event}
{f"KONTEXT: {context}" if context else ""}

AKTÖRER:
{actor_descriptions}

Svara ENBART med JSON:
{{
    "reactions": [
        {{
            "actor_id": "central_bank",
            "actor_name": "Centralbanker",
            "reaction": "max 25 ord om deras sannolika reaktion",
            "action": "AVVAKTA|KÖP|SÄLJ|HEDGE|INTERVENE",
            "intensity": 5,
            "timing": "OMEDELBART|DAGAR|VECKOR|MÅNADER",
            "affected_assets": ["SP500", "US10Y", "GOLD"],
            "asset_impacts": {{"SP500": -2, "US10Y": 0.5, "GOLD": 3}},
            "second_order": "max 20 ord om hur ANDRA reagerar",
            "confidence": 0.7
        }}
    ],
    "interactions": [
        {{
            "trigger_actor": "retail_sweden",
            "affected_actor": "hedge_fund",
            "effect": "Retail paniksäljer → hedgefonder köper dippen",
            "amplifies_or_dampens": "DAMPENS",
            "magnitude": 0.6
        }}
    ],
    "consensus": {{
        "direction": "BULL|BEAR|SPLIT",
        "agreement_score": 0.4
    }},
    "panic_dynamics": {{
        "panic_risk": 0.3,
        "panic_trigger": "Vad som utlöser panik max 20 ord",
        "panic_dampener": "Vad som förhindrar panik max 20 ord"
    }},
    "support_levels": {{"SP500": "6200 (pensionsfonder rebalanserar in)"}},
    "tipping_point": "max 30 ord om när sentimentet vänder",
    "net_impact": {{"SP500": -3, "GOLD": 8, "OIL": 15, "BTC": -5}},
    "key_insight": "max 30 ord - viktigaste insikten",
    "timeline": [
        {{"period": "Dag 1-3", "dominant_actor": "oil_trader", "market_mood": "CHOCK"}}
    ]
}}

REGLER:
- Simulera ALLA 10 aktörer
- asset_impacts i PROCENT
- Minst 5 interaktionspar
- Var REALISTISK
- BARA JSON"""

    def parse_simulation(self, ai_response: Dict, event: str) -> SimulationResult:
        reactions = []
        for r in ai_response.get("reactions", []):
            reactions.append(ActorReaction(
                actor_id=r.get("actor_id", ""),
                actor_name=r.get("actor_name", ""),
                reaction=r.get("reaction", ""),
                action=r.get("action", "AVVAKTA"),
                intensity=float(r.get("intensity", 5)),
                timing=r.get("timing", "DAGAR"),
                affected_assets=r.get("affected_assets", []),
                asset_impacts=r.get("asset_impacts", {}),
                second_order=r.get("second_order", ""),
                confidence=float(r.get("confidence", 0.5))
            ))

        interactions = []
        for i in ai_response.get("interactions", []):
            interactions.append(InteractionEffect(
                trigger_actor=i.get("trigger_actor", ""),
                affected_actor=i.get("affected_actor", ""),
                effect=i.get("effect", ""),
                amplifies_or_dampens=i.get("amplifies_or_dampens", "DAMPENS"),
                magnitude=float(i.get("magnitude", 0.5))
            ))

        consensus = ai_response.get("consensus", {})
        panic = ai_response.get("panic_dynamics", {})

        result = SimulationResult(
            id=f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            event=event,
            timestamp=datetime.now().isoformat(),
            reactions=reactions,
            interactions=interactions,
            consensus_direction=consensus.get("direction", "SPLIT"),
            panic_risk=float(panic.get("panic_risk", 0.3)),
            support_level_assets=ai_response.get("support_levels", {}),
            tipping_point=ai_response.get("tipping_point", ""),
            net_asset_impact=ai_response.get("net_impact", {}),
            key_insight=ai_response.get("key_insight", "")
        )

        self.simulations.append(result)
        self._save()
        return result

    def _save(self):
        data = [asdict(s) for s in self.simulations[-50:]]
        try:
            from db import kv_set
            kv_set("actor_simulations", data)
        except Exception as e:
            logger.warning(f"⚠️ KV save actor_simulations failed ({e}), falling back to file")
            os.makedirs("data", exist_ok=True)
            with open(SIMULATION_FILE, "w") as f:
                json.dump(data, f, default=str)

    def get_aggregated_actor_intelligence(self) -> Dict:
        if not self.simulations:
            return {"status": "Inga simuleringar ännu", "simulations": 0}

        actor_activity = {}
        for sim in self.simulations[-10:]:
            for reaction in sim.reactions:
                aid = reaction.actor_id
                if aid not in actor_activity:
                    actor_activity[aid] = {"total_intensity": 0, "count": 0, "actions": []}
                actor_activity[aid]["total_intensity"] += reaction.intensity
                actor_activity[aid]["count"] += 1
                actor_activity[aid]["actions"].append(reaction.action)

        avg_panic = sum(s.panic_risk for s in self.simulations[-10:]) / min(len(self.simulations), 10)

        interaction_patterns = {}
        for sim in self.simulations[-10:]:
            for inter in sim.interactions:
                key = f"{inter.trigger_actor}->{inter.affected_actor}"
                if key not in interaction_patterns:
                    interaction_patterns[key] = {"count": 0, "amplifies": 0, "dampens": 0}
                interaction_patterns[key]["count"] += 1
                if inter.amplifies_or_dampens == "AMPLIFIES":
                    interaction_patterns[key]["amplifies"] += 1
                else:
                    interaction_patterns[key]["dampens"] += 1

        return {
            "simulations_analyzed": min(len(self.simulations), 10),
            "avg_panic_risk": round(avg_panic, 2),
            "most_active_actors": sorted(
                [{"actor": k, "avg_intensity": round(v["total_intensity"]/v["count"], 1)}
                 for k, v in actor_activity.items()],
                key=lambda x: x["avg_intensity"], reverse=True
            )[:5],
            "key_interaction_patterns": sorted(
                [{"pattern": k, "count": v["count"],
                  "usually": "AMPLIFIES" if v["amplifies"] > v["dampens"] else "DAMPENS"}
                 for k, v in interaction_patterns.items() if v["count"] >= 2],
                key=lambda x: x["count"], reverse=True
            )[:5],
            "latest_key_insight": self.simulations[-1].key_insight if self.simulations else ""
        }
