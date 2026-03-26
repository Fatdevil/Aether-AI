"""
Supervisor Context Builder — Aggregates ALL intelligence for Supervisor V2.

Collects data from:
1. Agent results (macro, micro, sentiment, tech)
2. Regime Detector (risk-on/off, inflation/deflation)
3. Event Detector (geopolitical, monetary policy, etc.)
4. Narrative Tracker (market narrative phases)
5. Historical analyses (previous supervisor summaries)
6. Accuracy metrics (how well the system has performed)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import json

logger = logging.getLogger("aether.supervisor_context")


class SupervisorContextBuilder:
    """Builds comprehensive context for Supervisor V2 decisions."""

    def __init__(self, analysis_store=None):
        self.store = analysis_store

    def build_full_context(
        self,
        asset_id: str,
        asset_name: str,
        category: str,
        price_data: dict,
        agent_results: dict,
    ) -> dict:
        """Build complete context package for Supervisor."""
        context = {
            "regime": self._get_regime_context(),
            "active_events": self._get_event_context(),
            "narratives": self._get_narrative_context(),
            "previous_analyses": self._get_history_context(asset_id),
            "previous_summary": self._get_latest_supervisor_summary(),
            "accuracy": self._get_accuracy_context(),
        }
        # Also build the formatted prompt string
        context["formatted_prompt"] = self._format_for_prompt(
            asset_id, asset_name, category, price_data, agent_results, context
        )
        return context

    # ==================== Data Collectors ====================

    def _get_regime_context(self) -> dict:
        """Get current market regime from RegimeDetector."""
        try:
            from regime_detector import regime_detector
            regime = regime_detector.detect_regime()
            return {
                "current": regime.get("regime", "unknown"),
                "label": regime.get("label", ""),
                "confidence": regime.get("confidence", 0),
                "description": regime.get("description", ""),
                "vix": regime.get("signals", {}).get("vix", {}).get("level"),
                "yield_curve": regime.get("signals", {}).get("yield_curve", {}).get("spread"),
            }
        except Exception as e:
            logger.warning(f"Regime context failed: {e}")
            return {"current": "unknown", "label": "Okänt", "confidence": 0}

    def _get_event_context(self) -> dict:
        """Get active events from EventDetector."""
        try:
            from predictive.event_detector import EventDetector
            detector = EventDetector()
            stats = detector.get_statistics()
            unprocessed = detector.get_unprocessed()

            # Get recent HIGH/CRITICAL events
            recent_critical = [
                {"title": e.title, "severity": e.severity, "category": e.category}
                for e in unprocessed[:5]
            ]

            return {
                "total_30d": stats.get("last_30_days", 0),
                "critical_count": stats.get("by_severity", {}).get("CRITICAL", 0),
                "high_count": stats.get("by_severity", {}).get("HIGH", 0),
                "recent_events": recent_critical,
                "market_stress": stats.get("total_all_time", 0),
            }
        except Exception as e:
            logger.warning(f"Event context failed: {e}")
            return {"total_30d": 0, "critical_count": 0, "high_count": 0, "recent_events": []}

    def _get_narrative_context(self) -> dict:
        """Get active narratives from NarrativeTracker."""
        try:
            from predictive.narrative_tracker import NarrativeTracker
            tracker = NarrativeTracker()
            active = [n for n in tracker.narratives if n.status == "ACTIVE"]

            narratives = []
            for n in active[:5]:
                narratives.append({
                    "title": n.title,
                    "phase": n.phase,
                    "consensus_pct": n.consensus_pct,
                    "direction": n.direction,
                    "days_active": n.days_active,
                    "contrarian_signal": n.contrarian_signal,
                })

            return {
                "count": len(active),
                "narratives": narratives,
                "has_contrarian_signals": any(n.contrarian_signal for n in active),
            }
        except Exception as e:
            logger.warning(f"Narrative context failed: {e}")
            return {"count": 0, "narratives": [], "has_contrarian_signals": False}

    def _get_history_context(self, asset_id: str) -> dict:
        """Get previous analyses for this asset from DB."""
        if not self.store:
            return {"previous": [], "trend_direction": "unknown"}

        try:
            history = self.store.get_analysis_history(asset_id, limit=3)
            previous = []
            for h in history:
                previous.append({
                    "timestamp": h.get("timestamp", ""),
                    "score": h.get("final_score", 0),
                    "recommendation": h.get("recommendation", ""),
                    "text": (h.get("supervisor_text", "") or "")[:200],
                    "price": h.get("price_at_analysis", 0),
                })

            # Calculate trend: are scores improving or declining?
            if len(previous) >= 2:
                recent = previous[0].get("score", 0)
                older = previous[-1].get("score", 0)
                diff = recent - older
                if diff > 2:
                    trend = "improving"
                elif diff < -2:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "unknown"

            return {"previous": previous, "trend_direction": trend}
        except Exception as e:
            logger.warning(f"History context failed: {e}")
            return {"previous": [], "trend_direction": "unknown"}

    def _get_latest_supervisor_summary(self) -> dict:
        """Get the most recent supervisor summary for continuity."""
        if not self.store:
            return {}

        try:
            summaries = self.store.get_recent_summaries(n=1)
            if summaries:
                s = summaries[0]
                return {
                    "timestamp": s.get("timestamp", ""),
                    "mood": s.get("mood", ""),
                    "text": s.get("summary_text", ""),
                    "overall_score": s.get("overall_score", 0),
                    "regime": s.get("regime", ""),
                }
        except Exception as e:
            logger.debug(f"Previous summary not available: {e}")
        return {}

    def _get_accuracy_context(self) -> dict:
        """Get system accuracy metrics."""
        if not self.store:
            return {"available": False}

        try:
            summary_24h = self.store.get_evaluation_summary("24h")
            summary_7d = self.store.get_evaluation_summary("7d")

            return {
                "available": True,
                "accuracy_24h": summary_24h.get("accuracy", 0),
                "total_24h": summary_24h.get("total", 0),
                "accuracy_7d": summary_7d.get("accuracy", 0),
                "total_7d": summary_7d.get("total", 0),
            }
        except Exception as e:
            logger.debug(f"Accuracy context not available: {e}")
            return {"available": False}

    # ==================== Prompt Formatter ====================

    def _format_for_prompt(
        self,
        asset_id: str,
        asset_name: str,
        category: str,
        price_data: dict,
        agent_results: dict,
        context: dict,
    ) -> str:
        """Format all context into a structured prompt block for the LLM."""
        sections = []

        # --- Regime ---
        regime = context.get("regime", {})
        if regime.get("current") != "unknown":
            vix_str = f", VIX: {regime['vix']}" if regime.get("vix") else ""
            yc_str = f", Räntekurva: {regime['yield_curve']:+.2f}%" if regime.get("yield_curve") is not None else ""
            sections.append(
                f"MARKNADSREGIM: {regime['label']} (konfidens: {regime.get('confidence', 0):.0%})\n"
                f"  {regime.get('description', '')}{vix_str}{yc_str}"
            )

        # --- Events ---
        events = context.get("active_events", {})
        if events.get("recent_events"):
            event_lines = []
            for e in events["recent_events"][:3]:
                event_lines.append(f"  • [{e['severity']}] {e['title']}")
            sections.append(
                f"AKTIVA HÄNDELSER ({events.get('total_30d', 0)} senaste 30d, "
                f"{events.get('critical_count', 0)} kritiska):\n" + "\n".join(event_lines)
            )

        # --- Narratives ---
        narr = context.get("narratives", {})
        if narr.get("narratives"):
            narr_lines = []
            for n in narr["narratives"][:3]:
                contrarian = " ⚠️ KONTRÄR" if n.get("contrarian_signal") else ""
                narr_lines.append(
                    f"  • \"{n['title']}\" — fas: {n['phase']}, "
                    f"konsensus: {n['consensus_pct']:.0f}%, "
                    f"riktning: {n['direction']}{contrarian}"
                )
            sections.append("AKTIVA NARRATIV:\n" + "\n".join(narr_lines))

        # --- Previous analyses ---
        hist = context.get("previous_analyses", {})
        if hist.get("previous"):
            prev = hist["previous"][0]  # Most recent
            time_ago = ""
            try:
                prev_time = datetime.fromisoformat(prev["timestamp"])
                delta = datetime.now(timezone.utc) - prev_time
                hours = delta.total_seconds() / 3600
                if hours < 24:
                    time_ago = f"(för {hours:.0f}h sedan)"
                else:
                    time_ago = f"(för {delta.days}d sedan)"
            except Exception:
                pass

            sections.append(
                f"FÖREGÅENDE ANALYS AV {asset_name.upper()} {time_ago}:\n"
                f"  Poäng: {prev.get('score', 0):+.1f}, Rek: {prev.get('recommendation', '?')}, "
                f"Pris: {prev.get('price', 0):,.2f}\n"
                f"  Text: \"{prev.get('text', 'N/A')}\"\n"
                f"  Trend sedan dess: {hist.get('trend_direction', 'okänt')}"
            )

        # --- Previous global summary ---
        prev_summary = context.get("previous_summary", {})
        if prev_summary.get("text"):
            sections.append(
                f"SENASTE GLOBALA SUPERVISOR-SUMMERING:\n"
                f"  Mood: {prev_summary.get('mood', '?')}, "
                f"Regime: {prev_summary.get('regime', '?')}\n"
                f"  \"{prev_summary['text'][:300]}\""
            )

        # --- Accuracy ---
        acc = context.get("accuracy", {})
        if acc.get("available") and acc.get("total_24h", 0) > 0:
            sections.append(
                f"SYSTEMETS TRÄFFSÄKERHET:\n"
                f"  24h: {acc.get('accuracy_24h', 0):.0f}% "
                f"({acc.get('total_24h', 0)} prediktioner)\n"
                f"  7d: {acc.get('accuracy_7d', 0):.0f}% "
                f"({acc.get('total_7d', 0)} prediktioner)"
            )

        if not sections:
            return ""


        return "\n\n".join(sections)
