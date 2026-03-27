# ============================================================
# FIL: backend/predictive/event_detector.py
#
# HJÄRNA: AI-modellen som autonomt bestämmer VAD som behöver
# kausal analys. Detekterar, klassificerar och prioriterar
# händelser från alla datakällor.
#
# TRE DETEKTIONSMETODER:
# 1. AI-analys av nyheter/agentoutput (kvalitativ)
# 2. Prisavvikelse >2 sigma (kvantitativ)
# 3. Agent-divergens (konsensusförändring)
# ============================================================

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import logging

logger = logging.getLogger(__name__)

EVENT_LOG_FILE = "data/detected_events.json"


class EventSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOISE = "NOISE"


class EventCategory(str, Enum):
    GEOPOLITICAL = "GEOPOLITICAL"
    MONETARY_POLICY = "MONETARY_POLICY"
    MACRO_DATA = "MACRO_DATA"
    CORPORATE = "CORPORATE"
    COMMODITY = "COMMODITY"
    MARKET_STRUCTURE = "MARKET_STRUCTURE"
    REGULATORY = "REGULATORY"
    SENTIMENT_SHIFT = "SENTIMENT_SHIFT"


@dataclass
class DetectedEvent:
    id: str
    timestamp: str
    title: str
    description: str
    severity: str
    category: str
    affected_assets: List[str]
    estimated_impact: Dict[str, float]
    source: str
    requires_causal_chain: bool
    requires_event_tree: bool
    chain_id: Optional[str] = None
    tree_id: Optional[str] = None
    processed: bool = False
    duplicate_of: Optional[str] = None


