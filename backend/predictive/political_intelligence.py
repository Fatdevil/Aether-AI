# ============================================================
# FIL: backend/predictive/political_intelligence.py (NY FIL)
#
# POLITICAL INTELLIGENCE ENGINE
# Generaliserad makthavaranalys for marknadspaverkan
#
# PRINCIP: Politiska ledare foljer monster. Monstren ar
# predicerbara. Marknadseffekterna av deras beslut ar
# berakningsbara. Systemet ar AKTORS-AGNOSTISKT:
# Trump, Powell, Lagarde, nasta president — samma ramverk.
#
# ARKITEKTUR:
# 1. PoliticalActor: Dataclass per makthavare
# 2. RhetoricAnalyzer: Analyserar uttalanden, tonforandringar
# 3. BehaviorMatcher: Matchar mot historiska monster
# 4. PolicyPredictor: Sannolikhet per mojligt beslut
# 5. PoliticalIntelligenceEngine: Orchestrator
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger("aether.political_intelligence")

POLITICAL_DATA_FILE = "data/political_intelligence.json"


# ============================================================
# DEL 1: AKTORSTYPER OCH BETEENDEMODELLER
# ============================================================

class ActorType(str, Enum):
    PRESIDENT = "PRESIDENT"
    CENTRAL_BANK = "CENTRAL_BANK"
    AUTHORITARIAN = "AUTHORITARIAN"
    INSTITUTION = "INSTITUTION"
    FINANCE_MINISTER = "FINANCE_MINISTER"
    CARTEL = "CARTEL"


class PolicyArea(str, Enum):
    TRADE = "TRADE"
    MONETARY = "MONETARY"
    GEOPOLITICAL = "GEOPOLITICAL"
    REGULATORY = "REGULATORY"
    FISCAL = "FISCAL"
    ENERGY = "ENERGY"
    TECH = "TECH"


class EscalationPhase(str, Enum):
    SIGNAL = "SIGNAL"
    THREAT = "THREAT"
    ACTION = "ACTION"
    MARKET_REACTION = "MARKET_REACTION"
    BACKOFF_OR_ESCALATE = "BACKOFF_OR_ESCALATE"
    RESOLUTION = "RESOLUTION"


@dataclass
class BehaviorPattern:
    """Ett aterkommande beteendemonster for en makthavare."""
    name: str
    description: str
    typical_duration_days: int
    phases: List[Dict]
    trigger_conditions: List[str]
    backoff_conditions: List[str]
    historical_frequency: float
    market_impact: Dict[str, float]


@dataclass
class PoliticalActor:
    """En politisk makthavare med beteendemodell."""
    id: str
    name: str
    title: str
    actor_type: str
    active: bool
    power_concentration: float      # 0-1: hur mycket makt har personen ensam?
    predictability: float           # 0-1: hur predicerbar?
    market_sensitivity: float       # 0-1: bryr sig om marknadens reaktion?
    policy_areas: Dict[str, float]
    behavior_patterns: List[BehaviorPattern] = field(default_factory=list)
    signal_phrases: Dict[str, str] = field(default_factory=dict)
    backoff_triggers: List[Dict] = field(default_factory=list)
    transmission_assets: Dict[str, List[str]] = field(default_factory=dict)
    predictions_made: int = 0
    predictions_correct: int = 0


# ============================================================
# DEL 2: FORDEFINIERADE AKTORER
# ============================================================

