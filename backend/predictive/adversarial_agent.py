# ============================================================
# FIL: backend/predictive/adversarial_agent.py
# Devils Advocate: attackerar systematiskt varje rekommendation
#
# Confirmation bias är det största hotet mot AI-tradingsystem.
# Alla andra moduler hittar skäl att AGERA.
# Denna modul hittar skäl att INTE agera.
# ============================================================

import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdversarialResult:
    original_recommendation: str
    original_conviction: float
    challenges: List[Dict]
    weakest_assumption: str
    counter_narrative: str
    base_rate: str
    who_disagrees: str
    adjusted_conviction: float
    adjustment_reason: str
    should_proceed: bool
    red_flags: List[str]


class AdversarialAgent:
    def build_challenge_prompt(self, recommendation: Dict, market_context: str = "", portfolio_context: str = "") -> str:
        rec_str = json.dumps(recommendation, indent=2, ensure_ascii=False) if isinstance(recommendation, dict) else str(recommendation)

        return f"""Du är en DEVILS ADVOCATE. Din enda uppgift är att hitta PROBLEM
med följande investeringsrekommendation. Du är INTE här för att bekräfta.
Du är här för att ATTACKERA.

REKOMMENDATION:
{rec_str}

{f"MARKNADSKONTEXT: {market_context}" if market_context else ""}
{f"PORTFÖLJKONTEXT: {portfolio_context}" if portfolio_context else ""}

Svara ENBART med JSON:
{{
    "challenges": [
        {{
            "argument": "Kort motargument max 25 ord",
            "severity": "KRITISK|ALLVARLIG|MINOR",
            "type": "ASSUMPTION|DATA|TIMING|CROWDING|HISTORICAL|STRUCTURAL",
            "invalidates_recommendation": false
        }}
    ],
    "weakest_assumption": "Den svagaste punkten max 30 ord",
    "counter_narrative": "Det BÄSTA argumentet MOT denna position max 40 ord",
    "base_rate": "Historiskt: hur ofta har liknande rekommendationer stämt?",
    "who_disagrees": "Vilka marknadsaktörer tar motsatt position max 25 ord",
    "what_changes_mind": "Vad bevisar att rekommendationen är FEL max 20 ord",
    "crowding_risk": "Hur många täcker redan denna position? max 15 ord",
    "timing_risk": "Är tajmingen rätt eller för tidig/sen? max 15 ord",
    "conviction_adjustment": {{
        "original": 0.7,
        "adjusted": 0.5,
        "reason": "Varför justering max 20 ord"
    }},
    "red_flags": ["Varning 1", "Varning 2"],
    "verdict": "PROCEED|REDUCE_SIZE|DELAY|BLOCK",
    "verdict_reasoning": "max 25 ord"
}}

REGLER:
- Minst 3 challenges
- conviction adjusted: ALDRIG högre än original
- BLOCK: bara vid KRITISK brist som invaliderar hela tesen
- PROCEED: bara om alla challenges är MINOR
- Var BRUTAL. Bättre att missa en trade än att göra en dålig.
- BARA JSON"""

    def parse_challenge(self, ai_response: Dict, original_rec: Dict) -> AdversarialResult:
        conv_adj = ai_response.get("conviction_adjustment", {})
        original_conv = float(conv_adj.get("original", 0.7))
        adjusted_conv = float(conv_adj.get("adjusted", 0.5))

        red_flags = ai_response.get("red_flags", [])
        critical_challenges = [
            c for c in ai_response.get("challenges", [])
            if c.get("severity") == "KRITISK"
        ]
        if critical_challenges:
            red_flags.append(f"{len(critical_challenges)} KRITISKA utmaningar identifierade")

        verdict = ai_response.get("verdict", "REDUCE_SIZE")
        should_proceed = verdict in ("PROCEED", "REDUCE_SIZE")

        return AdversarialResult(
            original_recommendation=str(original_rec)[:200],
            original_conviction=original_conv,
            challenges=ai_response.get("challenges", []),
            weakest_assumption=ai_response.get("weakest_assumption", ""),
            counter_narrative=ai_response.get("counter_narrative", ""),
            base_rate=ai_response.get("base_rate", ""),
            who_disagrees=ai_response.get("who_disagrees", ""),
            adjusted_conviction=adjusted_conv,
            adjustment_reason=conv_adj.get("reason", ""),
            should_proceed=should_proceed,
            red_flags=red_flags,
        )

    def apply_to_portfolio(self, recommendations: List[Dict], challenges: List[AdversarialResult]) -> List[Dict]:
        adjusted = []
        for rec, challenge in zip(recommendations, challenges):
            if not challenge.should_proceed:
                logger.info(f"BLOCKERAD: {rec.get('asset', '?')} - {challenge.adjustment_reason}")
                continue

            adjustment_ratio = challenge.adjusted_conviction / max(challenge.original_conviction, 0.01)
            original_size = rec.get("weight", rec.get("size", 1.0))
            adjusted_size = original_size * adjustment_ratio

            adjusted_rec = dict(rec)
            adjusted_rec["original_conviction"] = challenge.original_conviction
            adjusted_rec["adjusted_conviction"] = challenge.adjusted_conviction
            adjusted_rec["adjustment_ratio"] = round(adjustment_ratio, 2)
            adjusted_rec["weight"] = round(adjusted_size, 2)
            adjusted_rec["red_flags"] = challenge.red_flags
            adjusted_rec["weakest_assumption"] = challenge.weakest_assumption
            adjusted.append(adjusted_rec)

        return adjusted
