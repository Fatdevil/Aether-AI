"""
Database Abstraction Layer — Dual-mode: PostgreSQL (production) / SQLite (local dev).

When DATABASE_URL is set → PostgreSQL (persistent, survives Railway deploys).
When DATABASE_URL is missing → SQLite (local dev, file-based).

Provides connection objects with the SAME API as sqlite3.Connection so existing
code (analysis_store.py, portfolio_manager.py) needs minimal changes.
"""

import os
import json
import sqlite3
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("aether.db")

DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_TYPE = "postgresql" if DATABASE_URL else "sqlite"

# SQLite default path
SQLITE_PATH = str(Path(__file__).parent / "aether_data.db")


def get_connection():
    """
    Get a database connection.
    Returns a connection object with sqlite3-compatible API:
      - conn.execute(query, params) → cursor-like with .fetchall(), .fetchone()
      - conn.executescript(script)
      - conn.commit()
      - conn.close()
    
    Placeholders use ? for both backends (auto-converted for PostgreSQL).
    """
    if DB_TYPE == "postgresql":
        return _PgConnection()
    else:
        conn = sqlite3.connect(SQLITE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class _PgCursor:
    """Cursor-like wrapper that mimics sqlite3.Cursor with dict rows."""
    def __init__(self, pg_cursor, results=None, rowcount=0):
        self._cursor = pg_cursor
        self._results = results
        self.rowcount = rowcount
        self.lastrowid = None

    def fetchall(self):
        if self._results is not None:
            return self._results
        try:
            rows = self._cursor.fetchall()
            return [_PgRowProxy(r) for r in rows]
        except Exception:
            return []

    def fetchone(self):
        if self._results is not None:
            return _PgRowProxy(self._results[0]) if self._results else None
        try:
            row = self._cursor.fetchone()
            return _PgRowProxy(row) if row else None
        except Exception:
            return None

    def __getitem__(self, key):
        """Support cursor[0] syntax for single-value queries."""
        row = self.fetchone()
        if row is None:
            return None
        if isinstance(key, int):
            return list(row.values())[key]
        return row.get(key)


class _PgRowProxy(dict):
    """Dict subclass that also supports integer indexing like sqlite3.Row."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _PgConnection:
    """PostgreSQL connection that mimics sqlite3.Connection API."""

    def __init__(self):
        import psycopg2
        import psycopg2.extras
        self.conn = psycopg2.connect(DATABASE_URL)
        self.conn.autocommit = False

    def execute(self, query: str, params=None) -> _PgCursor:
        """Execute a query. Auto-converts ? to %s for PostgreSQL."""
        import psycopg2.extras
        query = query.replace("?", "%s")
        
        # Handle INSERT OR IGNORE → ON CONFLICT DO NOTHING
        query = query.replace("INSERT OR IGNORE", "INSERT")
        if "INSERT" in query.upper() and "ON CONFLICT" not in query.upper() and "OR IGNORE" not in query.upper():
            pass  # Normal insert
        
        # Handle INSERT OR REPLACE → upsert (handled case by case)
        
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute(query, params or ())
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}\nQuery: {query[:200]}")
            self.conn.rollback()
            raise
        return _PgCursor(cursor, rowcount=cursor.rowcount)

    def executescript(self, script: str):
        """Execute multi-statement SQL. Convert SQLite syntax to PostgreSQL."""
        # Convert SQLite-specific syntax
        script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        script = script.replace("AUTOINCREMENT", "")  # remaining
        script = script.replace("INSERT OR IGNORE", "INSERT")
        script = script.replace("INSERT OR REPLACE", "INSERT")
        
        cursor = self.conn.cursor()
        cursor.execute(script)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    @property
    def row_factory(self):
        return None
    
    @row_factory.setter  
    def row_factory(self, value):
        pass  # Ignore — PostgreSQL always returns dicts via RealDictCursor


# ============================================================
# KV Store — Replaces JSON file storage for persistent state
# ============================================================

_kv_initialized = False

def _ensure_kv_table():
    """Create kv_store table if it doesn't exist."""
    global _kv_initialized
    if _kv_initialized:
        return
    
    conn = get_connection()
    try:
        if DB_TYPE == "postgresql":
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT
                )
            """)
        else:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT
                );
            """)
        conn.commit()
        _kv_initialized = True
    except Exception as e:
        logger.warning(f"KV table init: {e}")
    finally:
        conn.close()


