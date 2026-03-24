"""
AI Regime Feedback Loop
=======================
Analyzes historical regime switches to score their effectiveness,
identify drawdown episodes, and generate threshold adjustments
for the regime detection system.

This creates a self-improving AI that learns from its own mistakes.
"""
import logging
import json
import os
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "data", "regime_feedback.json")

# ===== OVERFITTING SAFEGUARDS =====
MIN_SAMPLES_FOR_ADJUSTMENT = 5    # Min datapoints per regime before suggesting changes
MAX_ADJUSTMENT_PCT = 0.20          # Max ±20% parameter change
DECAY_HALFLIFE_DAYS = 90           # Half-life for exponential decay (newer events weigh more)


def _ensure_data_dir():
    """Ensure the data directory exists."""
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)


def _load_feedback() -> dict:
    """Load saved feedback data."""
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"episodes": [], "threshold_adjustments": {}, "last_updated": None}


def _save_feedback(data: dict):
    """Save feedback data."""
    _ensure_data_dir()
    data["last_updated"] = datetime.now().isoformat()
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def analyze_regime_feedback() -> dict:
    """Analyze composite backtest results to generate feedback and learning insights.

    Returns:
    - switch_scores: effectiveness score for each regime switch
    - drawdown_episodes: identified drawdown events with analysis
    - hit_rate: per-regime accuracy stats
    - threshold_adjustments: suggested parameter changes
    - learning_insights: human-readable takeaways
    """
    import yfinance as yf
    import pandas as pd
    from composite_backtest import _detect_regime_historical
    from portfolio_optimizer import ASSET_TICKER_MAP, _fetch_market_data

    logger.info("🧠 Running AI Feedback Analysis...")

    # Get market data
    tickers = list(ASSET_TICKER_MAP.values())
    data = yf.download(tickers, period="1y", progress=False)
    if data is None or data.empty:
        raise ValueError("No data for feedback analysis")

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
    else:
        close = data

    close = close.ffill()
    close = close.dropna(axis=1, thresh=int(len(close) * 0.5))
    close = close.dropna()

    # S&P 500 as proxy for portfolio performance
    sp500_col = None
    for col in close.columns:
        if str(col).strip() == "^GSPC":
            sp500_col = col
            break

    if sp500_col is None:
        raise ValueError("No S&P 500 data for feedback")

    sp500 = close[sp500_col]
    sp500_returns = sp500.pct_change().fillna(0)
    dates = close.index.tolist()

    # Detect historical regimes
    regimes = _detect_regime_historical(close, window_short=20, window_long=50)

    # ===== 1. Score each regime switch =====
    switch_scores = []
    prev_regime = None
    switch_indices = []

    for i in range(len(regimes)):
        if regimes[i] != prev_regime:
            switch_indices.append(i)
            prev_regime = regimes[i]

    for idx, switch_i in enumerate(switch_indices):
        regime = regimes[switch_i]
        date_str = dates[switch_i].strftime("%Y-%m-%d") if hasattr(dates[switch_i], 'strftime') else str(dates[switch_i])[:10]

        # Measure forward returns after the switch
        fwd_returns = {}
        for lookfwd in [5, 10, 20]:
            end_i = min(switch_i + lookfwd, len(sp500_returns) - 1)
            if end_i > switch_i:
                cum_ret = float((1 + sp500_returns.iloc[switch_i:end_i]).prod() - 1) * 100
                fwd_returns[f"{lookfwd}d"] = round(cum_ret, 2)

        # Determine if the switch was "correct"
        ret_10d = fwd_returns.get("10d", 0)

        if regime == "aggressive":
            correct = ret_10d > 0  # Aggressive should precede gains
            score = min(10, max(-10, ret_10d * 2))  # Scale: 1% = 2 points
        elif regime == "conservative":
            correct = ret_10d < 0  # Conservative should precede losses
            score = min(10, max(-10, -ret_10d * 2))
        else:  # balanced
            correct = abs(ret_10d) < 3  # Balanced = stable period
            score = min(10, max(-10, 5 - abs(ret_10d)))

        switch_scores.append({
            "date": date_str,
            "regime": regime,
            "forward_returns": fwd_returns,
            "correct": correct,
            "score": round(score, 1),
            "label": {"conservative": "🛡️ Försiktig", "balanced": "⚖️ Balanserad", "aggressive": "🚀 Aggressiv"}.get(regime, regime),
        })

    # ===== 2. Identify drawdown episodes =====
    drawdown_episodes = []
    portfolio_values = [100.0]
    for i in range(1, len(sp500_returns)):
        portfolio_values.append(portfolio_values[-1] * (1 + sp500_returns.iloc[i]))

    peak = 100
    in_drawdown = False
    dd_start = 0
    dd_peak = 100

    for i in range(len(portfolio_values)):
        v = portfolio_values[i]
        if v > peak:
            if in_drawdown and (peak - dd_trough) / dd_peak * 100 > 3:
                # Record the drawdown episode
                dd_pct = (dd_peak - dd_trough) / dd_peak * 100
                regime_at_start = regimes[dd_start] if dd_start < len(regimes) else "unknown"
                start_date = dates[dd_start].strftime("%Y-%m-%d") if hasattr(dates[dd_start], 'strftime') else str(dates[dd_start])[:10]
                end_date = dates[i].strftime("%Y-%m-%d") if hasattr(dates[i], 'strftime') else str(dates[i])[:10]

                # Was AI protective?
                was_protective = regime_at_start in ("conservative", "balanced")

                drawdown_episodes.append({
                    "start_date": start_date,
                    "end_date": end_date,
                    "drawdown_pct": round(dd_pct, 1),
                    "recovery_days": i - dd_start,
                    "regime_at_start": regime_at_start,
                    "was_protective": was_protective,
                    "lesson": _generate_lesson(dd_pct, regime_at_start, was_protective),
                })

            in_drawdown = False
            peak = v
            dd_peak = v
            dd_trough = v
        else:
            if not in_drawdown:
                in_drawdown = True
                dd_start = i
                dd_peak = peak
                dd_trough = v
            else:
                dd_trough = min(dd_trough, v)

    # ===== 3. Calculate hit rates (with decay weighting) =====
    hit_rates = {}
    last_date = dates[-1] if dates else datetime.now()

    for regime in ["conservative", "balanced", "aggressive"]:
        regime_switches = [s for s in switch_scores if s["regime"] == regime]
        if regime_switches:
            total_count = len(regime_switches)

            # Apply exponential decay: recent events weigh more
            weights = []
            for s in regime_switches:
                try:
                    switch_date = datetime.strptime(s["date"], "%Y-%m-%d")
                    days_ago = (last_date - switch_date).days if hasattr(last_date, 'days') else (
                        (last_date.to_pydatetime() - switch_date).days if hasattr(last_date, 'to_pydatetime') else 180
                    )
                except Exception:
                    days_ago = 180
                w = np.exp(-0.693 * days_ago / DECAY_HALFLIFE_DAYS)  # 0.693 = ln(2)
                weights.append(w)

            weights = np.array(weights)
            correct_arr = np.array([1.0 if s["correct"] else 0.0 for s in regime_switches])

            # Decay-weighted hit rate
            weighted_hit_rate = float(np.sum(weights * correct_arr) / np.sum(weights)) * 100 if np.sum(weights) > 0 else 0
            # Simple hit rate (for display)
            simple_correct = sum(1 for s in regime_switches if s["correct"])
            simple_hit_rate = round(simple_correct / total_count * 100)

            avg_score = float(np.mean([s["score"] for s in regime_switches]))

            # Confidence level based on sample size
            if total_count >= MIN_SAMPLES_FOR_ADJUSTMENT:
                confidence = "high"
                confidence_note = f"Hög konfidens ({total_count} datapunkter)"
            elif total_count >= 3:
                confidence = "medium"
                confidence_note = f"Medium konfidens ({total_count} datapunkter, behöver {MIN_SAMPLES_FOR_ADJUSTMENT})"
            else:
                confidence = "low"
                confidence_note = f"⚠️ Låg konfidens — bara {total_count} datapunkt{'er' if total_count > 1 else ''}, kan vara slump"

            hit_rates[regime] = {
                "total_switches": total_count,
                "correct": simple_correct,
                "hit_rate": simple_hit_rate,
                "weighted_hit_rate": round(weighted_hit_rate),
                "avg_score": round(avg_score, 1),
                "confidence": confidence,
                "confidence_note": confidence_note,
                "sufficient_data": total_count >= MIN_SAMPLES_FOR_ADJUSTMENT,
            }

    overall_correct = sum(1 for s in switch_scores if s["correct"])
    overall_total = len(switch_scores) if switch_scores else 1
    overall_hit_rate = round(overall_correct / overall_total * 100)

    # ===== 4. Generate threshold adjustments (WITH SAFEGUARDS) =====
    threshold_adjustments = {}

    def _safe_adjustment(current: float, target: float) -> float:
        """Cap adjustment to MAX_ADJUSTMENT_PCT of current value."""
        max_delta = abs(current) * MAX_ADJUSTMENT_PCT
        delta = target - current
        capped_delta = max(-max_delta, min(max_delta, delta))
        return round(current + capped_delta, 2)

    # Conservative threshold
    if "conservative" in hit_rates:
        hr = hit_rates["conservative"]
        if hr["hit_rate"] < 50 and hr["sufficient_data"]:
            suggested = _safe_adjustment(-3.0, -4.0)
            threshold_adjustments["risk_off_threshold"] = {
                "current": -3.0,
                "suggested": suggested,
                "reason": f"Försiktig regim träffade {hr['hit_rate']}% (decay-viktad: {hr['weighted_hit_rate']}%). Sänker tröskel.",
                "confidence": hr["confidence"],
            }
        elif hr["hit_rate"] < 50 and not hr["sufficient_data"]:
            threshold_adjustments["risk_off_threshold"] = {
                "current": -3.0,
                "suggested": -3.0,  # No change
                "reason": f"Försiktig regim: {hr['hit_rate']}% hit rate men {hr['confidence_note']}. Inga ändringar görs.",
                "confidence": hr["confidence"],
                "blocked": True,
            }

    # Aggressive threshold
    if "aggressive" in hit_rates:
        hr = hit_rates["aggressive"]
        if hr["hit_rate"] < 50 and hr["sufficient_data"]:
            suggested = _safe_adjustment(4.0, 5.0)
            threshold_adjustments["risk_on_threshold"] = {
                "current": 4.0,
                "suggested": suggested,
                "reason": f"Aggressiv regim träffade {hr['hit_rate']}% (decay-viktad: {hr['weighted_hit_rate']}%). Höjer tröskel.",
                "confidence": hr["confidence"],
            }
        elif hr["hit_rate"] < 50 and not hr["sufficient_data"]:
            threshold_adjustments["risk_on_threshold"] = {
                "current": 4.0,
                "suggested": 4.0,  # No change
                "reason": f"Aggressiv regim: {hr['hit_rate']}% hit rate men {hr['confidence_note']}. Inga ändringar görs.",
                "confidence": hr["confidence"],
                "blocked": True,
            }

    # Volatility sensitivity — only adjust with sufficient drawdown data
    uncaught = [ep for ep in drawdown_episodes if not ep["was_protective"] and ep["drawdown_pct"] > 5]
    if uncaught and len(drawdown_episodes) >= 3:  # Need at least 3 drawdowns
        suggested = _safe_adjustment(1.2, 1.1)
        threshold_adjustments["volatility_sensitivity"] = {
            "current": 1.2,
            "suggested": suggested,
            "reason": f"{len(uncaught)}/{len(drawdown_episodes)} fall >5% missades. Ökar volatilitetskänslighet.",
            "confidence": "high" if len(drawdown_episodes) >= 5 else "medium",
        }
    elif uncaught:
        threshold_adjustments["volatility_sensitivity"] = {
            "current": 1.2,
            "suggested": 1.2,  # No change
            "reason": f"{len(uncaught)} fall >5% missades, men bara {len(drawdown_episodes)} nedgångar totalt — för lite data.",
            "confidence": "low",
            "blocked": True,
        }

    # ===== 5. Generate learning insights (with safeguard context) =====
    insights = []

    # Overfitting warning
    if overall_total < MIN_SAMPLES_FOR_ADJUSTMENT * 2:
        insights.append({
            "type": "safeguard",
            "icon": "🔒",
            "text": f"Övermatchningsskydd aktivt: bara {overall_total} regimskiften. Behöver {MIN_SAMPLES_FOR_ADJUSTMENT * 2}+ för fulla justeringar. Parametrar ändras max ±{int(MAX_ADJUSTMENT_PCT*100)}%.",
            "severity": "info",
        })

    # Overall performance
    insights.append({
        "type": "summary",
        "icon": "🧠",
        "text": f"AI:n träffade rätt på {overall_hit_rate}% av regimskiftena ({overall_correct}/{overall_total}).",
        "severity": "good" if overall_hit_rate >= 60 else "warning" if overall_hit_rate >= 40 else "bad",
    })

    # Best regime
    if hit_rates:
        best_regime = max(hit_rates.items(), key=lambda x: x[1]["hit_rate"])
        worst_regime = min(hit_rates.items(), key=lambda x: x[1]["hit_rate"])
        insights.append({
            "type": "strength",
            "icon": "💪",
            "text": f"Bäst på '{best_regime[0]}'-skiften ({best_regime[1]['hit_rate']}% hit rate, konfidens: {best_regime[1]['confidence']}).",
            "severity": "good",
        })
        if worst_regime[1]["hit_rate"] < 60:
            note = f" ({worst_regime[1]['confidence_note']})" if not worst_regime[1]["sufficient_data"] else ""
            insights.append({
                "type": "weakness",
                "icon": "⚠️",
                "text": f"Svagast på '{worst_regime[0]}'-skiften ({worst_regime[1]['hit_rate']}% hit rate).{note}",
                "severity": "warning",
            })

    # Drawdown lessons
    if drawdown_episodes:
        caught = sum(1 for ep in drawdown_episodes if ep["was_protective"])
        total_dd = len(drawdown_episodes)
        insights.append({
            "type": "drawdown",
            "icon": "📉",
            "text": f"AI:n var skyddande vid {caught}/{total_dd} nedgångar >3%.",
            "severity": "good" if caught / max(total_dd, 1) > 0.5 else "warning",
        })

    # Threshold advice — show blocked vs active
    if threshold_adjustments:
        active = [k for k, v in threshold_adjustments.items() if not v.get("blocked")]
        blocked = [k for k, v in threshold_adjustments.items() if v.get("blocked")]
        for key in active:
            adj = threshold_adjustments[key]
            insights.append({
                "type": "adjustment",
                "icon": "🔧",
                "text": f"{adj['reason']} (konfidens: {adj.get('confidence', '?')})",
                "severity": "info",
            })
        for key in blocked:
            adj = threshold_adjustments[key]
            insights.append({
                "type": "blocked",
                "icon": "🔒",
                "text": adj["reason"],
                "severity": "info",
            })

    # Save feedback
    feedback_data = _load_feedback()
    feedback_data["episodes"] = [e for e in drawdown_episodes]
    feedback_data["threshold_adjustments"] = {k: v for k, v in threshold_adjustments.items() if not v.get("blocked")}
    feedback_data["hit_rates"] = hit_rates
    _save_feedback(feedback_data)

    logger.info(f"  ✅ Feedback analysis complete: {overall_hit_rate}% hit rate, {len(drawdown_episodes)} drawdowns, {len(threshold_adjustments)} adjustments")

    return {
        "switch_scores": switch_scores,
        "drawdown_episodes": drawdown_episodes,
        "hit_rates": hit_rates,
        "overall_hit_rate": overall_hit_rate,
        "threshold_adjustments": threshold_adjustments,
        "insights": insights,
        "total_switches": len(switch_scores),
    }


