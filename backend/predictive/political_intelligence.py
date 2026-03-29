# ============================================================
# FIL: backend/predictive/political_intelligence.py
#
# POLITICAL INTELLIGENCE ENGINE v2
# Lean, fast, Sentinel-integrated power-actor analysis
#
# v2 DESIGN:
# 1. NewsSentinel (var 5 min) -> scorar nyheter med impact
# 2. PoliticalFilter -> matchar mot aktorer via signal_phrases
# 3. EscalationTracker -> raknar signal-ackumulering per aktor
# 4. Supervisor laser get_current_state() -> portfoljjustering
#
# VAD SOM TAGITS BORT (vs v1):
# - PolicyPredictor (AI-call som reformulerade existing data)
# - BehaviorMatcher (komplex fasmatchning med sprakproblem)
# - analyze_daily() nyhetsparser (duplicerade NewsSentinel)
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger("aether.political_intelligence")

POLITICAL_DATA_FILE = "data/political_intelligence.json"


# ============================================================
# DEL 1: DATAMODELL (oforandrad fran v1)
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
    """Ett aterkommande beteendemonster for en makthavare (metadata only i v2)."""
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
# DEL 2: FORDEFINIERADE AKTORER (oforandrad)
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
                    {"phase": "SIGNAL", "duration_days": 3, "description": "Aggressivt uttalande"},
                    {"phase": "THREAT", "duration_days": 5, "description": "Konkret hot med deadline"},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "SP500 -3 till -7%"},
                    {"phase": "BACKOFF_OR_ESCALATE", "duration_days": 5, "description": "Om SP500 -5%: backar"},
                    {"phase": "RESOLUTION", "duration_days": 5, "description": "Deal samre an status quo"},
                ],
                trigger_conditions=["trade", "tariff", "bilateral", "election"],
                backoff_conditions=["SP500 -5% pa 1 vecka", "Bipartisan kritik"],
                historical_frequency=0.75,
                market_impact={"SIGNAL": -1.0, "THREAT": -3.0, "MARKET_REACTION": -2.0, "RESOLUTION": +4.0},
            ),
            BehaviorPattern(
                name="Marknad-som-scorecard",
                description="Trump anvaender SP500 som betyg. Backar vid borsfall.",
                typical_duration_days=10,
                phases=[
                    {"phase": "ACTION", "duration_days": 1, "description": "Fattar beslut"},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "Marknaden reagerar"},
                    {"phase": "BACKOFF_OR_ESCALATE", "duration_days": 5, "description": "Om SP500 -5%+: justerar"},
                ],
                trigger_conditions=["SP500 faller >5%"],
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
            {"trigger": "SP500 faller >5% pa <7 dagar", "probability": 0.70, "response": "Deeskalerar inom 5-10 dagar"},
            {"trigger": "10Y yield stiger >30bps pa <5 dagar", "probability": 0.50, "response": "Trycker pa Fed"},
            {"trigger": "Godkannandesiffror <40%", "probability": 0.60, "response": "Skiftar fokus"},
            {"trigger": "Bipartisan kongresskritik", "probability": 0.40, "response": "Modifierar"},
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
                description="Signalerar kommande beslut 2-6 veckor fore.",
                typical_duration_days=42,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 14, "description": "Tal med nya formuleringar"},
                    {"phase": "THREAT", "duration_days": 14, "description": "FOMC-minuter bekraftar"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebeslut"},
                    {"phase": "RESOLUTION", "duration_days": 14, "description": "Ny guidance"},
                ],
                trigger_conditions=["inflation", "employment", "financial stress"],
                backoff_conditions=["Systemisk kris", "Politiskt tryck"],
                historical_frequency=0.90,
                market_impact={"SIGNAL": -0.5, "ACTION": -1.0, "RESOLUTION": +0.5},
            ),
        ],
        signal_phrases={
            "data dependent": "AVVAKTAR -- inget forandrat",
            "considerable progress": "SNART_AKTION -- ranteandring trolig",
            "patient": "HALLER_FAST -- ingen forandring planerad",
            "meeting by meeting": "OSAKER -- kan ga bada hall",
            "determined": "HOJNING_TROLIG -- hawkish signal",
            "appropriate": "STANDARD -- foljer planen",
            "closely monitoring": "BEREDD_AGERA -- redo att agera",
        },
        backoff_triggers=[
            {"trigger": "VIX >35 + kreditspreadar vidgas >100bps", "probability": 0.80, "response": "Emergency cut"},
            {"trigger": "Arbetsloshet +0.5% pa 3 manader", "probability": 0.70, "response": "Skiftar dovish"},
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
                description="Liknande Fed men med storre intern oenighet.",
                typical_duration_days=42,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 14, "description": "Lagarde-tal + ECB blogginlagg"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebeslut"},
                    {"phase": "RESOLUTION", "duration_days": 14, "description": "Ny guidance"},
                ],
                trigger_conditions=["eurozone CPI", "german industrial"],
                backoff_conditions=["European bank stress", "Italia-Tyskland spread"],
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
                description="Foljer i stort ECB men med lag till svensk data.",
                typical_duration_days=56,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 21, "description": "Protokoll + tal"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Rantebesked var 8:e vecka"},
                ],
                trigger_conditions=["KPIF", "SEK", "housing prices"],
                backoff_conditions=["SEK-kris", "housing collapse"],
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
                description="Manatliga moten. Beslutet lackar 1-2d fore.",
                typical_duration_days=30,
                phases=[
                    {"phase": "SIGNAL", "duration_days": 7, "description": "Lackor fran delegater"},
                    {"phase": "ACTION", "duration_days": 1, "description": "Officiellt beslut"},
                    {"phase": "MARKET_REACTION", "duration_days": 3, "description": "Oljepris reagerar"},
                ],
                trigger_conditions=["oil price <$70", "oil price >$100"],
                backoff_conditions=["US SPR release", "UAE internal conflict"],
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
# DEL 3: RETORISK ANALYSATOR (behalld fran v1 — 18/18 tester)
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
# DEL 4: ESCALATION TRACKER (NYTT i v2 — ersatter BehaviorMatcher)
# ============================================================

