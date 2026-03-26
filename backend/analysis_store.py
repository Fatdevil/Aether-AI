"""
Analysis Store - SQLite persistence for all AI analyses, price snapshots, and evaluations.
Enables backtesting, accuracy tracking, and adaptive learning.
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aether.store")

DB_PATH = Path(__file__).parent / "aether_data.db"


class AnalysisStore:
    """Persistent storage for AI analyses and evaluation data."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        import time as _time
        for attempt in range(3):
            try:
                conn = sqlite3.connect(self.db_path, timeout=10)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
                conn.execute("PRAGMA foreign_keys=ON")
                return conn
            except sqlite3.OperationalError as e:
                if attempt < 2:
                    _time.sleep(0.5 * (attempt + 1))
                else:
                    raise

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                asset_name TEXT,
                category TEXT,
                timestamp TEXT NOT NULL,
                price_at_analysis REAL,
                change_pct_at_analysis REAL,
                final_score REAL NOT NULL,
                recommendation TEXT,
                trend TEXT,
                supervisor_text TEXT,
                supervisor_confidence REAL,
                agent_scores TEXT,          -- JSON: {macro: {score, confidence, reasoning, provider}, ...}
                providers_used TEXT,        -- JSON array
                risk_flags TEXT,            -- JSON array
                analysis_type TEXT DEFAULT 'asset'  -- asset | sector | region
            );

            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                price_at_analysis REAL,
                price_1h REAL,
                price_4h REAL,
                price_24h REAL,
                price_48h REAL,
                price_7d REAL,
                filled_at TEXT,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id)
            );

            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                timeframe TEXT NOT NULL,    -- '1h' | '4h' | '24h' | '48h' | '7d'
                price_at_analysis REAL,
                price_at_evaluation REAL,
                actual_change_pct REAL,
                predicted_direction TEXT,   -- 'up' | 'down' | 'neutral'
                actual_direction TEXT,      -- 'up' | 'down' | 'neutral'
                direction_correct INTEGER, -- 0 or 1
                magnitude_error REAL,      -- abs(predicted_change - actual_change)
                score_at_analysis REAL,
                FOREIGN KEY (analysis_id) REFERENCES analyses(id)
            );

            CREATE TABLE IF NOT EXISTS agent_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                asset_id TEXT,             -- NULL = global
                period TEXT NOT NULL,      -- '7d' | '30d' | 'all'
                accuracy_direction REAL,   -- 0.0 to 1.0
                avg_magnitude_error REAL,
                total_predictions INTEGER,
                correct_predictions INTEGER,
                bias REAL,                 -- positive = tends to be bullish
                calibration_error REAL,    -- confidence vs actual accuracy
                calculated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS provider_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,       -- 'gemini', 'anthropic', 'openai'
                asset_id TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.0,
                avg_confidence REAL DEFAULT 0.5,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts_history (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                title TEXT,
                impact_score INTEGER,
                urgency TEXT,
                category TEXT,
                source TEXT,
                actual_market_impact REAL,  -- filled later
                evaluation_notes TEXT
            );

            CREATE TABLE IF NOT EXISTS supervisor_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_score REAL,
                regime TEXT,
                mood TEXT,
                summary_text TEXT,
                key_changes TEXT,
                accuracy_last_7d REAL,
                active_events_count INTEGER,
                assets_analyzed INTEGER
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_analyses_asset ON analyses(asset_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp);
            CREATE INDEX IF NOT EXISTS idx_snapshots_analysis ON price_snapshots(analysis_id);
            CREATE INDEX IF NOT EXISTS idx_evaluations_asset ON evaluations(asset_id, timeframe);
            CREATE INDEX IF NOT EXISTS idx_agent_accuracy_agent ON agent_accuracy(agent_name, period);
            CREATE INDEX IF NOT EXISTS idx_supervisor_summaries_ts ON supervisor_summaries(timestamp);
        """)
        conn.commit()

        # Migration: add regime column if missing
        try:
            conn.execute("ALTER TABLE analyses ADD COLUMN regime TEXT DEFAULT 'unknown'")
            conn.commit()
            logger.info("🔄 Added 'regime' column to analyses table")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.close()
        logger.info(f"📦 Analysis store initialized: {self.db_path}")

    # ========== STORE OPERATIONS ==========

    def store_analysis(self, asset_id: str, analysis: dict, price_data: dict, asset_name: str = "", category: str = "") -> str:
        """Store a complete asset analysis. Returns analysis ID."""
        analysis_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        # Get current regime for regime-conditional accuracy tracking
        current_regime = "unknown"
        try:
            from regime_detector import regime_detector
            regime_data = regime_detector.detect_regime()
            current_regime = regime_data.get("regime", "unknown") if regime_data else "unknown"
        except Exception:
            pass

        agent_scores = {}
        for agent in ["macro", "micro", "sentiment", "tech"]:
            details = analysis.get("agentDetails", {}).get(agent, {})
            scores = analysis.get("scores", {})
            agent_scores[agent] = {
                "score": scores.get(agent, 0),
                "confidence": details.get("confidence", 0),
                "reasoning": details.get("reasoning", ""),
                "provider": details.get("provider", "rule_based"),
                "key_factors": details.get("key_factors", []),
            }

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO analyses (id, asset_id, asset_name, category, timestamp,
                price_at_analysis, change_pct_at_analysis, final_score, recommendation,
                trend, supervisor_text, supervisor_confidence, agent_scores,
                providers_used, risk_flags, analysis_type, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'asset', ?)
        """, (
            analysis_id, asset_id, asset_name, category, now,
            price_data.get("price", 0), price_data.get("change_pct", 0),
            analysis["finalScore"], analysis.get("recommendation", ""),
            analysis.get("trend", "neutral"),
            analysis.get("supervisorText", ""),
            analysis.get("supervisorConfidence", 0),
            json.dumps(agent_scores),
            json.dumps(analysis.get("providersUsed", [])),
            json.dumps(analysis.get("riskFlags", [])),
            current_regime,
        ))

        # Create price snapshot entry (to be filled later)
        conn.execute("""
            INSERT INTO price_snapshots (analysis_id, asset_id, price_at_analysis)
            VALUES (?, ?, ?)
        """, (analysis_id, asset_id, price_data.get("price", 0)))

        conn.commit()
        conn.close()
        return analysis_id

    def store_sector_analysis(self, sector_id: str, analysis: dict) -> str:
        """Store a sector/region analysis."""
        analysis_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO analyses (id, asset_id, asset_name, category, timestamp,
                price_at_analysis, change_pct_at_analysis, final_score, recommendation,
                trend, supervisor_text, supervisor_confidence, agent_scores,
                providers_used, risk_flags, analysis_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_id, sector_id,
            analysis.get("name", sector_id),
            analysis.get("category", "sector"),
            now,
            analysis.get("price", 0),
            analysis.get("change_pct", 0),
            analysis.get("score", 0),
            analysis.get("recommendation", ""),
            "up" if analysis.get("score", 0) > 2 else "down" if analysis.get("score", 0) < -2 else "neutral",
            analysis.get("reasoning", ""),
            analysis.get("confidence", 0.5),
            json.dumps({}),
            json.dumps([analysis.get("provider", "rule_based")]),
            json.dumps([]),
            analysis.get("analysis_type", "sector"),
        ))
        conn.commit()
        conn.close()
        return analysis_id

    def store_alert(self, alert: dict) -> None:
        """Store a sentinel alert for later evaluation."""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR IGNORE INTO alerts_history (id, timestamp, title, impact_score, urgency, category, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.get("id", str(uuid.uuid4())[:12]),
            alert.get("timestamp", datetime.now(timezone.utc).isoformat()),
            alert.get("title", ""),
            alert.get("impact_score", 0),
            alert.get("urgency", "routine"),
            alert.get("category", ""),
            alert.get("source", ""),
        ))
        conn.commit()
        conn.close()

    # ========== BACKFILL OPERATIONS ==========

    # Ticker mapping for yfinance lookups
    _TICKER_MAP = {
        "btc": "BTC-USD", "global-equity": "ACWI", "sp500": "^GSPC",
        "gold": "GC=F", "silver": "SI=F", "eurusd": "EURUSD=X",
        "oil": "BZ=F", "us10y": "^TNX",
    }

    def backfill_prices(self, current_prices: dict) -> int:
        """
        Fill in follow-up prices for old analyses using historical 1h data.
        For each unfilled timeframe, fetches the actual price at that point in time.
        """
        import yfinance as yf

        conn = self._get_conn()
        now = datetime.now(timezone.utc)
        updated = 0

        # Get unfilled snapshots (only those old enough to have data)
        rows = conn.execute("""
            SELECT ps.id, ps.analysis_id, ps.asset_id, ps.price_at_analysis,
                   a.timestamp as analysis_time,
                   ps.price_1h, ps.price_4h, ps.price_24h, ps.price_48h, ps.price_7d
            FROM price_snapshots ps
            JOIN analyses a ON a.id = ps.analysis_id
            WHERE ps.price_7d IS NULL
            ORDER BY a.timestamp DESC
            LIMIT 100
        """).fetchall()

        # Group by asset_id to batch yfinance calls
        assets_needed = {}
        for row in rows:
            aid = row["asset_id"]
            if aid not in assets_needed:
                assets_needed[aid] = []
            assets_needed[aid].append(row)

        for asset_id, asset_rows in assets_needed.items():
            ticker = self._TICKER_MAP.get(asset_id)
            if not ticker:
                continue

            # Find oldest analysis to determine how much history we need
            oldest_time = min(
                datetime.fromisoformat(r["analysis_time"]) for r in asset_rows
            )
            days_back = max(2, (now - oldest_time).days + 1)

            # Fetch 1h historical data
            try:
                t = yf.Ticker(ticker)
                # yfinance max for 1h is 730 days
                period = f"{min(days_back, 29)}d"
                hist = t.history(period=period, interval="1h")

                if hist.empty:
                    logger.warning(f"No 1h history for {ticker}")
                    continue

                closes = hist["Close"].dropna()
                if closes.empty:
                    continue

            except Exception as e:
                logger.warning(f"Failed to fetch 1h history for {ticker}: {e}")
                continue

            for row in asset_rows:
                analysis_time = datetime.fromisoformat(row["analysis_time"])
                # Ensure timezone aware
                if analysis_time.tzinfo is None:
                    analysis_time = analysis_time.replace(tzinfo=timezone.utc)

                age = now - analysis_time
                updates = {}

                timeframes = [
                    ("price_1h", timedelta(hours=1)),
                    ("price_4h", timedelta(hours=4)),
                    ("price_24h", timedelta(hours=24)),
                    ("price_48h", timedelta(hours=48)),
                    ("price_7d", timedelta(days=7)),
                ]

                for col, offset in timeframes:
                    if row[col] is not None:
                        continue  # Already filled
                    if age < offset:
                        continue  # Not old enough yet

                    target_time = analysis_time + offset
                    price = self._find_closest_price(closes, target_time)
                    if price is not None:
                        updates[col] = price

                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    values = list(updates.values()) + [row["id"]]
                    conn.execute(
                        f"UPDATE price_snapshots SET filled_at = ?, {set_clause} WHERE id = ?",
                        [now.isoformat()] + values
                    )
                    updated += 1

        conn.commit()
        conn.close()
        if updated:
            logger.info(f"📊 Backfilled {updated} price snapshots with historical data")
        return updated

    @staticmethod
    def _find_closest_price(closes: "pd.Series", target_time: datetime) -> Optional[float]:
        """Find the price closest to target_time in a 1h close series."""
        import pandas as pd

        if closes.empty:
            return None

        # Make target timezone-aware to match yfinance index
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)

        target_ts = pd.Timestamp(target_time)

        # Find nearest index
        try:
            idx = closes.index.get_indexer([target_ts], method="nearest")[0]
            if 0 <= idx < len(closes):
                # Check that the match is within 2 hours
                matched_time = closes.index[idx]
                diff = abs((matched_time - target_ts).total_seconds())
                if diff <= 7200:  # 2 hours tolerance
                    return round(float(closes.iloc[idx]), 4)
        except Exception:
            pass

        return None

    # ========== QUERY OPERATIONS ==========

    def get_analysis_history(self, asset_id: str, limit: int = 50) -> list[dict]:
        """Get recent analysis history for an asset."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT a.*, ps.price_1h, ps.price_4h, ps.price_24h, ps.price_48h, ps.price_7d
            FROM analyses a
            LEFT JOIN price_snapshots ps ON ps.analysis_id = a.id
            WHERE a.asset_id = ?
            ORDER BY a.timestamp DESC
            LIMIT ?
        """, (asset_id, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_recent_analyses(self, hours: int = 24, analysis_type: str = "asset") -> list[dict]:
        """Get all recent analyses."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM analyses
            WHERE timestamp >= ? AND analysis_type = ?
            ORDER BY timestamp DESC
        """, (cutoff, analysis_type)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_total_analyses_count(self) -> dict:
        """Get total count of stored analyses."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        asset_count = conn.execute("SELECT COUNT(*) FROM analyses WHERE analysis_type='asset'").fetchone()[0]
        sector_count = conn.execute("SELECT COUNT(*) FROM analyses WHERE analysis_type='sector'").fetchone()[0]
        region_count = conn.execute("SELECT COUNT(*) FROM analyses WHERE analysis_type='region'").fetchone()[0]
        snapshots_filled = conn.execute("SELECT COUNT(*) FROM price_snapshots WHERE price_24h IS NOT NULL").fetchone()[0]
        evaluations_total = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        conn.close()
        return {
            "total": total,
            "assets": asset_count,
            "sectors": sector_count,
            "regions": region_count,
            "snapshots_filled": snapshots_filled,
            "evaluations": evaluations_total,
        }

    def get_agent_scores_history(self, agent_name: str, asset_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get historical scores for a specific agent."""
        conn = self._get_conn()
        if asset_id:
            rows = conn.execute("""
                SELECT timestamp, final_score, agent_scores, price_at_analysis
                FROM analyses WHERE asset_id = ? AND analysis_type = 'asset'
                ORDER BY timestamp DESC LIMIT ?
            """, (asset_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT timestamp, asset_id, final_score, agent_scores, price_at_analysis
                FROM analyses WHERE analysis_type = 'asset'
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
        conn.close()

        result = []
        for row in rows:
            r = dict(row)
            scores = json.loads(r.get("agent_scores", "{}"))
            agent_data = scores.get(agent_name, {})
            result.append({
                "timestamp": r["timestamp"],
                "asset_id": r.get("asset_id", ""),
                "agent_score": agent_data.get("score", 0),
                "agent_confidence": agent_data.get("confidence", 0),
                "agent_provider": agent_data.get("provider", ""),
                "final_score": r["final_score"],
                "price": r["price_at_analysis"],
            })
        return result

    # ========== EVALUATION STORAGE ==========

    def store_evaluation(self, analysis_id: str, asset_id: str, timeframe: str,
                         price_at_analysis: float, price_now: float, score: float) -> None:
        """Store a prediction evaluation."""
        if price_at_analysis <= 0:
            return

        actual_change = ((price_now - price_at_analysis) / price_at_analysis) * 100
        predicted_dir = "up" if score > 1 else "down" if score < -1 else "neutral"
        actual_dir = "up" if actual_change > 0.5 else "down" if actual_change < -0.5 else "neutral"

        # Direction correct: neutral predictions are "correct" if actual is small
        if predicted_dir == "neutral":
            direction_correct = 1 if abs(actual_change) < 2.0 else 0
        else:
            direction_correct = 1 if predicted_dir == actual_dir else 0

        magnitude_error = abs(score - actual_change)

        conn = self._get_conn()
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

    def store_agent_accuracy(self, agent_name: str, asset_id: Optional[str],
                             period: str, stats: dict) -> None:
        """Store aggregated agent accuracy stats."""
        conn = self._get_conn()
        # Remove old entry for this agent/asset/period
        if asset_id:
            conn.execute("DELETE FROM agent_accuracy WHERE agent_name=? AND asset_id=? AND period=?",
                         (agent_name, asset_id, period))
        else:
            conn.execute("DELETE FROM agent_accuracy WHERE agent_name=? AND asset_id IS NULL AND period=?",
                         (agent_name, period))

        conn.execute("""
            INSERT INTO agent_accuracy (agent_name, asset_id, period, accuracy_direction,
                avg_magnitude_error, total_predictions, correct_predictions, bias,
                calibration_error, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_name, asset_id, period,
            stats.get("accuracy", 0), stats.get("avg_magnitude_error", 0),
            stats.get("total", 0), stats.get("correct", 0),
            stats.get("bias", 0), stats.get("calibration_error", 0),
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        conn.close()

    def get_agent_accuracy(self, agent_name: Optional[str] = None, period: str = "all") -> list[dict]:
        """Get agent accuracy stats."""
        conn = self._get_conn()
        if agent_name:
            rows = conn.execute(
                "SELECT * FROM agent_accuracy WHERE agent_name=? AND period=?",
                (agent_name, period)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_accuracy WHERE period=?", (period,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_evaluation_summary(self, timeframe: str = "24h") -> dict:
        """Get overall evaluation summary."""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(direction_correct) as correct,
                AVG(direction_correct) as accuracy,
                AVG(magnitude_error) as avg_mag_error,
                AVG(actual_change_pct) as avg_actual_change
            FROM evaluations
            WHERE timeframe = ?
            AND direction_correct >= 0
        """, (timeframe,)).fetchone()
        conn.close()
        if row and row["total"] > 0:
            return {
                "total": row["total"],
                "correct": row["correct"],
                "accuracy": round(row["accuracy"] * 100, 1),
                "avg_magnitude_error": round(row["avg_mag_error"], 2),
                "avg_actual_change": round(row["avg_actual_change"], 3),
            }
        return {"total": 0, "correct": 0, "accuracy": 0, "avg_magnitude_error": 0, "avg_actual_change": 0}

    def get_best_worst_predictions(self, limit: int = 5) -> dict:
        """Get best and worst predictions by magnitude error."""
        conn = self._get_conn()
        best = conn.execute("""
            SELECT e.*, a.asset_name, a.supervisor_text
            FROM evaluations e
            JOIN analyses a ON a.id = e.analysis_id
            WHERE e.direction_correct = 1
            ORDER BY e.magnitude_error ASC
            LIMIT ?
        """, (limit,)).fetchall()
        worst = conn.execute("""
            SELECT e.*, a.asset_name, a.supervisor_text
            FROM evaluations e
            JOIN analyses a ON a.id = e.analysis_id
            WHERE e.direction_correct = 0
            ORDER BY e.magnitude_error DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return {"best": [dict(r) for r in best], "worst": [dict(r) for r in worst]}


    # ========== SUPERVISOR SUMMARIES ==========

    def store_supervisor_summary(
        self,
        overall_score: float,
        regime: str,
        mood: str,
        summary_text: str,
        key_changes: dict = None,
        accuracy_7d: float = 0.0,
        events_count: int = 0,
        assets_count: int = 0,
    ) -> None:
        """Store a supervisor summary for historical continuity."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO supervisor_summaries
                (timestamp, overall_score, regime, mood, summary_text,
                 key_changes, accuracy_last_7d, active_events_count, assets_analyzed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            overall_score,
            regime,
            mood,
            summary_text,
            json.dumps(key_changes or {}),
            accuracy_7d,
            events_count,
            assets_count,
        ))
        conn.commit()
        conn.close()
        logger.info(f"📝 Stored supervisor summary: mood={mood}, regime={regime}")

    def get_recent_summaries(self, n: int = 3) -> list[dict]:
        """Get the N most recent supervisor summaries."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM supervisor_summaries
            ORDER BY timestamp DESC
            LIMIT ?
        """, (n,)).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("key_changes"):
                try:
                    d["key_changes"] = json.loads(d["key_changes"])
                except Exception:
                    pass
            result.append(d)
        return result


# Singleton
store = AnalysisStore()