def _generate_lesson(dd_pct: float, regime: str, was_protective: bool) -> str:
    """Generate a human-readable lesson from a drawdown episode."""
    if was_protective:
        return f"✅ AI var korrekt i {regime}-läge. Skyddade mot {dd_pct:.1f}% nedgång."
    elif regime == "aggressive":
        return f"❌ AI låg i aggressiv under {dd_pct:.1f}% fall. Borde ha bytt till försiktig tidigare."
    elif regime == "balanced":
        return f"⚠️ AI låg i balanserad under {dd_pct:.1f}% fall. Övervägde aldrig försiktig profil."
    else:
        return f"📊 Nedgång på {dd_pct:.1f}% — AI:n bör analysera detta mönster."


def get_adjusted_thresholds() -> dict:
    """Get threshold adjustments from feedback for use in regime detection.

    Only applies adjustments that passed safeguard checks (not blocked).
    All adjustments are capped at MAX_ADJUSTMENT_PCT of the default.
    """
    feedback = _load_feedback()
    adjustments = feedback.get("threshold_adjustments", {})

    # Default thresholds
    defaults = {
        "risk_off_score": -3.0,
        "risk_on_score": 4.0,
        "vol_sensitivity": 1.2,
        "sma_short": 20,
        "sma_long": 50,
    }
    thresholds = dict(defaults)

    def _apply_capped(key: str, adjustment_key: str):
        """Apply adjustment with max cap safeguard."""
        if adjustment_key in adjustments:
            adj = adjustments[adjustment_key]
            if adj.get("blocked"):
                return  # Safeguard blocked this adjustment
            suggested = adj["suggested"]
            default = defaults[key]
            max_delta = abs(default) * MAX_ADJUSTMENT_PCT
            delta = suggested - default
            capped = max(-max_delta, min(max_delta, delta))
            thresholds[key] = round(default + capped, 2)

    _apply_capped("risk_off_score", "risk_off_threshold")
    _apply_capped("risk_on_score", "risk_on_threshold")
    _apply_capped("vol_sensitivity", "volatility_sensitivity")

    return thresholds