class EscalationTracker:
    """
    Raknar signal-ackumulering per aktor over tid.
    Ingen AI, ingen fasmatchning — bara matematik.

    Logik:
    - Sparar senaste 20 signaler per aktor
    - Om 3+ av senaste 10 ar ESCALATION och ratio > 2x DEESCALATION -> ESCALATING
    - Om 3+ av senaste 10 ar DEESCALATION -> DEESCALATING
    - Annars STABLE
    """

    def __init__(self):
        self.signals: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history = 20

    def track(self, actor_id: str, signal: Dict):
        """Lagg till en ny signal for en aktor."""
        signal["tracked_at"] = datetime.now().isoformat()
        self.signals[actor_id].append(signal)
        # Begrans historik
        if len(self.signals[actor_id]) > self._max_history:
            self.signals[actor_id] = self.signals[actor_id][-self._max_history:]

    def get_status(self, actor_id: str) -> Dict:
        """Hamta eskaleringssstatus for en aktor."""
        history = self.signals.get(actor_id, [])
        if not history:
            return {"status": "NO_DATA", "strength": 0, "signal_count": 0}

        recent = history[-10:]
        esc_count = sum(1 for s in recent if s.get("tone") == "ESCALATION")
        deesc_count = sum(1 for s in recent if s.get("tone") == "DEESCALATION")
        neutral_count = len(recent) - esc_count - deesc_count

        if esc_count >= 3 and esc_count > deesc_count * 2:
            status = "ESCALATING"
            strength = esc_count / len(recent)
        elif deesc_count >= 3 and deesc_count > esc_count * 2:
            status = "DEESCALATING"
            strength = deesc_count / len(recent)
        else:
            status = "STABLE"
            strength = 0

        return {
            "status": status,
            "strength": round(strength, 2),
            "signal_count": len(recent),
            "escalation_count": esc_count,
            "deescalation_count": deesc_count,
            "neutral_count": neutral_count,
            "latest_tone": recent[-1].get("tone", "NEUTRAL") if recent else "NEUTRAL",
        }

    def get_all_statuses(self) -> Dict[str, Dict]:
        """Hamta status for alla aktorer med signaler."""
        return {aid: self.get_status(aid) for aid in self.signals}

    def export(self) -> Dict:
        """Exportera for persistens."""
        return {aid: signals[-10:] for aid, signals in self.signals.items()}

    def load(self, data: Dict):
        """Ladda fran persistens."""
        for aid, signals in data.items():
            self.signals[aid] = signals