def create_default_actors() -> List[PoliticalActor]:
    """Skapar alla fordefinierade politiska aktorer."""
    actors = []

    # ---- TRUMP ----
    trump = PoliticalActor(
        id="trump",
        name="Donald Trump",
        title="President of the United States",
        actor_type=ActorType.PRESIDENT,
        active=True,
        power_concentration=0.85,
        predictability=0.70,
        market_sensitivity=0.80,
        policy_areas={
            PolicyArea.TRADE: 0.80,
            PolicyArea.GEOPOLITICAL: 0.50,
            PolicyArea.MONETARY: 0.70,
            PolicyArea.REGULATORY: 0.40,
            PolicyArea.FISCAL: 0.60,
            PolicyArea.TECH: 0.30,
        },
        behavior_patterns=[
            BehaviorPattern(
                name="Eskalerings-deeskalerings-cykel",
                description="Oppnar extremt, skapar kaos, erbjuder deal som var malet fran borjan.",
                typical_duration_days=21,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 3, "description": "Aggressivt uttalande pa Truth Social / presstraff"},
                    {"phase": "THREAT", "duration_days": 5, "description": "Konkret hot med deadline. Marknaden faller."},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "SP500 -3 till -7%. Media panik."},
                    {"phase": "BACKOFF_OR_ESCALATE", "duration_days": 5, "description": "Om SP500 faller >5%: backar. Annars: eskalerar."},
                    {"phase": "RESOLUTION", "duration_days": 5, "description": "Deal som ar samre an status quo men battre an hotet."},
                ],
                trigger_conditions=["Handelsforhandling", "Bilateral relation", "Valnaerhet"],
                backoff_conditions=["SP500 -5% pa 1 vecka", "Bipartisan kritik", "Fox News negativt"],
                historical_frequency=0.75,
                market_impact={"SIGNAL": -1.0, "THREAT": -3.0, "MARKET_REACTION": -2.0, "RESOLUTION": +4.0},
            ),
            BehaviorPattern(
                name="Marknad-som-scorecard",
                description="Trump anvaender SP500 som betyg. Stark bors = bra president. Backar vid borsfall.",
                typical_duration_days=10,
                phases=[
                    {"phase": "ACTION", "duration_days": 1, "description": "Fattar beslut (tull, sanktion, uttalande)"},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "Marknaden reagerar negativt"},
                    {"phase": "BACKOFF_OR_ESCALATE", "duration_days": 5, "description": "Om SP500 -5%+: justerar beslutet."},
                ],
                trigger_conditions=["SP500 faller >5% fran recent topp"],
                backoff_conditions=["SP500 aterhamtar", "Nyhetsagenda skiftar"],
                historical_frequency=0.80,
                market_impact={"ACTION": -2.0, "BACKOFF_OR_ESCALATE": +3.0},
            ),
        ],
        signal_phrases={
            "we'll see what happens": "AVVAKTAR -- inget beslut annu, 3-5 dagars fordrojning",
            "very soon": "48H_ACTION -- beslut inom 48 timmar",
            "all options are on the table": "ESKALERING_NARA -- 70% sannolikhet for aktion inom 7 dagar",
            "good conversation": "DEESKALERING -- tonlage mildras, deal mojlig",
            "big announcement": "EVENT_INOM_24H -- marknadspavverkande besked",
            "we are looking at it very strongly": "FORBEREDELSE -- 60% aktion inom 14 dagar",
            "reciprocal": "TULL_KOMMANDE -- handelsatgard planeras",
            "unfair": "RETORISK_UPPTRAPPNING -- annu ingen aktion men riktning negativ",
            "deal of the century": "DEAL_SIGNAL -- forhandling aktiv, deeskalering trolig",
            "great relationship": "STATUS_QUO -- ingen forandring vaentad",
        },
        backoff_triggers=[
            {"trigger": "SP500 faller >5% pa <7 dagar", "probability": 0.70, "response": "Deeskalerar inom 5-10 dagar", "historical_examples": "Kina-tullar dec 2018, Iran jan 2020"},
            {"trigger": "10Y yield stiger >30bps pa <5 dagar", "probability": 0.50, "response": "Trycker pa Fed, mildrar fiskal retorik"},
            {"trigger": "Godkannandesiffror <40%", "probability": 0.60, "response": "Skiftar fokus till populara fragor"},
            {"trigger": "Bipartisan kongresskritik", "probability": 0.40, "response": "Modifierar men backar sallan helt"},
        ],
        transmission_assets={
            PolicyArea.TRADE: ["SP500", "EEM", "EURUSD", "OMXS30", "XLK"],
            PolicyArea.GEOPOLITICAL: ["OIL", "GOLD", "VIX", "XLE", "ITA"],
            PolicyArea.MONETARY: ["US10Y", "GOLD", "SP500", "BTC", "USDSEK"],
            PolicyArea.FISCAL: ["SP500", "US10Y", "XLF"],
        },
    )
    actors.append(trump)

    # ---- POWELL (Fed) ----
    powell = PoliticalActor(
        id="powell",
        name="Jerome Powell",
        title="Chair, Federal Reserve",
        actor_type=ActorType.CENTRAL_BANK,
        active=True,
        power_concentration=0.60,
        predictability=0.85,
        market_sensitivity=0.30,
        policy_areas={PolicyArea.MONETARY: 0.90, PolicyArea.REGULATORY: 0.50},
        behavior_patterns=[
            BehaviorPattern(
                name="Forward guidance-cykel",
                description="Signalerar kommande beslut 2-6 veckor fore via tal och FOMC-minuter.",
                typical_duration_days=42,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 14, "description": "Tal med nya formuleringar. Marknaden tolkar."},
                    {"phase": "THREAT", "duration_days": 14, "description": "FOMC-minuter bekraftar riktning."},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebeslut. Oftast redan prissatt."},
                    {"phase": "RESOLUTION", "duration_days": 14, "description": "Ny forward guidance for nasta mote."},
                ],
                trigger_conditions=["Inflationsdata", "Arbetsmarknadsdata", "Finansiell stress"],
                backoff_conditions=["Systemisk finansiell kris", "Politiskt tryck"],
                historical_frequency=0.90,
                market_impact={"SIGNAL": -0.5, "ACTION": -1.0, "RESOLUTION": +0.5},
            ),
        ],
        signal_phrases={
            "data dependent": "AVVAKTAR -- inget forandrat sedan sist",
            "considerable progress": "SNART_AKTION -- ranteandring trolig nasta mote",
            "patient": "HALLER_FAST -- ingen forandring planerad",
            "meeting by meeting": "OSAKER -- kan ga bada hall",
            "determined": "HOJNING_TROLIG -- hawkish signal",
            "appropriate": "STANDARD -- foljer planen",
            "closely monitoring": "BEREDD_AGERA -- redo att agera om data forsemras",
        },
        backoff_triggers=[
            {"trigger": "VIX >35 + kreditspreadar vidgas >100bps", "probability": 0.80, "response": "Emergency rate cut eller likviditetsstod"},
            {"trigger": "Arbetsloshet stiger >0.5% pa 3 manader", "probability": 0.70, "response": "Skiftar till dovish, sanker snabbare"},
        ],
        transmission_assets={PolicyArea.MONETARY: ["US10Y", "SP500", "GOLD", "BTC", "USDSEK", "EURUSD", "XLF"]},
    )
    actors.append(powell)

    # ---- ECB / LAGARDE ----
    lagarde = PoliticalActor(
        id="lagarde",
        name="Christine Lagarde",
        title="President, European Central Bank",
        actor_type=ActorType.CENTRAL_BANK,
        active=True,
        power_concentration=0.50,
        predictability=0.80,
        market_sensitivity=0.25,
        policy_areas={PolicyArea.MONETARY: 0.85},
        behavior_patterns=[
            BehaviorPattern(
                name="ECB forward guidance",
                description="Liknande Fed men med storre intern oenighet (nordliga vs sydliga lander).",
                typical_duration_days=42,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 14, "description": "Lagarde-tal + ECB blogginlagg"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebeslut"},
                    {"phase": "RESOLUTION", "duration_days": 14, "description": "Ny guidance"},
                ],
                trigger_conditions=["Eurozone CPI", "Tysk industriproduktion"],
                backoff_conditions=["Europeisk bankstress", "Spridning Italia-Tyskland"],
                historical_frequency=0.85,
                market_impact={"SIGNAL": -0.3, "ACTION": -0.8},
            ),
        ],
        signal_phrases={
            "determined": "HOJNING -- hawkish",
            "flexible": "DOVISH -- beredd sanka",
            "fragmentation": "ORO -- spridningsrisk",
            "transmission protection": "KRIS_NARA -- beredd agera",
        },
        backoff_triggers=[
            {"trigger": "Italiensk-tysk spread >250bps", "probability": 0.75, "response": "TPI aktiveras"},
        ],
        transmission_assets={PolicyArea.MONETARY: ["EURUSD", "VGK", "OMXS30", "USDSEK"]},
    )
    actors.append(lagarde)

    # ---- RIKSBANKEN ----
    riksbanken = PoliticalActor(
        id="riksbanken",
        name="Riksbanken (Erik Thedeen)",
        title="Sveriges Riksbank",
        actor_type=ActorType.CENTRAL_BANK,
        active=True,
        power_concentration=0.55,
        predictability=0.80,
        market_sensitivity=0.20,
        policy_areas={PolicyArea.MONETARY: 0.85},
        behavior_patterns=[
            BehaviorPattern(
                name="Riksbanken rantebesked",
                description="Foljer i stort ECB men med lag till svensk data (fastighetsmarknad, SEK).",
                typical_duration_days=56,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 21, "description": "Protokoll + tal"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebesked var 8:e vecka"},
                ],
                trigger_conditions=["KPIF-data", "SEK-kurs", "Bostadspriser"],
                backoff_conditions=["SEK-kris (<9.0 EURSEK)", "Fastighetsmarknadskollaps"],
                historical_frequency=0.85,
                market_impact={"ACTION": -0.5},
            ),
        ],
        signal_phrases={
            "kronan ar svag": "HOJNING_TROLIG",
            "inflationen ar for hog": "HOJNING_TROLIG",
            "konjunkturen forsvagas": "SANKNING_TROLIG",
        },
        backoff_triggers=[],
        transmission_assets={PolicyArea.MONETARY: ["OMXS30", "USDSEK", "EURUSD"]},
    )
    actors.append(riksbanken)

    # ---- OPEC+ ----
    opec = PoliticalActor(
        id="opec",
        name="OPEC+ (MBS / Saudiarabien)",
        title="OPEC+ koalitionen",
        actor_type=ActorType.CARTEL,
        active=True,
        power_concentration=0.65,
        predictability=0.55,
        market_sensitivity=0.40,
        policy_areas={PolicyArea.ENERGY: 0.80},
        behavior_patterns=[
            BehaviorPattern(
                name="Produktionsbeslut-cykel",
                description="Manatliga moten. Internt spel Saudiarabien-Ryssland-UAE. Beslutet lackar 1-2d fore.",
                typical_duration_days=30,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 7, "description": "Lackor fran delegater, Reuters/Bloomberg"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Officiellt beslut"},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "Oljepris reagerar"},
                ],
                trigger_conditions=["Oljepris <$70", "Oljepris >$100"],
                backoff_conditions=["USA hotar SPR-release", "Intern oenighet (UAE)"],
                historical_frequency=0.70,
                market_impact={"ACTION": 3.0},
            ),
        ],
        signal_phrases={
            "voluntary cuts": "BULLISH_OLJA -- begransad produktion",
            "compliance": "STATUS_QUO",
            "market conditions": "OVERVAEGER_FORANDRING",
            "gradually increase": "BEARISH_OLJA -- mer olja pa marknaden",
        },
        backoff_triggers=[
            {"trigger": "Brent >$110 + USA pressar", "probability": 0.50, "response": "Okar produktion"},
        ],
        transmission_assets={PolicyArea.ENERGY: ["OIL", "XLE", "GOLD", "OMXS30"]},
    )
    actors.append(opec)

    return actors