class EventDetector:
    """
    Autonom händelsedetektor som bestämmer vad som behöver
    djup kausal analys.
    """

    def __init__(self):
        self.detected_events: List[DetectedEvent] = []
        self.event_hashes: set = set()
        self._load()

    def _load(self):
        try:
            from db import kv_get
            data = kv_get("detected_events")
            if data:
                self.detected_events = [DetectedEvent(**e) for e in data[-500:]]
                self.event_hashes = {self._hash_event(e.title) for e in self.detected_events}
                return
        except Exception:
            pass
        if os.path.exists(EVENT_LOG_FILE):
            try:
                with open(EVENT_LOG_FILE, "r") as f:
                    data = json.load(f)
                    self.detected_events = [DetectedEvent(**e) for e in data[-500:]]
                    self.event_hashes = {self._hash_event(e.title) for e in self.detected_events}
            except Exception as e:
                logger.error(f"Failed to load events: {e}")

    def _save(self):
        data = [asdict(e) for e in self.detected_events[-500:]]
        try:
            from db import kv_set
            kv_set("detected_events", data)
        except Exception:
            os.makedirs(os.path.dirname(EVENT_LOG_FILE), exist_ok=True)
            with open(EVENT_LOG_FILE, "w") as f:
                json.dump(data, f, default=str)

    def _hash_event(self, title: str) -> str:
        normalized = title.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    # ================================================================
    # METOD 1: AI-BASERAD NYHETS/AGENTANALYS
    # ================================================================

    def build_detection_prompt(
        self,
        news_summary: str,
        agent_outputs: Dict[str, str],
        recent_prices: Dict[str, float],
        existing_chains: List[str]
    ) -> str:
        existing_str = "\n".join([f"- {c}" for c in existing_chains]) if existing_chains else "Inga aktiva kedjor."

        agent_str = ""
        for agent_name, output in agent_outputs.items():
            agent_str += f"\n{agent_name}: {output[:200]}"

        return f"""Du är en händelsedetekterings-AI. Din uppgift är att identifiera
VIKTIGA händelser som kräver djupare analys.

AKTUELLA NYHETER:
{news_summary[:2000]}

AGENT-ANALYSER:{agent_str}

PRISRÖRELSER (senaste 24h):
{json.dumps(recent_prices, indent=2)}

REDAN AKTIVA KAUSALA KEDJOR (undvik duplicering):
{existing_str}

Svara ENBART med JSON:
{{
    "detected_events": [
        {{
            "title": "Kort titel max 10 ord",
            "description": "Beskrivning max 50 ord",
            "severity": "CRITICAL|HIGH|MEDIUM|LOW|NOISE",
            "category": "GEOPOLITICAL|MONETARY_POLICY|MACRO_DATA|CORPORATE|COMMODITY|MARKET_STRUCTURE|REGULATORY|SENTIMENT_SHIFT",
            "affected_assets": ["OIL", "GOLD", "SP500"],
            "estimated_impact": {{"OIL": 10.0, "SP500": -3.0}},
            "source": "nyheter|prisrorelse|agent_divergens|makrodata",
            "requires_causal_chain": true,
            "requires_event_tree": false,
            "reasoning": "Varför detta är viktigt max 25 ord",
            "is_new": true
        }}
    ],
    "overall_market_stress": 5,
    "recommended_analysis_depth": "FULL|STANDARD|MINIMAL"
}}

REGLER:
- CRITICAL: Regimskifte, krig, finanskris → ALLTID kausal kedja + event tree
- HIGH: Centralbanksbesked, stor prisrörelse (>3% index) → kausal kedja
- MEDIUM: Viktig nyhet med potentiell påverkan → enkel analys
- LOW/NOISE: Logga men analysera ej
- is_new: false om händelsen redan täcks av en aktiv kedja
- estimated_impact i PROCENT
- Max 5 events per analys
- BARA JSON"""

    def parse_detection_response(self, ai_response: Dict) -> List[DetectedEvent]:
        """Parsar AI-svar och skapar DetectedEvent-objekt"""
        new_events = []

        for event_data in ai_response.get("detected_events", []):
            title = event_data.get("title", "")
            event_hash = self._hash_event(title)

            if event_hash in self.event_hashes:
                if not event_data.get("is_new", True):
                    continue

            severity = event_data.get("severity", "MEDIUM")

            requires_chain = event_data.get("requires_causal_chain", False)
            requires_tree = event_data.get("requires_event_tree", False)

            if severity == "CRITICAL":
                requires_chain = True
                requires_tree = True
            elif severity == "HIGH":
                requires_chain = True

            event = DetectedEvent(
                id=f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{event_hash[:6]}",
                timestamp=datetime.now().isoformat(),
                title=title,
                description=event_data.get("description", ""),
                severity=severity,
                category=event_data.get("category", "MACRO_DATA"),
                affected_assets=event_data.get("affected_assets", []),
                estimated_impact=event_data.get("estimated_impact", {}),
                source=event_data.get("source", "ai_detection"),
                requires_causal_chain=requires_chain,
                requires_event_tree=requires_tree,
            )

            self.detected_events.append(event)
            self.event_hashes.add(event_hash)
            new_events.append(event)

        self._save()
        return new_events

    # ================================================================
    # METOD 2: PRISAVVIKELSE-DETEKTION (KVANTITATIV)
    # ================================================================

    def detect_price_anomalies(
        self,
        current_prices: Dict[str, float],
        historical_returns_std: Dict[str, float],
        daily_returns: Dict[str, float],
        z_threshold: float = 2.0
    ) -> List[DetectedEvent]:
        anomaly_events = []

        for asset, daily_return in daily_returns.items():
            std = historical_returns_std.get(asset, 0.02)
            if std < 0.001:
                continue

            z_score = abs(daily_return) / std

            if z_score < z_threshold:
                continue

            if z_score > 4.0:
                severity = "CRITICAL"
            elif z_score > 3.0:
                severity = "HIGH"
            elif z_score > 2.5:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            direction = "steg" if daily_return > 0 else "föll"
            pct = abs(daily_return) * 100

            title = f"{asset} {direction} {pct:.1f}% ({z_score:.1f} sigma)"
            event_hash = self._hash_event(f"{asset}_{datetime.now().strftime('%Y%m%d')}")

            if event_hash in self.event_hashes:
                continue

            event = DetectedEvent(
                id=f"price_{datetime.now().strftime('%Y%m%d')}_{asset}",
                timestamp=datetime.now().isoformat(),
                title=title,
                description=f"{asset} rörde sig {z_score:.1f} standardavvikelser. "
                            f"Normal daglig rörelse: +/-{std*100:.1f}%. Idag: {daily_return*100:+.1f}%.",
                severity=severity,
                category="MARKET_STRUCTURE",
                affected_assets=[asset],
                estimated_impact={asset: round(daily_return * 100, 2)},
                source="price_anomaly",
                requires_causal_chain=severity in ("CRITICAL", "HIGH"),
                requires_event_tree=severity == "CRITICAL",
            )

            self.detected_events.append(event)
            self.event_hashes.add(event_hash)
            anomaly_events.append(event)

        if anomaly_events:
            self._save()

        return anomaly_events

    # ================================================================
    # METOD 3: AGENT-DIVERGENS-DETEKTION
    # ================================================================

    def detect_agent_divergence(
        self,
        current_scores: Dict[str, Dict[str, float]],
        previous_scores: Dict[str, Dict[str, float]],
        divergence_threshold: float = 3.0
    ) -> List[DetectedEvent]:
        divergence_events = []

        if not previous_scores:
            return []

        all_assets = set()
        for scores in current_scores.values():
            all_assets.update(scores.keys())

        for asset in all_assets:
            changes = []

            for agent in current_scores:
                curr = current_scores[agent].get(asset, 0)
                prev = previous_scores.get(agent, {}).get(asset, 0)
                changes.append(abs(curr - prev))

            if not changes:
                continue

            max_change = max(changes)
            avg_change = sum(changes) / len(changes)

            if avg_change > divergence_threshold:
                current_vals = [current_scores[a].get(asset, 0) for a in current_scores]
                previous_vals = [previous_scores.get(a, {}).get(asset, 0) for a in current_scores]
                direction = "POSITIV" if sum(current_vals) > sum(previous_vals) else "NEGATIV"

                event = DetectedEvent(
                    id=f"divergence_{datetime.now().strftime('%Y%m%d')}_{asset}",
                    timestamp=datetime.now().isoformat(),
                    title=f"Agenter skiftar {direction} på {asset} ({avg_change:.1f} snittändring)",
                    description=f"Agenter ändrade sina scores för {asset} kraftigt. "
                                f"Snittändring: {avg_change:.1f}. Störst: {max_change:.1f}.",
                    severity="HIGH" if avg_change > 5 else "MEDIUM",
                    category="SENTIMENT_SHIFT",
                    affected_assets=[asset],
                    estimated_impact={asset: round(avg_change * (1 if direction == "POSITIV" else -1), 1)},
                    source="agent_divergence",
                    requires_causal_chain=avg_change > 5,
                    requires_event_tree=False,
                )

                divergence_events.append(event)
                self.detected_events.append(event)

        if divergence_events:
            self._save()

        return divergence_events

    # ================================================================
    # FULL DETECTION (alla 3 metoder)
    # ================================================================

    def run_full_detection(
        self,
        news_summary: str,
        agent_outputs: Dict[str, str],
        recent_prices: Dict[str, float],
        daily_returns: Dict[str, float],
        historical_std: Dict[str, float],
        current_agent_scores: Dict[str, Dict[str, float]],
        previous_agent_scores: Dict[str, Dict[str, float]],
        existing_chain_titles: List[str]
    ) -> Dict:
        all_events = []

        # Metod 1: AI prompt (returneras för extern AI-anrop)
        prompt = self.build_detection_prompt(
            news_summary, agent_outputs, recent_prices, existing_chain_titles
        )

        # Metod 2: Prisavvikelser
        price_events = self.detect_price_anomalies(
            recent_prices, historical_std, daily_returns
        )
        all_events.extend(price_events)

        # Metod 3: Agent-divergens
        divergence_events = self.detect_agent_divergence(
            current_agent_scores, previous_agent_scores
        )
        all_events.extend(divergence_events)

        prioritized = self._prioritize_events(all_events)

        needs_chain = [e for e in prioritized if e.requires_causal_chain and not e.processed]
        needs_tree = [e for e in prioritized if e.requires_event_tree and not e.processed]

        return {
            "ai_detection_prompt": prompt,
            "auto_detected_events": [asdict(e) for e in all_events],
            "prioritized": [asdict(e) for e in prioritized],
            "trigger_causal_chains": [
                {"event_id": e.id, "title": e.title, "severity": e.severity}
                for e in needs_chain[:3]
            ],
            "trigger_event_trees": [
                {"event_id": e.id, "title": e.title, "severity": e.severity}
                for e in needs_tree[:2]
            ],
            "total_detected": len(all_events),
            "critical_count": sum(1 for e in all_events if e.severity == "CRITICAL"),
            "high_count": sum(1 for e in all_events if e.severity == "HIGH"),
        }

    def _prioritize_events(self, events: List[DetectedEvent]) -> List[DetectedEvent]:
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NOISE": 4}
        return sorted(events, key=lambda e: severity_order.get(e.severity, 5))

    def mark_processed(self, event_id: str, chain_id: str = None, tree_id: str = None):
        for event in self.detected_events:
            if event.id == event_id:
                event.processed = True
                event.chain_id = chain_id
                event.tree_id = tree_id
        self._save()

    def get_unprocessed(self) -> List[DetectedEvent]:
        return [e for e in self.detected_events
                if not e.processed
                and e.severity in ("CRITICAL", "HIGH")
                and e.requires_causal_chain]

    def get_statistics(self) -> Dict:
        if not self.detected_events:
            return {"total": 0, "last_30_days": 0}

        recent = [e for e in self.detected_events
                  if (datetime.now() - datetime.fromisoformat(e.timestamp)).days <= 30]

        return {
            "total_all_time": len(self.detected_events),
            "last_30_days": len(recent),
            "by_severity": {
                s: sum(1 for e in recent if e.severity == s)
                for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NOISE"]
            },
            "by_category": {
                c: sum(1 for e in recent if e.category == c)
                for c in set(e.category for e in recent) if recent
            },
            "by_source": {
                s: sum(1 for e in recent if e.source == s)
                for s in set(e.source for e in recent) if recent
            },
            "processed_rate": round(
                sum(1 for e in recent if e.processed) / max(len(recent), 1), 2
            ),
            "chains_triggered": sum(1 for e in recent if e.chain_id),
            "trees_triggered": sum(1 for e in recent if e.tree_id),
        }
