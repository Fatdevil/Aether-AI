"""
Meta-Supervisor: Orchestrates the multi-provider ensemble system.
Decides when to request a second opinion and aggregates results.

Kill switch: ENSEMBLE_ENABLED=false in .env
Cost cap: ENSEMBLE_MAX_DAILY=50 in .env
"""

import os
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.ensemble")

# Configuration
ENSEMBLE_ENABLED = os.getenv("ENSEMBLE_ENABLED", "true").lower() == "true"
ENSEMBLE_MAX_DAILY = int(os.getenv("ENSEMBLE_MAX_DAILY", "50"))

# Triggers for second opinion
CONFIDENCE_THRESHOLD = 0.6       # Below this → get second opinion
ACCURACY_THRESHOLD = 0.40        # Below 40% historical accuracy → get second opinion
AGENT_SPREAD_THRESHOLD = 6.0     # Agent score spread > 6 → get second opinion
NEWS_IMPACT_THRESHOLD = 8        # Impact score >= 8 → get second opinion

# Daily counter (resets automatically)
_daily_second_opinions = 0
_daily_reset_date: Optional[str] = None


def is_ensemble_enabled() -> bool:
    """Check if ensemble is enabled and within daily budget."""
    global _daily_second_opinions, _daily_reset_date

    if not ENSEMBLE_ENABLED:
        return False

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _daily_reset_date != today:
        _daily_second_opinions = 0
        _daily_reset_date = today

    return _daily_second_opinions < ENSEMBLE_MAX_DAILY


def should_get_second_opinion(
    asset_id: str,
    primary_result: dict,
    agent_results: dict,
    news_impact: int = 0,
) -> tuple[bool, str]:
    """Decide if we should request a second opinion from another provider.

    Returns (should_trigger, reason)
    """
    if not is_ensemble_enabled():
        return False, "ensemble_disabled"

    reasons = []

    # 1. Low supervisor confidence
    confidence = primary_result.get("supervisorConfidence", 0.7)
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(f"low_confidence({confidence:.2f})")

    # 2. Historical accuracy below threshold for this asset
    asset_accuracy = _get_provider_accuracy("gemini", asset_id)
    if asset_accuracy is not None and asset_accuracy < ACCURACY_THRESHOLD:
        reasons.append(f"low_accuracy({asset_accuracy:.0%})")

    # 3. Large spread between agents (disagreement)
    scores = [r.get("score", 0) for r in agent_results.values()]
    if scores:
        spread = max(scores) - min(scores)
        if spread > AGENT_SPREAD_THRESHOLD:
            reasons.append(f"agent_disagreement(spread={spread:.1f})")

    # 4. Critical news event
    if news_impact >= NEWS_IMPACT_THRESHOLD:
        reasons.append(f"high_impact_news({news_impact})")

    if reasons:
        return True, " + ".join(reasons)

    return False, "no_trigger"


def _get_provider_accuracy(provider: str, asset_id: str) -> Optional[float]:
    """Get historical accuracy for a provider on an asset."""
    try:
        from analysis_store import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT accuracy FROM provider_accuracy WHERE provider = ? AND asset_id = ?",
            (provider, asset_id)
        ).fetchone()
        conn.close()
        return row["accuracy"] if row else None
    except Exception:
        return None