# ============================================================
# DEL 3: RETORISK ANALYSATOR
# ============================================================

class RhetoricAnalyzer:
    """Analyserar politiska uttalanden och detekterar tonforandringar."""

    def analyze_statement(self, actor: PoliticalActor, statement: str,
                          source: str = "", timestamp: str = "") -> Dict:
        """Analysera ETT uttalande. Matchar mot aktorns signal_phrases."""
        statement_lower = statement.lower()
        matched_signals = []

        for phrase, interpretation in actor.signal_phrases.items():
            if phrase.lower() in statement_lower:
                matched_signals.append({
                    "phrase": phrase,
                    "interpretation": interpretation,
                    "context": self._extract_context(statement_lower, phrase.lower()),
                })

        # Bedom overall ton
        esc_words = ["tariff", "sanction", "threat", "war", "retaliate", "punish", "reciprocal", "unfair"]
        deesc_words = ["deal", "talk", "negotiate", "agree", "good", "friend", "great", "progress"]

        esc_count = sum(1 for w in esc_words if w in statement_lower)
        deesc_count = sum(1 for w in deesc_words if w in statement_lower)

        if esc_count > deesc_count + 1:
            tone = "ESCALATION"
        elif deesc_count > esc_count + 1:
            tone = "DEESCALATION"
        else:
            tone = "NEUTRAL"

        return {
            "actor": actor.id,
            "statement_preview": statement[:200],
            "source": source,
            "timestamp": timestamp or datetime.now().isoformat(),
            "matched_signals": matched_signals,
            "tone": tone,
            "escalation_score": esc_count - deesc_count,
            "n_signals": len(matched_signals),
        }

    def _extract_context(self, text: str, phrase: str, window: int = 50) -> str:
        idx = text.find(phrase)
        if idx < 0:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(phrase) + window)
        return "..." + text[start:end] + "..."

    def detect_tonal_shift(self, actor: PoliticalActor,
                           recent_analyses: List[Dict], lookback: int = 5) -> Dict:
        """Detektera tonforandring over de senaste N uttalandena."""
        if len(recent_analyses) < 2:
            return {"shift": "INSUFFICIENT_DATA", "confidence": 0}

        recent = recent_analyses[-lookback:]
        scores = [a.get("escalation_score", 0) for a in recent]

        if len(scores) >= 3:
            first_half = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
            second_half = sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1)
            delta = second_half - first_half
        else:
            delta = scores[-1] - scores[0]

        if delta > 1.5:
            shift = "ESCALATING"
            confidence = min(abs(delta) / 3.0, 1.0)
        elif delta < -1.5:
            shift = "DEESCALATING"
            confidence = min(abs(delta) / 3.0, 1.0)
        else:
            shift = "STABLE"
            confidence = 0.3

        return {
            "shift": shift,
            "delta": round(delta, 2),
            "confidence": round(confidence, 2),
            "recent_tone": recent[-1].get("tone", "NEUTRAL") if recent else "UNKNOWN",
            "trend_scores": scores,
            "implication": {
                "ESCALATING": f"{actor.name} trappar upp retoriken. Forbered for negativ marknadseffekt.",
                "DEESCALATING": f"{actor.name} mildrar tonen. Mojlig positiv vandpunkt.",
                "STABLE": f"Ingen signifikant tonforandring fran {actor.name}.",
            }.get(shift, "")
        }