# ============================================================
# DEL 5: ENGINE (ORCHESTRATOR v2)
# ============================================================

class PoliticalIntelligenceEngine:
    """
    Orchestrator v2: Sentinel-driven politisk intelligens.

    v1: Analyserade ratt nyhetstext i 6h-pipeline -> AI predictions
    v2: Tar emot Sentinel-alerts (var 5 min) -> frasmatchning -> eskalationstracking
        Supervisor laser get_current_state() utan AI-anrop.
    """

    def __init__(self):
        self.actors = {a.id: a for a in create_default_actors()}
        self.rhetoric = RhetoricAnalyzer()
        self.tracker = EscalationTracker()
        self.active_signals: List[Dict] = []  # Senaste 50 politiska signaler
        self._max_signals = 50
        self._load()

    def _load(self):
        """Ladda historik fran KV-store eller fil."""
        try:
            from db import kv_get
            data = kv_get("political_intelligence_v2")
            if data:
                self.active_signals = data.get("signals", [])
                self.tracker.load(data.get("tracker", {}))
                return
        except Exception:
            pass
        if os.path.exists(POLITICAL_DATA_FILE):
            try:
                with open(POLITICAL_DATA_FILE, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.active_signals = data.get("signals", [])
                        self.tracker.load(data.get("tracker", {}))
                    elif isinstance(data, list):
                        # v1 format — ignore
                        pass
            except Exception:
                pass

    def _save(self):
        """Spara till KV-store eller fil."""
        data = {
            "signals": self.active_signals[-self._max_signals:],
            "tracker": self.tracker.export(),
        }
        try:
            from db import kv_set
            kv_set("political_intelligence_v2", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(POLITICAL_DATA_FILE, "w") as f:
                json.dump(data, f, default=str)

    # ----- PUBLIC API -----

    def get_active_actors(self) -> List[PoliticalActor]:
        return [a for a in self.actors.values() if a.active]

    def add_actor(self, actor: PoliticalActor):
        """Lagg till ny aktor (t.ex. vid presidentbyte)."""
        self.actors[actor.id] = actor
        logger.info(f"Added political actor: {actor.name}")

    def deactivate_actor(self, actor_id: str):
        """Inaktivera en aktor."""
        if actor_id in self.actors:
            self.actors[actor_id].active = False
            logger.info(f"Deactivated political actor: {actor_id}")

    def process_sentinel_alert(self, alert: Dict) -> Optional[Dict]:
        """
        HUVUDMETOD v2: Anropas av NewsSentinel vid impact >= 5.
        Matchar mot aktorer via signal_phrases.
        Returnerar political signal eller None.

        Sentinel-alert-format:
        {
            "title": "...",
            "impact_score": 7,
            "category": "geopolitics",
            "affected_assets": [{"id": "sp500", "direction": "down", "strength": "strong"}],
            "urgency": "critical",
        }
        """
        title = alert.get("title", "")
        if not title:
            return None

        best_match = None
        best_signals = 0

        for actor in self.get_active_actors():
            rhetoric = self.rhetoric.analyze_statement(actor, title)
            if rhetoric["n_signals"] > best_signals:
                best_signals = rhetoric["n_signals"]
                best_match = {
                    "actor_id": actor.id,
                    "actor_name": actor.name,
                    "tone": rhetoric["tone"],
                    "escalation_score": rhetoric["escalation_score"],
                    "matched_signals": rhetoric["matched_signals"],
                    "n_signals": rhetoric["n_signals"],
                    "sentinel_impact": alert.get("impact_score", 0),
                    "sentinel_urgency": alert.get("urgency", "routine"),
                    "sentinel_category": alert.get("category", "other"),
                    "affected_assets": alert.get("affected_assets", []),
                    "title": title,
                    "timestamp": datetime.now().isoformat(),
                }

        if best_match:
            # Spara signal och uppdatera tracker
            self.active_signals.append(best_match)
            if len(self.active_signals) > self._max_signals:
                self.active_signals = self.active_signals[-self._max_signals:]

            self.tracker.track(best_match["actor_id"], {
                "tone": best_match["tone"],
                "escalation_score": best_match["escalation_score"],
                "impact": best_match["sentinel_impact"],
            })

            self._save()
            logger.info(
                f"Political signal: {best_match['actor_name']} "
                f"tone={best_match['tone']} signals={best_match['n_signals']} "
                f"impact={best_match['sentinel_impact']}"
            )

        return best_match

    def get_current_state(self) -> Dict:
        """
        Anropas av pipeline:n (L3 PREDICTIVE).
        Returnerar ackumulerat politiskt tillstand — INGA AI-anrop.
        """
        # Samla eskalationsstatus per aktor
        actor_statuses = {}
        for actor in self.get_active_actors():
            status = self.tracker.get_status(actor.id)
            if status["status"] != "NO_DATA":
                actor_statuses[actor.id] = {
                    "name": actor.name,
                    "escalation": status["status"],
                    "strength": status["strength"],
                    "signal_count": status["signal_count"],
                    "latest_tone": status["latest_tone"],
                    "power": actor.power_concentration,
                    "transmission_assets": {
                        k.value if hasattr(k, 'value') else k: v
                        for k, v in actor.transmission_assets.items()
                    },
                }

        # Bedom overall political risk
        escalating_actors = [
            a for a in actor_statuses.values()
            if a["escalation"] == "ESCALATING"
        ]
        high_impact_recent = [
            s for s in self.active_signals[-20:]
            if s.get("sentinel_impact", 0) >= 7
        ]

        if len(escalating_actors) >= 2 or len(high_impact_recent) >= 3:
            political_risk = "HIGH"
        elif len(escalating_actors) >= 1 or len(high_impact_recent) >= 1:
            political_risk = "ELEVATED"
        else:
            political_risk = "NORMAL"

        # Bygg direct_signals for Supervisor (samma format som v1)
        direct_signals = []
        for actor_id, status in actor_statuses.items():
            if status["escalation"] in ("ESCALATING", "DEESCALATING"):
                # Samla alla affected_assets fran aktoren
                all_assets = set()
                for assets_list in status["transmission_assets"].values():
                    all_assets.update(assets_list)

                direct_signals.append({
                    "actor": status["name"],
                    "signal": status["escalation"],
                    "confidence": status["strength"],
                    "affected_assets": list(all_assets),
                })

        # Dominant actor
        dominant = None
        if actor_statuses:
            most_signals = max(actor_statuses.values(), key=lambda x: x["signal_count"])
            if most_signals["signal_count"] > 0:
                dominant = most_signals["name"]

        return {
            "timestamp": datetime.now().isoformat(),
            "political_risk": political_risk,
            "actor_statuses": actor_statuses,
            "direct_signals": direct_signals,
            "dominant_actor": dominant,
            "recent_signals": self.active_signals[-5:],
            "total_signals_tracked": len(self.active_signals),
        }

    def get_dashboard(self) -> Dict:
        """API-endpoint data for /api/political-intelligence."""
        state = self.get_current_state()
        return {
            "market_bias": self._compute_bias(),
            "political_risk": state["political_risk"],
            "active_actors": [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.actor_type.value if hasattr(a.actor_type, 'value') else a.actor_type,
                    "power_concentration": a.power_concentration,
                    "predictability": a.predictability,
                    "n_patterns": len(a.behavior_patterns),
                    "n_signal_phrases": len(a.signal_phrases),
                    "escalation": self.tracker.get_status(a.id),
                }
                for a in self.get_active_actors()
            ],
            "recent_signals": self.active_signals[-10:],
            "total_signals": len(self.active_signals),
            "dominant_actor": state["dominant_actor"],
        }

    def _compute_bias(self) -> Dict:
        """Aggregera marknadsbias fran senaste signalerna."""
        recent = self.active_signals[-20:]
        if not recent:
            return {"bias": "NEUTRAL", "confidence": 0, "escalation_ratio": 0.0, "entries_analyzed": 0, "overall_risk": "NORMAL"}

        esc = sum(1 for s in recent if s.get("tone") == "ESCALATION")
        deesc = sum(1 for s in recent if s.get("tone") == "DEESCALATION")
        total = len(recent)
        ratio = esc / max(total, 1)

        if esc > deesc + 2:
            bias = "BEARISH"
        elif deesc > esc + 2:
            bias = "BULLISH"
        else:
            bias = "NEUTRAL"

        return {
            "bias": bias,
            "confidence": round(abs(esc - deesc) / max(total, 1), 2),
            "escalation_ratio": round(ratio, 2),
            "entries_analyzed": total,
            "overall_risk": self.get_current_state()["political_risk"],
        }

    # Backwards-compatible methods

    def analyze_daily(self, news_summary: str, market_data: Dict) -> Dict:
        """
        v1-kompatibel metod. Anvands i pipeline om Sentinel inte kort an.
        Parser nyhetstext direkt (fallback).
        """
        for actor in self.get_active_actors():
            rhetoric = self.rhetoric.analyze_statement(actor, news_summary)
            if rhetoric["n_signals"] > 0:
                self.tracker.track(actor.id, {
                    "tone": rhetoric["tone"],
                    "escalation_score": rhetoric["escalation_score"],
                    "impact": 5,  # Default, no Sentinel score
                })
                self.active_signals.append({
                    "actor_id": actor.id,
                    "actor_name": actor.name,
                    "tone": rhetoric["tone"],
                    "n_signals": rhetoric["n_signals"],
                    "matched_signals": rhetoric["matched_signals"],
                    "sentinel_impact": 5,
                    "timestamp": datetime.now().isoformat(),
                    "title": news_summary[:100],
                })

        state = self.get_current_state()
        # Return v1-compatible format for main.py
        return {
            "timestamp": state["timestamp"],
            "actors_analyzed": [
                {
                    "actor": a.id, "name": a.name,
                    "rhetoric_tone": self.tracker.get_status(a.id).get("latest_tone", "NEUTRAL"),
                    "tonal_shift": self.tracker.get_status(a.id).get("status", "STABLE"),
                    "pattern_matches": 0,
                    "signals_detected": self.tracker.get_status(a.id).get("signal_count", 0),
                }
                for a in self.get_active_actors()
            ],
            "prompts_for_ai": [],  # v2: no AI prompts
            "direct_signals": state["direct_signals"],
            "dominant_actor": state["dominant_actor"],
            "overall_political_risk": state["political_risk"],
        }

    def process_ai_predictions(self, actor_id: str, ai_response: Dict) -> Dict:
        """v1-kompatibel stub. v2 gor inga AI-predictions."""
        return {"actor": actor_id, "predictions": [], "note": "v2: AI predictions removed"}