def kv_get(key: str) -> Optional[dict]:
    """Get a JSON value from the KV store. Returns None if not found."""
    _ensure_kv_table()
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
        if row:
            val = row["value"] if isinstance(row, dict) else row[0]
            if isinstance(val, str):
                return json.loads(val)
            return val
    except Exception as e:
        logger.warning(f"KV get '{key}': {e}")
    finally:
        conn.close()
    return None


def kv_set(key: str, value) -> None:
    """Set a JSON value in the KV store (upsert)."""
    from datetime import datetime, timezone
    _ensure_kv_table()
    
    now = datetime.now(timezone.utc).isoformat()
    val_str = json.dumps(value, default=str) if not isinstance(value, str) else value
    
    conn = get_connection()
    try:
        if DB_TYPE == "postgresql":
            conn.execute(
                """INSERT INTO kv_store (key, value, updated_at) 
                   VALUES (%s, %s, %s) 
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at""",
                (key, val_str, now)
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value, updated_at) VALUES (?, ?, ?)",
                (key, val_str, now)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"KV set '{key}': {e}")
    finally:
        conn.close()


def init_postgresql_tables():
    """Initialize all tables for PostgreSQL. Called on startup when DATABASE_URL is set."""
    if DB_TYPE != "postgresql":
        return
    
    conn = get_connection()
    try:
        conn.execute("""
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
                agent_scores TEXT,
                providers_used TEXT,
                risk_flags TEXT,
                analysis_type TEXT DEFAULT 'asset',
                regime TEXT DEFAULT 'unknown'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id SERIAL PRIMARY KEY,
                analysis_id TEXT NOT NULL REFERENCES analyses(id),
                asset_id TEXT NOT NULL,
                price_at_analysis REAL,
                price_1h REAL,
                price_4h REAL,
                price_24h REAL,
                price_48h REAL,
                price_7d REAL,
                filled_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id SERIAL PRIMARY KEY,
                analysis_id TEXT NOT NULL REFERENCES analyses(id),
                asset_id TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                price_at_analysis REAL,
                price_at_evaluation REAL,
                actual_change_pct REAL,
                predicted_direction TEXT,
                actual_direction TEXT,
                direction_correct INTEGER,
                magnitude_error REAL,
                score_at_analysis REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_accuracy (
                id SERIAL PRIMARY KEY,
                agent_name TEXT NOT NULL,
                asset_id TEXT,
                period TEXT NOT NULL,
                accuracy_direction REAL,
                avg_magnitude_error REAL,
                total_predictions INTEGER,
                correct_predictions INTEGER,
                bias REAL,
                calibration_error REAL,
                calculated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_accuracy (
                id SERIAL PRIMARY KEY,
                provider TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.0,
                avg_confidence REAL DEFAULT 0.5,
                last_updated TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_history (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                title TEXT,
                impact_score INTEGER,
                urgency TEXT,
                category TEXT,
                source TEXT,
                actual_market_impact REAL,
                evaluation_notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS supervisor_summaries (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                overall_score REAL,
                regime TEXT,
                mood TEXT,
                summary_text TEXT,
                key_changes TEXT,
                accuracy_last_7d REAL,
                active_events_count INTEGER,
                assets_analyzed INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                asset_name TEXT,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_date TEXT NOT NULL,
                currency TEXT DEFAULT '$',
                notes TEXT,
                status TEXT DEFAULT 'open',
                closed_price REAL,
                closed_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                total_value REAL,
                total_cost REAL,
                total_pnl REAL,
                total_pnl_pct REAL,
                position_count INTEGER,
                snapshot_data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT
            )
        """)
        # Indexes
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_analyses_asset ON analyses(asset_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON analyses(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_analysis ON price_snapshots(analysis_id)",
            "CREATE INDEX IF NOT EXISTS idx_evaluations_asset ON evaluations(asset_id, timeframe)",
            "CREATE INDEX IF NOT EXISTS idx_agent_accuracy_agent ON agent_accuracy(agent_name, period)",
            "CREATE INDEX IF NOT EXISTS idx_supervisor_summaries_ts ON supervisor_summaries(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_positions_asset ON positions(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_time ON portfolio_snapshots(timestamp)",
        ]:
            conn.execute(idx_sql)
        
        conn.commit()
        logger.info("🐘 All PostgreSQL tables initialized!")
    except Exception as e:
        logger.error(f"PostgreSQL table init failed: {e}")
        conn.rollback()
    finally:
        conn.close()


# Auto-log on import
logger.info(f"🗄️ Database: {DB_TYPE}" + (f" (Railway PostgreSQL)" if DATABASE_URL else f" (local SQLite: {SQLITE_PATH})"))
