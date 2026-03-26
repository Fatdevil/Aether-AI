"""
Supervisor Context Builder V3 — Aggregates ALL intelligence for Supervisor.

Collects data from ALL 10 modules:
1. Agent results (macro, micro, sentiment, tech)
2. Regime Detector (risk-on/off, inflation/deflation)
3. Event Detector (geopolitical, monetary policy, etc.)
4. Narrative Tracker (market narrative phases)
5. Causal Chain Engine (event → consequence chains)
6. Event Tree Builder (branching probability scenarios)
7. Lead-Lag Detector (predictive cross-asset signals)
8. Economic Calendar (upcoming scheduled events)
9. Meta Strategy (method performance per regime)
10. Historical analyses + accuracy metrics
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
            # Original V2 modules
            "regime": self._get_regime_context(),
            "active_events": self._get_event_context(),
            "narratives": self._get_narrative_context(),
            "previous_analyses": self._get_history_context(asset_id),
            "previous_summary": self._get_latest_supervisor_summary(),
            "accuracy": self._get_accuracy_context(),
            # NEW: Full predict modules
            "causal_chains": self._get_causal_chains_context(),
            "event_trees": self._get_event_trees_context(),
            "calendar": self._get_calendar_context(),
            "lead_lag": self._get_lead_lag_context(),
            "meta_strategy": self._get_meta_strategy_context(),
        }
        # Build formatted prompt string
        context["formatted_prompt"] = self._format_for_prompt(
            asset_id, asset_name, category, price_data, agent_results, context
        )
        return context

    # ==================== Original V2 Collectors ====================

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
                "momentum": regime.get("signals", {}).get("market_momentum", {}),
                "weight_adjustments": regime.get("weight_adjustments", {}),
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

            recent_critical = [
                {"title": e.title, "severity": e.severity, "category": e.category,
                 "affected_assets": e.affected_assets}
                for e in unprocessed[:5]
            ]

            return {
                "total_30d": stats.get("last_30_days", 0),
                "critical_count": stats.get("by_severity", {}).get("CRITICAL", 0),
                "high_count": stats.get("by_severity", {}).get("HIGH", 0),
                "recent_events": recent_critical,
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

            if len(previous) >= 2:
                diff = previous[0].get("score", 0) - previous[-1].get("score", 0)
                trend = "improving" if diff > 2 else "declining" if diff < -2 else "stable"
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
        except Exception:
            pass
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
        except Exception:
            return {"available": False}

    # ==================== NEW: Full Predict Modules ====================

    def _get_causal_chains_context(self) -> dict:
        """Get active causal chains and portfolio implications."""
        try:
            from predictive.causal_engine import CausalChainEngine
            engine = CausalChainEngine()

            active = [c for c in engine.active_chains if c.status == "ACTIVE"]
            if not active:
                return {"count": 0, "chains": [], "implications": {}}

            chains_summary = []
            for c in active[:5]:
                chains_summary.append({
                    "trigger": c.trigger_event,
                    "steps": len(c.links),
                    "probability": c.cumulative_probability,
                    "confidence": c.chain_confidence,
                    "top_impacts": dict(sorted(
                        c.net_portfolio_impact.items(),
                        key=lambda x: abs(x[1]), reverse=True
                    )[:3]),
                    "time_horizon": c.total_time_horizon_days,
                })

            implications = engine.get_portfolio_implications()

            return {
                "count": len(active),
                "chains": chains_summary,
                "top_actions": implications.get("top_action", []),
                "accuracy": engine.get_chain_accuracy(),
            }
        except Exception as e:
            logger.debug(f"Causal chains context: {e}")
            return {"count": 0, "chains": [], "implications": {}}

    def _get_event_trees_context(self) -> dict:
        """Get active event trees with convex positions."""
        try:
            from predictive.event_tree import EventTreeEngine
            engine = EventTreeEngine()

            active = [t for t in engine.trees if t.status == "ACTIVE"]
            if not active:
                return {"count": 0, "trees": [], "convex_positions": []}

            trees_summary = []
            for t in active[:3]:
                trees_summary.append({
                    "name": t.name,
                    "root_event": t.root_event,
                    "scenarios": t.total_scenarios,
                    "expected_impact": t.expected_portfolio_impact,
                })

            convex = engine.get_all_convex_positions()[:5]

            return {
                "count": len(active),
                "trees": trees_summary,
                "convex_positions": convex,
            }
        except Exception as e:
            logger.debug(f"Event trees context: {e}")
            return {"count": 0, "trees": [], "convex_positions": []}

    def _get_calendar_context(self) -> dict:
        """Get upcoming economic events."""
        try:
            from economic_calendar import calendar
            upcoming = calendar.get_upcoming(hours_ahead=168, limit=5)
            recent = calendar.get_recent(hours_back=24)

            return {
                "upcoming": [
                    {"name": e["name"], "hours_until": e["hours_until"],
                     "impact": e["impact"], "affects": e.get("affects_assets", [])}
                    for e in upcoming
                ],
                "recent": [
                    {"name": e["name"], "hours_ago": e["hours_ago"], "impact": e["impact"]}
                    for e in recent
                ],
            }
        except Exception as e:
            logger.debug(f"Calendar context: {e}")
            return {"upcoming": [], "recent": []}

    def _get_lead_lag_context(self) -> dict:
        """Get lead-lag prediction signals."""
        try:
            from predictive.lead_lag import LeadLagDetector
            # We need returns data — get from data_service cache
            detector = LeadLagDetector()
            # Try to get cached returns
            try:
                from data_service import data_service
                returns = data_service.get_historical_returns()
                if returns is not None and not returns.empty:
                    signals = detector.get_actionable_signals(returns)
                    return {
                        "active_signals": len(signals),
                        "signals": [
                            {"leader": s["leader"], "follower": s["follower"],
                             "prediction": s["prediction"], "confidence": s["confidence"],
                             "action": s["action"]}
                            for s in signals[:5]
                        ],
                    }
            except Exception:
                pass
            return {"active_signals": 0, "signals": []}
        except Exception as e:
            logger.debug(f"Lead-lag context: {e}")
            return {"active_signals": 0, "signals": []}

    def _get_meta_strategy_context(self) -> dict:
        """Get meta-strategy method weights per regime."""
        try:
            from predictive.meta_strategy import MetaStrategySelector
            meta = MetaStrategySelector()
            diagnostics = meta.get_diagnostics()

            # Get current regime to show active weights
            regime = "NEUTRAL"
            try:
                from regime_detector import regime_detector
                r = regime_detector.detect_regime()
                regime_name = r.get("regime", "transition")
                regime_map = {"risk-on": "RISK_ON", "risk-off": "RISK_OFF",
                              "inflation": "RISK_ON", "deflation": "RISK_OFF",
                              "transition": "NEUTRAL"}
                regime = regime_map.get(regime_name, "NEUTRAL")
            except Exception:
                pass

            weights = meta.get_weights(regime)
            return {
                "active_regime": regime,
                "method_weights": weights,
                "recommendation": diagnostics.get("recommendation", ""),
            }
        except Exception as e:
            logger.debug(f"Meta strategy context: {e}")
            return {"active_regime": "NEUTRAL", "method_weights": {}}

    # ==================== Prompt Formatter ====================

    def _format_for_prompt(
        self, asset_id, asset_name, category, price_data, agent_results, context
    ) -> str:
        """Format ALL context into a structured prompt block for the LLM."""
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
            lines = [f"  • [{e['severity']}] {e['title']}" for e in events["recent_events"][:3]]
            sections.append(
                f"AKTIVA HÄNDELSER ({events.get('total_30d', 0)} senaste 30d, "
                f"{events.get('critical_count', 0)} kritiska):\n" + "\n".join(lines)
            )

        # --- Narratives ---
        narr = context.get("narratives", {})
        if narr.get("narratives"):
            lines = []
            for n in narr["narratives"][:3]:
                c = " ⚠️ KONTRÄR" if n.get("contrarian_signal") else ""
                lines.append(f"  • \"{n['title']}\" — fas: {n['phase']}, konsensus: {n['consensus_pct']:.0f}%{c}")
            sections.append("AKTIVA NARRATIV:\n" + "\n".join(lines))

        # --- Causal Chains (NEW) ---
        chains = context.get("causal_chains", {})
        if chains.get("chains"):
            lines = []
            for c in chains["chains"][:3]:
                impacts = ", ".join(f"{k}: {v:+.1f}%" for k, v in c["top_impacts"].items())
                lines.append(
                    f"  • \"{c['trigger']}\" → {c['steps']} steg, "
                    f"prob: {c['probability']:.0%}, "
                    f"påverkan: {impacts}"
                )
            actions = chains.get("top_actions", [])
            action_str = ""
            if actions and actions[0].get("action") != "HOLD":
                action_str = "\n  REKOMMENDATION: " + "; ".join(
                    f"{a['action']} {a.get('asset', '')} ({a.get('reasoning', '')})"
                    for a in actions[:2]
                )
            sections.append(f"KAUSALA KEDJOR ({chains['count']} aktiva):\n" + "\n".join(lines) + action_str)

        # --- Event Trees (NEW) ---
        trees = context.get("event_trees", {})
        if trees.get("trees"):
            lines = []
            for t in trees["trees"][:2]:
                impacts = ", ".join(f"{k}: {v:+.1f}%" for k, v in list(t["expected_impact"].items())[:3])
                lines.append(f"  • \"{t['name']}\" — {t['scenarios']} scenarier, förväntad: {impacts}")
            convex = trees.get("convex_positions", [])
            if convex:
                conv_str = ", ".join(
                    f"{c['asset']} ({c['consensus_direction']}, win {c['avg_win_ratio']:.0%})"
                    for c in convex[:3]
                )
                lines.append(f"  KONVEXA POSITIONER: {conv_str}")
            sections.append(f"SCENARITRÄD ({trees['count']} aktiva):\n" + "\n".join(lines))

        # --- Calendar (NEW) ---
        cal = context.get("calendar", {})
        if cal.get("upcoming"):
            lines = [
                f"  • {e['name']} om {e['hours_until']:.0f}h (impact: {e['impact']}/10)"
                for e in cal["upcoming"][:4]
            ]
            sections.append("KOMMANDE EKONOMISKA EVENTS:\n" + "\n".join(lines))
        if cal.get("recent"):
            lines = [f"  • {e['name']} (för {e['hours_ago']:.0f}h sedan, impact: {e['impact']}/10)" for e in cal["recent"][:2]]
            sections.append("NYLIGEN INTRÄFFADE EVENTS:\n" + "\n".join(lines))

        # --- Lead-Lag (NEW) ---
        ll = context.get("lead_lag", {})
        if ll.get("signals"):
            lines = [
                f"  • {s['leader']} → {s['follower']}: {s['action']} "
                f"(konf: {s['confidence']:.0%}) — {s['prediction']}"
                for s in ll["signals"][:3]
            ]
            sections.append(f"LEAD-LAG SIGNALER ({ll['active_signals']} aktiva):\n" + "\n".join(lines))

        # --- Previous analyses ---
        hist = context.get("previous_analyses", {})
        if hist.get("previous"):
            prev = hist["previous"][0]
            time_ago = ""
            try:
                delta = datetime.now(timezone.utc) - datetime.fromisoformat(prev["timestamp"])
                hours = delta.total_seconds() / 3600
                time_ago = f"(för {hours:.0f}h sedan)" if hours < 24 else f"(för {delta.days}d sedan)"
            except Exception:
                pass
            sections.append(
                f"FÖREGÅENDE ANALYS AV {asset_name.upper()} {time_ago}:\n"
                f"  Poäng: {prev.get('score', 0):+.1f}, Rek: {prev.get('recommendation', '?')}\n"
                f"  Trend: {hist.get('trend_direction', 'okänt')}"
            )

        # --- Previous global summary ---
        prev_summary = context.get("previous_summary", {})
        if prev_summary.get("text"):
            sections.append(
                f"SENASTE SUPERVISOR-SUMMERING:\n"
                f"  Mood: {prev_summary.get('mood', '?')}\n"
                f"  \"{prev_summary['text'][:300]}\""
            )

        # --- Accuracy ---
        acc = context.get("accuracy", {})
        if acc.get("available") and acc.get("total_7d", 0) > 0:
            sections.append(
                f"SYSTEMETS TRÄFFSÄKERHET: "
                f"7d: {acc.get('accuracy_7d', 0):.0f}% ({acc.get('total_7d', 0)} pred.)"
            )

        if not sections:
            return ""
        return "\n\n".join(sections)