# ============================================================
# DEL 4: BEHAVIOR MATCHER
# ============================================================

class BehaviorMatcher:
    """Matchar nuvarande situation mot aktorers kanda beteendemonster."""

    def match_patterns(self, actor: PoliticalActor, current_context: Dict,
                       market_data: Dict = None) -> List[Dict]:
        matches = []

        for pattern in actor.behavior_patterns:
            match_score = 0
            current_phase = None
            reasoning = []

            # Kolla trigger conditions
            for trigger in pattern.trigger_conditions:
                trigger_lower = trigger.lower()
                context_str = json.dumps(current_context).lower()
                if any(word in context_str for word in trigger_lower.split()):
                    match_score += 0.3
                    reasoning.append(f"Trigger matchar: {trigger}")

            # Kolla backoff conditions
            backoff_active = False
            if market_data:
                for backoff in pattern.backoff_conditions:
                    backoff_lower = backoff.lower()
                    if "sp500" in backoff_lower and "-5%" in backoff_lower:
                        sp_change = market_data.get("sp500_change_7d", 0)
                        if sp_change < -0.05:
                            backoff_active = True
                            reasoning.append(f"Backoff aktiv: SP500 {sp_change*100:.1f}% 7d")

            # Bedom vilken fas
            rhetoric_tone = current_context.get("rhetoric_tone", "NEUTRAL")
            if rhetoric_tone == "ESCALATION" and not backoff_active:
                current_phase = "THREAT"
                match_score += 0.3
            elif rhetoric_tone == "DEESCALATION" or backoff_active:
                current_phase = "RESOLUTION"
                match_score += 0.2
            elif rhetoric_tone == "NEUTRAL":
                current_phase = "SIGNAL"
                match_score += 0.1

            if match_score > 0.3:
                phase_idx = None
                for i, phase in enumerate(pattern.phases):
                    if phase["phase"] == current_phase:
                        phase_idx = i
                        break

                next_phase = None
                if phase_idx is not None and phase_idx < len(pattern.phases) - 1:
                    next_phase = pattern.phases[phase_idx + 1]

                expected_impact = pattern.market_impact.get(
                    next_phase["phase"] if next_phase else current_phase, 0
                )

                matches.append({
                    "pattern": pattern.name,
                    "match_score": round(match_score, 2),
                    "current_phase": current_phase,
                    "next_phase": next_phase["phase"] if next_phase else "END",
                    "next_phase_description": next_phase["description"] if next_phase else "Monster avslutat",
                    "estimated_days_to_next": next_phase["duration_days"] if next_phase else 0,
                    "expected_market_impact_pct": expected_impact,
                    "backoff_active": backoff_active,
                    "confidence": round(match_score * pattern.historical_frequency, 2),
                    "reasoning": reasoning,
                })

        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches


# ============================================================
# DEL 5: POLICY PREDICTOR
# ============================================================

class PolicyPredictor:
    """Givet aktorens monster + signaler -> sannolikhet per beslut."""

    def build_prediction_prompt(self, actor: PoliticalActor, context: str,
                                rhetoric_analysis: Dict, pattern_matches: List[Dict],
                                market_context: str = "") -> str:
        patterns_str = ""
        for m in pattern_matches[:3]:
            patterns_str += f"\n- {m['pattern']}: fas={m['current_phase']}, nasta={m['next_phase']}, confidence={m['confidence']}"

        signals_str = ""
        for s in rhetoric_analysis.get("matched_signals", [])[:5]:
            signals_str += f"\n- '{s['phrase']}' -> {s['interpretation']}"

        return f"""Du ar en politisk analytiker som predicerar makthavares nasta beslut.

AKTOR: {actor.name} ({actor.title})
Typ: {actor.actor_type}
Predicerbarhet: {actor.predictability:.0%}
Marknadskansliglet: {actor.market_sensitivity:.0%}

AKTUELL KONTEXT:
{context}

{f"MARKNADSKONTEXT: {market_context}" if market_context else ""}

RETORISK ANALYS:
Ton: {rhetoric_analysis.get('tone', 'NEUTRAL')}
Eskaleringspoang: {rhetoric_analysis.get('escalation_score', 0)}
Matchade signaler:{signals_str if signals_str else " Inga"}

MONSTERMATCHNING:{patterns_str if patterns_str else " Inga aktiva monster"}

BACKOFF-TRIGGERS for {actor.name}:
{json.dumps([t['trigger'] + ' -> ' + t['response'] for t in actor.backoff_triggers], ensure_ascii=False, indent=2)}

Svara ENBART med JSON:
{{
    "predictions": [
        {{
            "action": "Kort beskrivning av troligt beslut max 15 ord",
            "policy_area": "TRADE|MONETARY|GEOPOLITICAL|REGULATORY|FISCAL|ENERGY",
            "probability": 0.0-1.0,
            "timeframe_days": 1-90,
            "affected_assets": ["SP500", "GOLD", "OIL"],
            "estimated_impact": {{"SP500": -3, "GOLD": 5, "OIL": 10}},
            "confidence": "HIGH|MEDIUM|LOW",
            "reasoning": "max 25 ord",
            "what_changes_this": "Vad som skulle andra prediktionen max 15 ord"
        }}
    ],
    "dominant_scenario": "Det mest sannolika utfallet max 30 ord",
    "contrarian_view": "Vad om vi har fel? Max 25 ord",
    "key_signal_to_watch": "En specifik sak att bevaka max 15 ord",
    "overall_market_bias": "BULLISH|BEARISH|NEUTRAL",
    "time_to_clarity_days": 1-30
}}

REGLER:
- Max 4 prediktioner, rankat efter sannolikhet
- Sannolikheter summerar INTE till 1.0 (oberoende handelser)
- estimated_impact i PROCENT
- Ta hansyn till backoff-triggers
- Var REALISTISK med timeframes
- BARA JSON"""

    def parse_prediction(self, ai_response: Dict, actor: PoliticalActor) -> Dict:
        """Parsar AI-svar och laggar till aktors-metadata."""
        predictions = ai_response.get("predictions", [])

        for pred in predictions:
            policy = pred.get("policy_area", "")
            if policy in actor.transmission_assets:
                pred["known_transmission_assets"] = actor.transmission_assets[policy]
            pred["actor_id"] = actor.id
            pred["actor_name"] = actor.name
            pred["actor_predictability"] = actor.predictability

        return {
            "actor": actor.id,
            "timestamp": datetime.now().isoformat(),
            "predictions": predictions,
            "dominant_scenario": ai_response.get("dominant_scenario", ""),
            "contrarian_view": ai_response.get("contrarian_view", ""),
            "key_signal": ai_response.get("key_signal_to_watch", ""),
            "market_bias": ai_response.get("overall_market_bias", "NEUTRAL"),
            "time_to_clarity": ai_response.get("time_to_clarity_days", 14),
        }


