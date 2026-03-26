"""
Evaluator - Backtesting engine that compares AI predictions against actual outcomes.
Calculates direction accuracy with ATR-adjusted thresholds, Brier score for calibration,
and per-agent performance metrics.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from analysis_store import store

logger = logging.getLogger("aether.evaluator")

# ATR-based thresholds per asset class (% of price)
# If actual move < threshold → "noise", don't count direction
DEFAULT_NOISE_THRESHOLD = 0.5  # fallback %

# Timeframe noise multipliers: shorter timeframes are noisier
TIMEFRAME_NOISE_MULTIPLIER = {
    "1h": 2.5,   # 1h moves are mostly noise, require 2.5x threshold
    "4h": 1.8,   # 4h still noisy
    "24h": 1.0,  # baseline
    "48h": 0.9,  # 48h moves should be more significant
    "7d": 0.7,   # weekly moves are rarely noise
}

# Score-to-direction mapping: higher threshold = only count strong convictions
SCORE_DIRECTION_THRESHOLD = 2.5  # Score must be > 2.5 for "up", < -2.5 for "down"


class Evaluator:
    """Evaluates prediction accuracy and calculates agent performance metrics."""

    def evaluate_all(self, current_prices: dict) -> dict:
        """Run full evaluation cycle: backfill prices, evaluate predictions, update agent stats."""
        results = {"backfilled": 0, "evaluated": 0, "agents_updated": 0}

        # 1. Backfill follow-up prices on old analyses
        results["backfilled"] = store.backfill_prices(current_prices)

        # 2. Evaluate predictions where we now have outcome data
        results["evaluated"] = self._evaluate_pending(current_prices)

        # 3. Update per-agent accuracy stats
        results["agents_updated"] = self._update_agent_accuracy()

        if results["evaluated"] > 0:
            logger.info(f"📊 Evaluation: {results['evaluated']} predictions scored, "
                        f"{results['agents_updated']} agent stats updated")
        return results

    def _get_noise_threshold(self, asset_id: str, current_prices: dict) -> float:
        """Get ATR-based noise threshold for an asset."""
        price_data = current_prices.get(asset_id, {})
        indicators = price_data.get("indicators", {})
        atr_pct = indicators.get("atr_pct")

        if atr_pct and atr_pct > 0:
            # Noise = 30% of ATR (moves smaller than this are insignificant)
            return atr_pct * 0.3

        # Fallback thresholds by asset type
        thresholds = {
            "btc": 1.5, "gold": 0.5, "silver": 1.0, "oil": 1.0,
            "sp500": 0.5, "global-equity": 0.5, "eurusd": 0.2, "us10y": 0.3,
        }
        return thresholds.get(asset_id, DEFAULT_NOISE_THRESHOLD)

    def _evaluate_pending(self, current_prices: dict) -> int:
        """Evaluate analyses where price snapshots are filled but not yet evaluated."""
        from analysis_store import DB_PATH
        import sqlite3

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Find analyses with ANY filled snapshot that hasn't been evaluated yet
        # Uses 1h as minimum (first evaluations appear after just 1 hour)
        rows = conn.execute("""
            SELECT a.id, a.asset_id, a.final_score, a.agent_scores,
                   a.price_at_analysis, a.supervisor_confidence,
                   ps.price_1h, ps.price_4h, ps.price_24h, ps.price_48h, ps.price_7d
            FROM analyses a
            JOIN price_snapshots ps ON ps.analysis_id = a.id
            WHERE a.analysis_type = 'asset'
            AND (ps.price_1h IS NOT NULL OR ps.price_4h IS NOT NULL OR ps.price_24h IS NOT NULL)
            AND a.id NOT IN (SELECT DISTINCT analysis_id FROM evaluations WHERE timeframe IN ('1h', '4h', '24h'))
            LIMIT 200
        """).fetchall()
        conn.close()

        evaluated = 0
        for row in rows:
            price_at = row["price_at_analysis"]
            if not price_at or price_at <= 0:
                continue

            threshold = self._get_noise_threshold(row["asset_id"], current_prices)

            # Evaluate each available timeframe
            timeframes = [
                ("1h", row["price_1h"]),
                ("4h", row["price_4h"]),
                ("24h", row["price_24h"]),
                ("48h", row["price_48h"]),
                ("7d", row["price_7d"]),
            ]

            for tf_name, tf_price in timeframes:
                if tf_price and tf_price > 0:
                    self._store_evaluation_v2(
                        analysis_id=row["id"],
                        asset_id=row["asset_id"],
                        timeframe=tf_name,
                        price_at_analysis=price_at,
                        price_now=tf_price,
                        score=row["final_score"],
                        confidence=row["supervisor_confidence"] or 0.5,
                        noise_threshold=threshold,
                    )
                    evaluated += 1

            # Also evaluate individual agent scores
            self._evaluate_agents(row, threshold)

        return evaluated

    def _store_evaluation_v2(self, analysis_id: str, asset_id: str, timeframe: str,
                             price_at_analysis: float, price_now: float, score: float,
                             confidence: float, noise_threshold: float) -> None:
        """Store evaluation with ATR-adjusted direction and Brier score."""
        actual_change = ((price_now - price_at_analysis) / price_at_analysis) * 100

        # Timeframe-aware noise threshold
        tf_multiplier = TIMEFRAME_NOISE_MULTIPLIER.get(timeframe, 1.0)
        effective_threshold = noise_threshold * tf_multiplier

        # Predicted direction: only count STRONG convictions as directional
        predicted_dir = "up" if score > SCORE_DIRECTION_THRESHOLD else "down" if score < -SCORE_DIRECTION_THRESHOLD else "neutral"

        # Actual direction: use effective threshold
        if actual_change > effective_threshold:
            actual_dir = "up"
        elif actual_change < -effective_threshold:
            actual_dir = "down"
        else:
            actual_dir = "neutral"

        # Direction correct logic – HONEST but FAIR evaluation
        if predicted_dir == "neutral" and actual_dir == "neutral":
            # Both neutral: skip entirely – this is NOT a prediction
            direction_correct = -1  # -1 = skip, don't count in accuracy
        elif predicted_dir == "neutral" and actual_dir != "neutral":
            # AI said neutral but market moved significantly: wrong
            direction_correct = 0
        elif actual_dir == "neutral":
            # AI made directional call but move was within noise threshold
            # Check if the actual change is at least in the same direction
            if (predicted_dir == "up" and actual_change > 0) or \
               (predicted_dir == "down" and actual_change < 0):
                # Direction was right, just a small move – count as correct
                direction_correct = 1
            else:
                # Wrong direction or truly flat
                direction_correct = 0
        else:
            # Both directional: check if directions match
            direction_correct = 1 if predicted_dir == actual_dir else 0

        # Magnitude error: normalize score to expected % range
        # Score 10 ≈ strong move = ~ATR, Score 1 = small move = ~0.2*ATR
        score_normalized = score * noise_threshold * 0.3
        magnitude_error = abs(score_normalized - actual_change)

        # Brier score: measures calibration of confidence
        # Skip Brier for neutral→neutral (not a real prediction)
        if direction_correct == -1:
            brier = 0.0
        else:
            brier = (confidence - direction_correct) ** 2

        from analysis_store import DB_PATH
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            INSERT INTO evaluations (analysis_id, asset_id, evaluated_at, timeframe,
                price_at_analysis, price_at_evaluation, actual_change_pct,
                predicted_direction, actual_direction, direction_correct,
                magnitude_error, score_at_analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_id, asset_id, datetime.now(timezone.utc).isoformat(), timeframe,
            price_at_analysis, price_now, round(actual_change, 4),
            predicted_dir, actual_dir, direction_correct,
            round(magnitude_error, 4), score,
        ))
        conn.commit()
        conn.close()

    def _evaluate_agents(self, row, noise_threshold: float) -> None:
        """Evaluate individual agent predictions within an analysis."""
        agent_scores = json.loads(row["agent_scores"]) if row["agent_scores"] else {}
        price_at = row["price_at_analysis"]
        price_24h = row["price_24h"]

        if not price_24h or not price_at or price_at <= 0:
            return

        actual_change = ((price_24h - price_at) / price_at) * 100

        for agent_name, agent_data in agent_scores.items():
            agent_score = agent_data.get("score", 0)
            agent_confidence = agent_data.get("confidence", 0.5)
            predicted_dir = "up" if agent_score > SCORE_DIRECTION_THRESHOLD else "down" if agent_score < -SCORE_DIRECTION_THRESHOLD else "neutral"

            if actual_change > noise_threshold:
                actual_dir = "up"
            elif actual_change < -noise_threshold:
                actual_dir = "down"
            else:
                actual_dir = "neutral"

            if predicted_dir == "neutral" and actual_dir == "neutral":
                correct = -1  # Skip
            elif predicted_dir == "neutral":
                correct = 0  # Missed the move
            elif actual_dir == "neutral":
                # Directional call but small move – check direction
                if (predicted_dir == "up" and actual_change > 0) or \
                   (predicted_dir == "down" and actual_change < 0):
                    correct = 1
                else:
                    correct = 0
            else:
                correct = 1 if predicted_dir == actual_dir else 0

            # Brier score for individual agent
            brier = 0.0 if correct == -1 else (agent_confidence - max(0, correct)) ** 2

            from analysis_store import DB_PATH
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("""
                INSERT OR IGNORE INTO evaluations (analysis_id, asset_id, evaluated_at, timeframe,
                    price_at_analysis, price_at_evaluation, actual_change_pct,
                    predicted_direction, actual_direction, direction_correct,
                    magnitude_error, score_at_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{row['id']}_{agent_name}", row["asset_id"],
                datetime.now(timezone.utc).isoformat(),
                f"24h_{agent_name}",
                price_at, price_24h, round(actual_change, 4),
                predicted_dir, actual_dir, correct,
                round(brier, 4),  # Store Brier score as magnitude_error for agents
                agent_score,
            ))
            conn.commit()
            conn.close()

    def _update_agent_accuracy(self) -> int:
        """Calculate and store aggregated accuracy per agent, including regime-split."""
        from analysis_store import DB_PATH
        import sqlite3

        agents = ["macro", "micro", "sentiment", "tech"]
        periods = [
            ("7d", 7),
            ("30d", 30),
            ("all", 365 * 10),
        ]
        updated = 0

        for agent in agents:
            for period_name, days in periods:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                row = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(direction_correct) as correct,
                        AVG(direction_correct) as accuracy,
                        AVG(magnitude_error) as avg_mag_error,
                        AVG(score_at_analysis) as avg_score
                    FROM evaluations
                    WHERE timeframe = ?
                    AND evaluated_at >= ?
                    AND direction_correct >= 0
                """, (f"24h_{agent}", cutoff)).fetchone()
                conn.close()

                if row and row["total"] > 0:
                    bias = row["avg_score"] if row["avg_score"] else 0

                    store.store_agent_accuracy(agent, None, period_name, {
                        "accuracy": round(row["accuracy"], 4) if row["accuracy"] else 0,
                        "avg_magnitude_error": round(row["avg_mag_error"], 2) if row["avg_mag_error"] else 0,
                        "total": row["total"],
                        "correct": row["correct"] or 0,
                        "bias": round(bias, 2),
                        "calibration_error": round(row["avg_mag_error"], 4) if row["avg_mag_error"] else 0,
                    })
                    updated += 1

        # Also overall (supervisor) accuracy
        for period_name, days in periods:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT COUNT(*) as total, SUM(direction_correct) as correct,
                       AVG(direction_correct) as accuracy, AVG(magnitude_error) as avg_mag_error,
                       AVG(score_at_analysis) as avg_score
                FROM evaluations WHERE timeframe = '24h' AND evaluated_at >= ?
                AND direction_correct >= 0
            """, (cutoff,)).fetchone()
            conn.close()

            if row and row["total"] > 0:
                store.store_agent_accuracy("supervisor", None, period_name, {
                    "accuracy": round(row["accuracy"], 4),
                    "avg_magnitude_error": round(row["avg_mag_error"], 2),
                    "total": row["total"],
                    "correct": row["correct"] or 0,
                    "bias": round(row["avg_score"], 2) if row["avg_score"] else 0,
                    "calibration_error": 0,
                })
                updated += 1

        # FIX 1: Regime-conditional accuracy
        self._update_regime_accuracy()

        return updated

    def _update_regime_accuracy(self):
        """Calculate accuracy per agent per regime (risk-on, risk-off, etc.)."""
        from analysis_store import DB_PATH
        import sqlite3

        regimes = ["risk-on", "risk-off", "inflation", "deflation", "transition"]
        agents = ["macro", "micro", "sentiment", "tech", "supervisor"]

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        self._regime_accuracy = {}

        for agent in agents:
            self._regime_accuracy[agent] = {}
            timeframe = "24h" if agent == "supervisor" else f"24h_{agent}"

            for regime in regimes:
                row = conn.execute("""
                    SELECT COUNT(*) as total, SUM(e.direction_correct) as correct,
                           AVG(e.direction_correct) as accuracy
                    FROM evaluations e
                    JOIN analyses a ON e.analysis_id = a.id
                    WHERE e.timeframe = ?
                    AND a.regime = ?
                    AND e.direction_correct >= 0
                """, (timeframe, regime)).fetchone()

                if row and row["total"] and row["total"] >= 5:
                    self._regime_accuracy[agent][regime] = {
                        "accuracy": round(row["accuracy"], 3) if row["accuracy"] else 0,
                        "total": row["total"],
                        "correct": row["correct"] or 0,
                    }

        conn.close()

    def get_regime_accuracy(self, agent: str = None) -> dict:
        """Get regime-conditional accuracy for one or all agents."""
        if not hasattr(self, '_regime_accuracy'):
            self._update_regime_accuracy()
        if agent:
            return self._regime_accuracy.get(agent, {})
        return self._regime_accuracy

    def get_performance_report(self) -> dict:
        """Generate complete performance report for the API/frontend."""
        counts = store.get_total_analyses_count()

        # Per-agent accuracy
        agents = {}
        for agent in ["macro", "micro", "sentiment", "tech", "supervisor"]:
            agent_stats = {}
            for period in ["7d", "30d", "all"]:
                data = store.get_agent_accuracy(agent, period)
                if data:
                    agent_stats[period] = data[0]
                else:
                    agent_stats[period] = {
                        "accuracy_direction": 0, "avg_magnitude_error": 0,
                        "total_predictions": 0, "correct_predictions": 0,
                        "bias": 0, "calibration_error": 0,
                    }
            agents[agent] = agent_stats

        # Evaluation summaries per timeframe
        timeframe_summaries = {}
        for tf in ["1h", "4h", "24h", "48h", "7d"]:
            timeframe_summaries[tf] = store.get_evaluation_summary(tf)

        # Best/worst predictions
        best_worst = store.get_best_worst_predictions(5)

        return {
            "database_stats": counts,
            "agent_accuracy": agents,
            "timeframe_summaries": timeframe_summaries,
            "best_predictions": best_worst["best"],
            "worst_predictions": best_worst["worst"],
        }


# Singleton
evaluator = Evaluator()
