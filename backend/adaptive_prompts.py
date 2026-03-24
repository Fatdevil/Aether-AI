"""
Adaptive Prompts - Generates context-aware performance feedback for AI agent prompts.
Injects historical accuracy data to help agents learn from past mistakes.
"""

import json
import logging
from typing import Optional
from analysis_store import store

logger = logging.getLogger("aether.adaptive")


def get_performance_context(agent_name: str, asset_id: Optional[str] = None) -> str:
    """
    Generate performance feedback context to inject into agent prompts.
    Uses bias-correction instead of vague 'be more careful' instructions.
    Requires minimum 10 predictions before activating.
    """
    # Get agent accuracy stats
    accuracy_data = store.get_agent_accuracy(agent_name, "30d")
    
    if not accuracy_data or accuracy_data[0].get("total_predictions", 0) < 5:
        return ""  # Not enough data for reliable feedback
    
    stats = accuracy_data[0]
    total = stats.get("total_predictions", 0)
    accuracy = stats.get("accuracy_direction", 0)
    bias = stats.get("bias", 0)
    mag_error = stats.get("avg_magnitude_error", 0)
    cal_error = stats.get("calibration_error", 0)
    
    parts = []
    
    # Overall accuracy
    acc_pct = round(accuracy * 100, 0)
    parts.append(f"Träffsäkerhet: {acc_pct}% korrekt riktning ({total} analyser, senaste 30d).")
    
    # Specific bias-correction (not vague 'be careful')
    if abs(bias) > 1.5:
        direction = "positiv (bullish)" if bias > 0 else "negativ (bearish)"
        parts.append(
            f"BIAS-KORREKTION: Subtrahera {bias:+.1f} från din bedömning. "
            f"Du tenderar att ge {abs(bias):.1f} poäng för {direction} score."
        )
    
    # Neutral-drift detection: high accuracy but all scores near 0
    if accuracy > 0.7 and abs(bias) < 0.5 and mag_error < 1.5:
        parts.append(
            "⚠️ Dina score ligger nära 0 – accuracy kan vara artificiellt hög. "
            "Ge tydligare riktning när data stödjer det. Undvik alltid score 0."
        )
    
    # Calibration feedback (Brier score)
    if cal_error > 0.3:
        parts.append(
            f"Kalibrering: Din confidence matchar inte dina resultat "
            f"(Brier: {cal_error:.2f}). Sänk confidence om du är osäker."
        )
    
    # Asset-specific context - DIRECT from evaluations (no minimum threshold)
    if asset_id:
        try:
            from analysis_store import DB_PATH
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN direction_correct = 1 THEN 1 ELSE 0 END) as correct,
                       AVG(CASE WHEN direction_correct >= 0 THEN actual_change_pct ELSE NULL END) as avg_change,
                       SUM(CASE WHEN predicted_direction = 'up' THEN 1 ELSE 0 END) as pred_up,
                       SUM(CASE WHEN predicted_direction = 'down' THEN 1 ELSE 0 END) as pred_down,
                       SUM(CASE WHEN actual_direction = 'up' THEN 1 ELSE 0 END) as actual_up,
                       SUM(CASE WHEN actual_direction = 'down' THEN 1 ELSE 0 END) as actual_down
                FROM evaluations
                WHERE asset_id = ? AND direction_correct >= 0
            """, (asset_id,)).fetchone()
            conn.close()

            if row and row["total"] >= 3:
                acc = (row["correct"] / row["total"]) * 100 if row["total"] > 0 else 0
                parts.append(f"HISTORISK ACCURACY för denna tillgång: {acc:.0f}% ({row['correct']}/{row['total']}).")

                # Direction bias detection
                pred_up = row["pred_up"] or 0
                pred_down = row["pred_down"] or 0
                actual_up = row["actual_up"] or 0
                actual_down = row["actual_down"] or 0

                if pred_down > pred_up * 2 and actual_up > actual_down:
                    parts.append(
                        f"⚠️ KRITISK BIAS: Du har predikterat DOWN {pred_down} gånger men marknaden gick UP {actual_up} gånger. "
                        f"KOMPENSERA genom att vara mer positiv i din bedömning av denna tillgång!"
                    )
                elif pred_up > pred_down * 2 and actual_down > actual_up:
                    parts.append(
                        f"⚠️ KRITISK BIAS: Du har predikterat UP {pred_up} gånger men marknaden gick DOWN {actual_down} gånger. "
                        f"KOMPENSERA genom att vara mer negativ i din bedömning av denna tillgång!"
                    )
        except Exception:
            pass

        # Asset class hints
        asset_class_hints = {
            "eurusd": "TIPS: EUR/USD styrs primärt av ränteskillnader, ECB/Fed-politik och handelsflöden. Undvik att ge starka riktningssignaler utan tydlig makrogrund.",
            "oil": "TIPS: Olja styrs av OPEC-beslut, lager, geopolitik och global efterfrågan. Var försiktig med bearish bias – oljemarknaden trenderar ofta uppåt.",
            "gold": "TIPS: Guld korrelerar negativt med USD och realräntor. I osäkra tider tenderar guld uppåt. Undvik persistent bearish bias.",
            "silver": "TIPS: Silver är en hybrid: ädelmetall + industri. Hög volatilitet – undvik extrema score utan stöd.",
        }
        if asset_id in asset_class_hints:
            parts.append(asset_class_hints[asset_id])
    
    if not parts:
        return ""
    
    context = "\n\nHISTORISK PRESTATION (justera din analys baserat på detta):\n" + "\n".join(f"- {p}" for p in parts)
    return context


def get_supervisor_context() -> str:
    """
    Generate performance feedback specifically for the supervisor agent.
    Includes which sub-agents to trust more/less.
    """
    agents = ["macro", "micro", "sentiment", "tech"]
    agent_stats = {}
    
    for agent in agents:
        data = store.get_agent_accuracy(agent, "30d")
        if data and data[0].get("total_predictions", 0) >= 5:
            agent_stats[agent] = data[0]
    
    if not agent_stats:
        return ""
    
    parts = ["AGENT-PRESTATION (vikta din bedömning baserat på agenternas träffsäkerhet):"]
    
    # Rank agents by accuracy
    ranked = sorted(agent_stats.items(), 
                   key=lambda x: x[1].get("accuracy_direction", 0), 
                   reverse=True)
    
    for agent, stats in ranked:
        acc = round(stats.get("accuracy_direction", 0) * 100, 0)
        total = stats.get("total_predictions", 0)
        bias = stats.get("bias", 0)
        
        bias_note = ""
        if abs(bias) > 1.5:
            direction = "bullish" if bias > 0 else "bearish"
            bias_note = f", {direction} bias {abs(bias):.1f}"
        
        agent_label = {"macro": "Makro", "micro": "Mikro", "sentiment": "Sentiment", "tech": "Teknisk"}.get(agent, agent)
        
        if acc >= 70:
            parts.append(f"  ✅ {agent_label}: {acc}% träff ({total} analyser{bias_note}) — PÅLITLIG")
        elif acc >= 50:
            parts.append(f"  ⚠️ {agent_label}: {acc}% träff ({total} analyser{bias_note}) — MEDEL")
        else:
            parts.append(f"  ❌ {agent_label}: {acc}% träff ({total} analyser{bias_note}) — OPÅLITLIG, vikta ned")
    
    return "\n".join(parts)


def get_dynamic_weights() -> dict:
    """
    Calculate suggested agent weights based on historical accuracy.
    Returns: {"macro": 0.35, "micro": 0.25, "sentiment": 0.20, "tech": 0.20}
    """
    agents = ["macro", "micro", "sentiment", "tech"]
    accuracies = {}
    
    for agent in agents:
        data = store.get_agent_accuracy(agent, "30d")
        if data and data[0].get("total_predictions", 0) >= 5:
            accuracies[agent] = max(0.2, data[0].get("accuracy_direction", 0.5))
        else:
            accuracies[agent] = 0.5  # Default: assume 50% if no data
    
    # Normalize to sum to 1.0
    total = sum(accuracies.values())
    weights = {agent: round(acc / total, 3) for agent, acc in accuracies.items()}
    
    return weights