def aggregate_results(
    asset_id: str,
    primary_result: dict,
    second_result: Optional[dict],
    primary_provider: str = "gemini",
    second_provider: str = "anthropic",
) -> dict:
    """Aggregate primary and secondary analysis results.

    If no second opinion, just pass through primary.
    If both available, weight by historical accuracy.
    """
    global _daily_second_opinions

    if not second_result:
        return {
            **primary_result,
            "ensemble": {
                "active": False,
                "primary_provider": primary_provider,
                "second_provider": None,
                "consensus": "single",
            }
        }

    _daily_second_opinions += 1

    # Get historical accuracy for weighting
    primary_acc = _get_provider_accuracy(primary_provider, asset_id) or 0.5
    second_acc = _get_provider_accuracy(second_provider, asset_id) or 0.5

    # Normalize to weights
    total = primary_acc + second_acc
    if total > 0:
        w1 = primary_acc / total
        w2 = second_acc / total
    else:
        w1 = w2 = 0.5

    # Weighted final score
    s1 = primary_result.get("finalScore", 0)
    s2 = second_result.get("finalScore", 0)
    weighted_score = round(s1 * w1 + s2 * w2, 1)

    # Consensus indicator
    score_diff = abs(s1 - s2)
    if score_diff < 2:
        consensus = "strong"  # Both agree
    elif score_diff < 5:
        consensus = "moderate"  # Some disagreement
    else:
        consensus = "divergent"  # Major disagreement

    # Determine trend from weighted score
    if weighted_score >= 3:
        trend = "up"
    elif weighted_score <= -3:
        trend = "down"
    else:
        trend = "neutral"

    # Use primary result as base, overlay ensemble data
    result = {**primary_result}
    result["finalScore"] = weighted_score
    result["trend"] = trend

    # Merge supervisor text
    result["supervisorText"] = (
        f"[ENSEMBLE] {primary_provider.upper()} ({s1:+.1f}, vikt {w1:.0%}) + "
        f"{second_provider.upper()} ({s2:+.1f}, vikt {w2:.0%}) → {weighted_score:+.1f}. "
        f"Konsensus: {consensus}. "
        f"{primary_result.get('supervisorText', '')}"
    )

    result["ensemble"] = {
        "active": True,
        "primary_provider": primary_provider,
        "primary_score": s1,
        "second_provider": second_provider,
        "second_score": s2,
        "weights": {primary_provider: round(w1, 2), second_provider: round(w2, 2)},
        "consensus": consensus,
        "reason": "triggered",
        "daily_count": _daily_second_opinions,
        "daily_max": ENSEMBLE_MAX_DAILY,
    }

    logger.info(
        f"  🔀 ENSEMBLE {asset_id}: {primary_provider}={s1:+.1f} ({w1:.0%}) + "
        f"{second_provider}={s2:+.1f} ({w2:.0%}) → {weighted_score:+.1f} [{consensus}]"
    )

    return result


def update_provider_accuracy(provider: str, asset_id: str, correct: bool) -> None:
    """Update provider accuracy tracking after an evaluation."""
    try:
        from analysis_store import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        now = datetime.now(timezone.utc).isoformat()

        # Upsert
        existing = conn.execute(
            "SELECT total, correct FROM provider_accuracy WHERE provider = ? AND asset_id = ?",
            (provider, asset_id)
        ).fetchone()

        if existing:
            new_total = existing[0] + 1
            new_correct = existing[1] + (1 if correct else 0)
            new_accuracy = new_correct / new_total
            conn.execute(
                "UPDATE provider_accuracy SET total=?, correct=?, accuracy=?, last_updated=? "
                "WHERE provider=? AND asset_id=?",
                (new_total, new_correct, round(new_accuracy, 4), now, provider, asset_id)
            )
        else:
            conn.execute(
                "INSERT INTO provider_accuracy (provider, asset_id, total, correct, accuracy, last_updated) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (provider, asset_id, 1 if correct else 0, 1.0 if correct else 0.0, now)
            )

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to update provider accuracy: {e}")


def get_ensemble_status() -> dict:
    """Return current ensemble status for API/frontend."""
    global _daily_second_opinions
    return {
        "enabled": ENSEMBLE_ENABLED,
        "daily_count": _daily_second_opinions,
        "daily_max": ENSEMBLE_MAX_DAILY,
        "remaining": max(0, ENSEMBLE_MAX_DAILY - _daily_second_opinions),
        "triggers": {
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "accuracy_threshold": ACCURACY_THRESHOLD,
            "agent_spread_threshold": AGENT_SPREAD_THRESHOLD,
            "news_impact_threshold": NEWS_IMPACT_THRESHOLD,
        }
    }