# ============================================================
# DEL 6: ENGINE (ORCHESTRATOR)
# ============================================================

class PoliticalIntelligenceEngine:
    """
    Orchestrator for politisk intelligens.
    Kors dagligen som del av L3 PREDICTIVE.
    """

    def __init__(self):
        self.actors = {a.id: a for a in create_default_actors()}
        self.rhetoric = RhetoricAnalyzer()
        self.behavior = BehaviorMatcher()
        self.predictor = PolicyPredictor()
        self.analysis_history: List[Dict] = []
        self._load()

    def _load(self):
        try:
            from db import kv_get
            data = kv_get("political_intelligence")
            if data:
                self.analysis_history = data.get("history", [])
                return
        except Exception:
            pass
        if os.path.exists(POLITICAL_DATA_FILE):
            try:
                with open(POLITICAL_DATA_FILE, "r") as f:
                    self.analysis_history = json.load(f)
            except Exception:
                pass

    def _save(self):
        data = {"history": self.analysis_history[-500:]}
        try:
            from db import kv_set
            kv_set("political_intelligence", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(POLITICAL_DATA_FILE, "w") as f:
                json.dump(self.analysis_history[-500:], f, default=str)

    def get_active_actors(self) -> List[PoliticalActor]:
        return [a for a in self.actors.values() if a.active]

    def add_actor(self, actor: PoliticalActor):
        """Lagg till ny aktor (t.ex. vid presidentbyte)."""
        self.actors[actor.id] = actor
        logger.info(f"Added political actor: {actor.name}")

    def deactivate_actor(self, actor_id: str):
        """Inaktivera en aktor (t.ex. Trump nar han avgar)."""
        if actor_id in self.actors:
            self.actors[actor_id].active = False
            logger.info(f"Deactivated political actor: {actor_id}")

    def analyze_daily(self, news_summary: str, market_data: Dict) -> Dict:
        """
        HUVUDMETOD: Daglig politisk analys.
        Anropas fran L3 PREDICTIVE.

        Returns: prompts for AI + direkt-analyserbara resultat
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "actors_analyzed": [],
            "prompts_for_ai": [],
            "direct_signals": [],
            "dominant_actor": None,
            "overall_political_risk": "NORMAL",
        }

        for actor in self.get_active_actors():
            # Steg 1: Retorisk analys (kraver INTE AI)
            rhetoric = self.rhetoric.analyze_statement(actor, news_summary)

            # Hamta historik for tonal shift
            actor_history = [
                h.get("rhetoric", {})
                for h in self.analysis_history
                if h.get("actor") == actor.id
            ]
            tonal_shift = self.rhetoric.detect_tonal_shift(actor, actor_history)

            # Steg 2: Monstermatchning (kraver INTE AI)
            context = {
                "recent_actions": news_summary[:500],
                "rhetoric_tone": rhetoric["tone"],
                "tonal_shift": tonal_shift["shift"],
            }
            pattern_matches = self.behavior.match_patterns(actor, context, market_data)

            # Steg 3: Generera AI-prompt BARA om signaler hittats
            if rhetoric["n_signals"] > 0 or len(pattern_matches) > 0:
                prompt = self.predictor.build_prediction_prompt(
                    actor=actor,
                    context=news_summary[:1000],
                    rhetoric_analysis=rhetoric,
                    pattern_matches=pattern_matches,
                    market_context=json.dumps(market_data)[:500] if market_data else "",
                )
                results["prompts_for_ai"].append({
                    "actor_id": actor.id,
                    "actor_name": actor.name,
                    "prompt": prompt,
                })

            # Direkta signaler (utan AI)
            if tonal_shift["shift"] in ("ESCALATING", "DEESCALATING") and tonal_shift["confidence"] > 0.5:
                results["direct_signals"].append({
                    "actor": actor.name,
                    "signal": tonal_shift["shift"],
                    "confidence": tonal_shift["confidence"],
                    "implication": tonal_shift["implication"],
                    "affected_assets": list(set(
                        a for assets in actor.transmission_assets.values() for a in assets
                    )),
                })

            if pattern_matches and pattern_matches[0]["confidence"] > 0.4:
                best = pattern_matches[0]
                results["direct_signals"].append({
                    "actor": actor.name,
                    "signal": f"Monster matchar: {best['pattern']}",
                    "current_phase": best["current_phase"],
                    "next_phase": best["next_phase"],
                    "expected_impact": best["expected_market_impact_pct"],
                    "confidence": best["confidence"],
                    "days_to_next": best["estimated_days_to_next"],
                })

            results["actors_analyzed"].append({
                "actor": actor.id,
                "name": actor.name,
                "rhetoric_tone": rhetoric["tone"],
                "tonal_shift": tonal_shift["shift"],
                "pattern_matches": len(pattern_matches),
                "signals_detected": rhetoric["n_signals"],
            })

        # Bestam dominant aktor och politisk risk
        if results["direct_signals"]:
            escalating = [s for s in results["direct_signals"] if "ESCALAT" in str(s.get("signal", ""))]
            if len(escalating) >= 2:
                results["overall_political_risk"] = "HIGH"
            elif len(escalating) >= 1:
                results["overall_political_risk"] = "ELEVATED"

        if results["actors_analyzed"]:
            most_active = max(results["actors_analyzed"], key=lambda x: x["signals_detected"])
            results["dominant_actor"] = most_active["name"]

        # Spara historik
        self.analysis_history.append({
            "timestamp": results["timestamp"],
            "actors": results["actors_analyzed"],
            "political_risk": results["overall_political_risk"],
        })
        self._save()

        return results

    def process_ai_predictions(self, actor_id: str, ai_response: Dict) -> Dict:
        """Parsa AI-svar for en aktor."""
        actor = self.actors.get(actor_id)
        if not actor:
            return {"error": f"Unknown actor: {actor_id}"}
        return self.predictor.parse_prediction(ai_response, actor)

    def get_aggregated_market_bias(self) -> Dict:
        """Aggregera alla aktiva aktorers marknadspaverkan."""
        recent = self.analysis_history[-10:]
        if not recent:
            return {"bias": "NEUTRAL", "confidence": 0, "actors": []}

        escalation_count = 0
        deescalation_count = 0
        total_actors = 0

        for entry in recent:
            for actor_data in entry.get("actors", []):
                total_actors += 1
                if actor_data.get("tonal_shift") == "ESCALATING":
                    escalation_count += 1
                elif actor_data.get("tonal_shift") == "DEESCALATING":
                    deescalation_count += 1

        if escalation_count > deescalation_count + 2:
            bias = "BEARISH"
        elif deescalation_count > escalation_count + 2:
            bias = "BULLISH"
        else:
            bias = "NEUTRAL"

        return {
            "bias": bias,
            "escalation_ratio": round(escalation_count / max(total_actors, 1), 2),
            "deescalation_ratio": round(deescalation_count / max(total_actors, 1), 2),
            "entries_analyzed": len(recent),
            "overall_risk": recent[-1].get("political_risk", "NORMAL") if recent else "NORMAL",
        }

    def get_dashboard(self) -> Dict:
        """Full dashboard-data for API."""
        bias = self.get_aggregated_market_bias()
        actors_summary = []
        for a in self.get_active_actors():
            actors_summary.append({
                "id": a.id,
                "name": a.name,
                "title": a.title,
                "type": a.actor_type,
                "power_concentration": a.power_concentration,
                "predictability": a.predictability,
                "market_sensitivity": a.market_sensitivity,
                "n_patterns": len(a.behavior_patterns),
                "n_signal_phrases": len(a.signal_phrases),
                "n_policy_areas": len(a.policy_areas),
                "active": a.active,
            })
        return {
            "market_bias": bias,
            "active_actors": actors_summary,
            "recent_analyses": self.analysis_history[-5:],
            "total_analyses": len(self.analysis_history),
        }
