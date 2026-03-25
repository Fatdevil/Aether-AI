# ============================================================
# FIL: backend/predictive/narrative_tracker.py
# Spårar marknadens dominanta narrativ och bedömer
# var i livscykeln de befinner sig
#
# Livscykel: Uppkomst → Acceleration → Konsensus → Reversal
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

NARRATIVE_FILE = "data/narratives.json"


class NarrativePhase:
    EMERGENCE = "EMERGENCE"
    ACCELERATION = "ACCELERATION"
    CONSENSUS = "CONSENSUS"
    EXTREME = "EXTREME_CONSENSUS"
    REVERSAL = "REVERSAL"


@dataclass
class Narrative:
    id: str
    title: str
    description: str
    created_date: str
    phase: str
    consensus_pct: float
    affected_assets: List[str]
    direction: str
    days_active: int
    peak_consensus: float
    sentiment_momentum: float
    contrarian_signal: bool
    history: List[Dict]
    status: str = "ACTIVE"


class NarrativeTracker:
    """
    Spårar och analyserar marknadens narrativ.

    KEY INSIGHT: När alla är överens om ett narrativ är det ofta
    för sent. Trendföljning fungerar i ACCELERATION-fasen.
    Kontrarianism fungerar i EXTREME-fasen.
    """

    def __init__(self):
        self.narratives: List[Narrative] = []
        self._load()

    def _load(self):
        if os.path.exists(NARRATIVE_FILE):
            try:
                with open(NARRATIVE_FILE, "r") as f:
                    data = json.load(f)
                    self.narratives = [Narrative(**n) for n in data]
            except Exception:
                pass

    def _save(self):
        os.makedirs(os.path.dirname(NARRATIVE_FILE), exist_ok=True)
        with open(NARRATIVE_FILE, "w") as f:
            json.dump([asdict(n) for n in self.narratives[-100:]], f, default=str)

    def build_narrative_prompt(self, market_context: str) -> str:
        """Prompt för AI att identifiera aktiva narrativ"""
        existing = [f"- {n.title} ({n.phase}, {n.consensus_pct}%)" for n in self.narratives if n.status == "ACTIVE"]
        existing_str = "\n".join(existing) if existing else "Inga tidigare narrativ."

        return f"""Analysera aktuella marknadsnarrativ. Identifiera 3-5 dominerande
narrativ som driver marknaden just nu.

MARKNADSKONTEXT:
{market_context}

BEFINTLIGA NARRATIV:
{existing_str}

Svara ENBART med JSON:
{{
    "narratives": [
        {{
            "title": "Kort titel (t.ex. 'AI-revolutionen')",
            "description": "Max 30 ord beskrivning",
            "consensus_pct": 65,
            "affected_assets": ["XLK", "SP500"],
            "direction": "BULLISH",
            "phase": "CONSENSUS",
            "momentum": 0.5,
            "reasoning": "Varför denna fas max 20 ord",
            "contrarian_view": "Vad kontrarianen tänker max 20 ord",
            "historical_parallel": "Liknande narrativ från historien max 15 ord"
        }}
    ],
    "dominant_narrative": "Det enskilt viktigaste narrativet just nu",
    "narrative_risk": "Vad som händer om det dominerande narrativet bryts max 25 ord"
}}

REGLER:
- consensus_pct: 0-100, realistiskt
- phase: EMERGENCE (<20%) / ACCELERATION (20-50%) / CONSENSUS (50-80%) / EXTREME_CONSENSUS (>80%)
- momentum: -1.0 (avtar snabbt) till +1.0 (accelererar snabbt)
- BARA JSON"""

    def update_narratives(self, ai_response: Dict):
        """Uppdatera narrativ-databas med AI-analys"""
        for narr_data in ai_response.get("narratives", []):
            title = narr_data.get("title", "")

            # Kolla om narrativet redan finns
            existing = None
            for n in self.narratives:
                if n.title.lower() == title.lower() and n.status == "ACTIVE":
                    existing = n
                    break

            if existing:
                old_consensus = existing.consensus_pct
                new_consensus = float(narr_data.get("consensus_pct", old_consensus))

                existing.consensus_pct = new_consensus
                existing.phase = narr_data.get("phase", existing.phase)
                existing.sentiment_momentum = float(narr_data.get("momentum", 0))
                existing.days_active = (datetime.now() - datetime.fromisoformat(existing.created_date)).days
                existing.peak_consensus = max(existing.peak_consensus, new_consensus)
                existing.contrarian_signal = new_consensus > 80 or (
                    existing.peak_consensus > 70 and new_consensus < existing.peak_consensus - 10
                )
                existing.history.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "consensus": new_consensus,
                    "phase": existing.phase
                })

                # Detektera reversal
                if existing.peak_consensus > 60 and new_consensus < existing.peak_consensus - 20:
                    existing.phase = NarrativePhase.REVERSAL
                    existing.contrarian_signal = True
            else:
                new_narrative = Narrative(
                    id=f"narr_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.narratives)}",
                    title=title,
                    description=narr_data.get("description", ""),
                    created_date=datetime.now().isoformat(),
                    phase=narr_data.get("phase", NarrativePhase.EMERGENCE),
                    consensus_pct=float(narr_data.get("consensus_pct", 30)),
                    affected_assets=narr_data.get("affected_assets", []),
                    direction=narr_data.get("direction", "NEUTRAL"),
                    days_active=0,
                    peak_consensus=float(narr_data.get("consensus_pct", 30)),
                    sentiment_momentum=float(narr_data.get("momentum", 0)),
                    contrarian_signal=False,
                    history=[{
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "consensus": float(narr_data.get("consensus_pct", 30)),
                        "phase": narr_data.get("phase", NarrativePhase.EMERGENCE)
                    }]
                )
                self.narratives.append(new_narrative)

        self._save()

    def get_trading_signals(self) -> List[Dict]:
        """
        Generera tradingsignaler baserat på narrativ-livscykel.

        ACCELERATION → Trendföljning (köp det narrativet gynnar)
        CONSENSUS → Försiktig (börja ta vinst)
        EXTREME → Kontrarian (ta motsatt position)
        REVERSAL → Stark kontrarian
        """
        signals = []

        for narr in self.narratives:
            if narr.status != "ACTIVE":
                continue

            if narr.phase == NarrativePhase.ACCELERATION and narr.sentiment_momentum > 0.3:
                signals.append({
                    "narrative": narr.title,
                    "phase": narr.phase,
                    "action": "TRENDFÖLJNING",
                    "direction": narr.direction,
                    "assets": narr.affected_assets,
                    "strength": "MEDEL",
                    "reasoning": f"Narrativ i acceleration ({narr.consensus_pct:.0f}% consensus, momentum +{narr.sentiment_momentum:.1f}). Trendföljning."
                })

            elif narr.phase == NarrativePhase.CONSENSUS:
                signals.append({
                    "narrative": narr.title,
                    "phase": narr.phase,
                    "action": "MINSKA",
                    "direction": "NEUTRAL",
                    "assets": narr.affected_assets,
                    "strength": "MEDEL",
                    "reasoning": f"Narrativ i konsensus ({narr.consensus_pct:.0f}%). Potentialen är begränsad. Börja ta vinst."
                })

            elif narr.phase in (NarrativePhase.EXTREME, NarrativePhase.REVERSAL):
                opposite = "BEARISH" if narr.direction == "BULLISH" else "BULLISH"
                signals.append({
                    "narrative": narr.title,
                    "phase": narr.phase,
                    "action": "KONTRARIAN",
                    "direction": opposite,
                    "assets": narr.affected_assets,
                    "strength": "STARK" if narr.phase == NarrativePhase.REVERSAL else "MEDEL",
                    "reasoning": f"Narrativ i {'reversal' if narr.phase == NarrativePhase.REVERSAL else 'extrem konsensus'} "
                                 f"({narr.consensus_pct:.0f}%, peak {narr.peak_consensus:.0f}%). Kontrarian-position rekommenderas."
                })

            elif narr.contrarian_signal:
                signals.append({
                    "narrative": narr.title,
                    "phase": narr.phase,
                    "action": "VARNING",
                    "direction": "NEUTRAL",
                    "assets": narr.affected_assets,
                    "strength": "LÅG",
                    "reasoning": f"Kontrarian-signal: consensus faller från topp ({narr.peak_consensus:.0f}% → {narr.consensus_pct:.0f}%). Bevaka."
                })

        return signals

    def get_dashboard(self) -> Dict:
        """Komplett narrativ-dashboard"""
        active = [n for n in self.narratives if n.status == "ACTIVE"]

        phase_icons = {
            NarrativePhase.EMERGENCE: "🌱",
            NarrativePhase.ACCELERATION: "🚀",
            NarrativePhase.CONSENSUS: "⚠️",
            NarrativePhase.EXTREME: "🔴",
            NarrativePhase.REVERSAL: "💥"
        }

        return {
            "active_narratives": len(active),
            "narratives": [
                {
                    "title": n.title,
                    "phase": n.phase,
                    "consensus_pct": n.consensus_pct,
                    "direction": n.direction,
                    "days_active": n.days_active,
                    "momentum": n.sentiment_momentum,
                    "contrarian_signal": n.contrarian_signal,
                    "assets": n.affected_assets,
                    "peak_consensus": n.peak_consensus,
                    "phase_icon": phase_icons.get(n.phase, "❓")
                }
                for n in sorted(active, key=lambda x: x.consensus_pct, reverse=True)
            ],
            "signals": self.get_trading_signals(),
            "risk_level": self._assess_narrative_risk(active)
        }

    def _assess_narrative_risk(self, active: List[Narrative]) -> Dict:
        """Bedöm systemisk narrativ-risk"""
        extreme_count = sum(1 for n in active if n.phase in (NarrativePhase.EXTREME, NarrativePhase.REVERSAL))
        avg_consensus = sum(n.consensus_pct for n in active) / max(len(active), 1)

        if extreme_count >= 2 or avg_consensus > 75:
            return {"level": "HÖG", "message": "Flera narrativ i extremfas. Reversal-risk hög. Öka kassa."}
        elif extreme_count >= 1 or avg_consensus > 60:
            return {"level": "FÖRHÖJD", "message": "Narrativ i konsensus. Potentialen begränsad. Var selektiv."}
        else:
            return {"level": "NORMAL", "message": "Narrativ i tidig fas. Normal trendföljnings-environment."}
