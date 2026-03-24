"""
Portfolio Manager - Track real positions, P/L, and risk metrics.
Stores positions in SQLite and calculates live P/L, allocation, and risk.
"""

import sqlite3
import json
import uuid
import logging
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aether.portfolio")

DB_PATH = Path(__file__).parent / "aether_data.db"


class PortfolioManager:
    """Manages user portfolio positions with P/L tracking and risk analysis."""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        for attempt in range(3):
            try:
                conn = sqlite3.connect(self.db_path, timeout=10)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                return conn
            except sqlite3.OperationalError:
                if attempt < 2:
                    _time.sleep(0.5 * (attempt + 1))
                else:
                    raise

    def _init_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                asset_name TEXT,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_date TEXT NOT NULL,
                currency TEXT DEFAULT '$',
                notes TEXT,
                status TEXT DEFAULT 'open',   -- open | closed
                closed_price REAL,
                closed_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_value REAL,
                total_cost REAL,
                total_pnl REAL,
                total_pnl_pct REAL,
                position_count INTEGER,
                snapshot_data TEXT   -- JSON: per-position details
            );

            CREATE INDEX IF NOT EXISTS idx_positions_asset ON positions(asset_id);
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            CREATE INDEX IF NOT EXISTS idx_snapshots_time ON portfolio_snapshots(timestamp);
        """)
        conn.commit()
        conn.close()
        logger.info("💼 Portfolio manager initialized")

    # ==================== POSITION CRUD ====================

    def add_position(self, asset_id: str, quantity: float, entry_price: float,
                     entry_date: str = "", asset_name: str = "",
                     currency: str = "$", notes: str = "") -> dict:
        """Add a new position."""
        pos_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        if not entry_date:
            entry_date = now

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO positions (id, asset_id, asset_name, quantity, entry_price,
                entry_date, currency, notes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """, (pos_id, asset_id, asset_name, quantity, entry_price,
              entry_date, currency, notes, now, now))
        conn.commit()
        conn.close()

        logger.info(f"💼 Position added: {quantity} {asset_id} @ {currency}{entry_price:,.2f}")
        return {"id": pos_id, "asset_id": asset_id, "quantity": quantity, "entry_price": entry_price}

    def close_position(self, position_id: str, closed_price: float) -> Optional[dict]:
        """Close a position at a given price."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()

        pos = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
        if not pos:
            conn.close()
            return None

        conn.execute("""
            UPDATE positions SET status = 'closed', closed_price = ?, closed_date = ?, updated_at = ?
            WHERE id = ?
        """, (closed_price, now, now, position_id))
        conn.commit()
        conn.close()

        pnl = (closed_price - pos["entry_price"]) * pos["quantity"]
        pnl_pct = ((closed_price - pos["entry_price"]) / pos["entry_price"]) * 100

        logger.info(f"💼 Position closed: {pos['asset_id']} @ {closed_price:,.2f} (P/L: {pnl:+,.2f})")
        return {"id": position_id, "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2)}

    def delete_position(self, position_id: str) -> bool:
        """Delete a position entirely."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def update_position(self, position_id: str, quantity: float = None,
                        entry_price: float = None, notes: str = None) -> bool:
        """Update position fields."""
        updates = []
        values = []
        if quantity is not None:
            updates.append("quantity = ?")
            values.append(quantity)
        if entry_price is not None:
            updates.append("entry_price = ?")
            values.append(entry_price)
        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)
        if not updates:
            return False

        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(position_id)

        conn = self._get_conn()
        cursor = conn.execute(
            f"UPDATE positions SET {', '.join(updates)} WHERE id = ?", values
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    # ==================== PORTFOLIO QUERIES ====================

    def get_positions(self, status: str = "open") -> list[dict]:
        """Get all positions with given status."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM positions WHERE status = ? ORDER BY entry_date DESC", (status,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_portfolio_summary(self, current_prices: dict) -> dict:
        """
        Calculate full portfolio summary with live P/L.
        current_prices: {"btc": {"price": 68000, ...}, "gold": {...}, ...}
        """
        positions = self.get_positions("open")
        if not positions:
            return {
                "total_value": 0, "total_cost": 0, "total_pnl": 0, "total_pnl_pct": 0,
                "positions": [], "allocation": {}, "risk_metrics": {},
            }

        enriched = []
        total_value = 0
        total_cost = 0

        for pos in positions:
            asset_id = pos["asset_id"]
            price_info = current_prices.get(asset_id, {})
            current_price = price_info.get("price", pos["entry_price"])
            indicators = price_info.get("indicators", {})

            qty = pos["quantity"]
            cost = qty * pos["entry_price"]
            value = qty * current_price
            pnl = value - cost
            pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100

            total_value += value
            total_cost += cost

            enriched.append({
                **pos,
                "current_price": round(current_price, 2),
                "current_value": round(value, 2),
                "cost_basis": round(cost, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "daily_change_pct": price_info.get("change_pct", 0),
                "atr_pct": indicators.get("atr_pct", 0),
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

        # Allocation percentages
        allocation = {}
        for pos in enriched:
            pct = (pos["current_value"] / total_value * 100) if total_value > 0 else 0
            allocation[pos["asset_id"]] = round(pct, 1)

        # Risk metrics
        risk = self._calculate_risk_metrics(enriched, total_value)

        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "position_count": len(enriched),
            "positions": enriched,
            "allocation": allocation,
            "risk_metrics": risk,
        }

    # ==================== TICKER MAPPING ====================

    _TICKER_MAP = {
        "btc": "BTC-USD", "gold": "GC=F", "silver": "SI=F",
        "sp500": "^GSPC", "global-equity": "ACWI", "oil": "BZ=F",
        "eurusd": "EURUSD=X", "us10y": "^TNX",
    }

    def _calculate_risk_metrics(self, positions: list[dict], total_value: float) -> dict:
        """Calculate portfolio-level risk metrics using CVaR, Monte Carlo, Sharpe, Max Drawdown."""
        if not positions or total_value <= 0:
            return {}

        # --- Concentration risk (fast, no API calls) ---
        allocations = sorted([pos["current_value"] / total_value for pos in positions], reverse=True)
        hhi = sum(a ** 2 for a in allocations)
        max_concentration = allocations[0] * 100 if allocations else 0

        # Winners vs losers
        winners = sum(1 for p in positions if p["pnl"] > 0)
        losers = sum(1 for p in positions if p["pnl"] < 0)

        # Best/worst positions
        best = max(positions, key=lambda p: p["pnl"]) if positions else None
        worst = min(positions, key=lambda p: p["pnl"]) if positions else None

        result = {
            "concentration": {
                "hhi": round(hhi, 4),
                "max_single_pct": round(max_concentration, 1),
                "diversified": hhi < 0.25 and len(positions) >= 3,
            },
            "win_loss": {"winners": winners, "losers": losers},
            "best_position": {
                "asset": best["asset_id"], "pnl": best["pnl"], "pnl_pct": best["pnl_pct"]
            } if best else None,
            "worst_position": {
                "asset": worst["asset_id"], "pnl": worst["pnl"], "pnl_pct": worst["pnl_pct"]
            } if worst else None,
        }

        # --- CVaR + Monte Carlo (uses yfinance, cached per session) ---
        try:
            from risk_math import get_portfolio_risk_metrics

            # Build ticker weights from positions
            ticker_weights = {}
            for pos in positions:
                ticker = self._TICKER_MAP.get(pos["asset_id"])
                if ticker:
                    weight = pos["current_value"] / total_value
                    ticker_weights[ticker] = ticker_weights.get(ticker, 0) + weight

            if ticker_weights:
                risk_data = get_portfolio_risk_metrics(ticker_weights)
                result.update({
                    "cvar": risk_data["cvar"],
                    "monte_carlo": risk_data["monte_carlo"],
                    "sharpe_ratio": risk_data["sharpe_ratio"],
                    "max_drawdown": risk_data["max_drawdown"],
                    "annualized_volatility": risk_data["annualized_volatility"],
                    "risk_level": risk_data["risk_level"],
                    "risk_label": risk_data["risk_label"],
                })
            else:
                result["risk_level"] = "okänd"
                result["risk_label"] = "Inga matchade tillgångar"
        except Exception as e:
            logger.warning(f"CVaR calculation failed, using basic metrics: {e}")
            # Fallback to basic ATR-based estimate
            weighted_atr = sum(
                pos.get("atr_pct", 2.0) * (pos["current_value"] / total_value)
                for pos in positions
            )
            result["risk_level"] = "hög" if weighted_atr > 5 else "medel" if weighted_atr > 3 else "låg"
            result["risk_label"] = f"Uppskattad risk (ATR): {round(weighted_atr, 1)}%"
            result["daily_var_pct"] = round(weighted_atr * 1.65, 2)

        return result

    def save_snapshot(self, current_prices: dict) -> None:
        """Save a portfolio snapshot for historical tracking."""
        summary = self.get_portfolio_summary(current_prices)
        if summary["position_count"] == 0:
            return

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO portfolio_snapshots (timestamp, total_value, total_cost,
                total_pnl, total_pnl_pct, position_count, snapshot_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            summary["total_value"], summary["total_cost"],
            summary["total_pnl"], summary["total_pnl_pct"],
            summary["position_count"],
            json.dumps(summary["allocation"]),
        ))
        conn.commit()
        conn.close()

    def get_history(self, limit: int = 100) -> list[dict]:
        """Get portfolio value history."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_closed_trades(self, limit: int = 50) -> list[dict]:
        """Get closed position history."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM positions WHERE status = 'closed'
            ORDER BY closed_date DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()

        trades = []
        for row in rows:
            r = dict(row)
            if r.get("closed_price") and r.get("entry_price"):
                r["pnl"] = round((r["closed_price"] - r["entry_price"]) * r["quantity"], 2)
                r["pnl_pct"] = round(((r["closed_price"] - r["entry_price"]) / r["entry_price"]) * 100, 2)
            trades.append(r)
        return trades


# Singleton
portfolio = PortfolioManager()
