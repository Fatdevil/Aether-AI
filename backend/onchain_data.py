"""
On-Chain Data - Fetches BTC on-chain metrics from free APIs (no API key needed).
Provides exchange flows, mempool stats, fee data, and network activity.
Data sources: mempool.space, blockchain.info
"""

import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("aether.onchain")

# Cache
_onchain_cache: Optional[dict] = None
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes

# API endpoints
MEMPOOL_API = "https://mempool.space/api"
BLOCKCHAIN_API = "https://blockchain.info"


async def fetch_onchain_data() -> dict:
    """Fetch BTC on-chain data from free APIs. Returns combined metrics."""
    global _onchain_cache, _cache_time

    now = time.monotonic()
    if now - _cache_time < _CACHE_TTL and _onchain_cache:
        return _onchain_cache

    result = {
        "available": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Fetch all data concurrently
        tasks = {
            "mempool": _fetch_mempool_stats(client),
            "fees": _fetch_fee_estimates(client),
            "hashrate": _fetch_hashrate(client),
            "difficulty": _fetch_difficulty(client),
            "supply": _fetch_supply(client),
        }

        results = {}
        for key, coro in tasks.items():
            try:
                results[key] = await coro
            except Exception as e:
                logger.warning(f"On-chain {key} failed: {e}")
                results[key] = None

    # Build combined result
    mempool = results.get("mempool") or {}
    fees = results.get("fees") or {}
    hashrate = results.get("hashrate") or {}
    difficulty = results.get("difficulty") or {}
    supply = results.get("supply") or {}

    result.update({
        "available": any(results.values()),
        "mempool": mempool,
        "fees": fees,
        "hashrate": hashrate,
        "difficulty": difficulty,
        "supply": supply,
    })

    if result["available"]:
        _onchain_cache = result
        _cache_time = now
        logger.info(f"⛓️ On-chain data fetched: mempool={mempool.get('tx_count', '?')} tx, "
                     f"fee={fees.get('fastest', '?')} sat/vB")

    return result


async def _fetch_mempool_stats(client: httpx.AsyncClient) -> dict:
    """Fetch mempool statistics from mempool.space."""
    resp = await client.get(f"{MEMPOOL_API}/mempool")
    if resp.status_code != 200:
        return {}

    data = resp.json()
    tx_count = data.get("count", 0)
    vsize = data.get("vsize", 0)

    # Mempool congestion assessment
    if tx_count > 100000:
        congestion = "extremt hög"
    elif tx_count > 50000:
        congestion = "hög"
    elif tx_count > 20000:
        congestion = "måttlig"
    else:
        congestion = "låg"

    return {
        "tx_count": tx_count,
        "vsize_mb": round(vsize / 1_000_000, 1),
        "congestion": congestion,
    }


async def _fetch_fee_estimates(client: httpx.AsyncClient) -> dict:
    """Fetch recommended fees from mempool.space."""
    resp = await client.get(f"{MEMPOOL_API}/v1/fees/recommended")
    if resp.status_code != 200:
        return {}

    data = resp.json()
    fastest = data.get("fastestFee", 0)

    # Fee pressure assessment
    if fastest > 100:
        pressure = "extremt hög"
    elif fastest > 50:
        pressure = "hög"
    elif fastest > 20:
        pressure = "måttlig"
    elif fastest > 5:
        pressure = "normal"
    else:
        pressure = "låg"

    return {
        "fastest": data.get("fastestFee", 0),
        "half_hour": data.get("halfHourFee", 0),
        "hour": data.get("hourFee", 0),
        "economy": data.get("economyFee", 0),
        "minimum": data.get("minimumFee", 0),
        "pressure": pressure,
        "unit": "sat/vB",
    }


async def _fetch_hashrate(client: httpx.AsyncClient) -> dict:
    """Fetch hashrate from mempool.space."""
    resp = await client.get(f"{MEMPOOL_API}/v1/mining/hashrate/1m")
    if resp.status_code != 200:
        return {}

    data = resp.json()
    hashrates = data.get("hashrates", [])
    current_difficulty = data.get("currentDifficulty", 0)

    if hashrates:
        latest = hashrates[-1]
        current_hr = latest.get("avgHashrate", 0)
        # Convert to EH/s (exahashes)
        hr_eh = current_hr / 1e18

        # Trend: compare last vs 7d ago
        if len(hashrates) >= 7:
            week_ago_hr = hashrates[-7].get("avgHashrate", current_hr)
            hr_change = ((current_hr - week_ago_hr) / week_ago_hr * 100) if week_ago_hr > 0 else 0
        else:
            hr_change = 0

        return {
            "current_eh": round(hr_eh, 1),
            "weekly_change_pct": round(hr_change, 1),
            "trend": "stigande" if hr_change > 2 else "fallande" if hr_change < -2 else "stabil",
        }

    return {}


async def _fetch_difficulty(client: httpx.AsyncClient) -> dict:
    """Fetch difficulty adjustment info from mempool.space."""
    resp = await client.get(f"{MEMPOOL_API}/v1/difficulty-adjustment")
    if resp.status_code != 200:
        return {}

    data = resp.json()
    return {
        "progress_pct": round(data.get("progressPercent", 0), 1),
        "estimated_change_pct": round(data.get("difficultyChange", 0), 2),
        "remaining_blocks": data.get("remainingBlocks", 0),
        "estimated_date": data.get("estimatedRetargetDate"),
    }


async def _fetch_supply(client: httpx.AsyncClient) -> dict:
    """Fetch BTC supply from blockchain.info."""
    try:
        resp = await client.get(f"{BLOCKCHAIN_API}/q/totalbc")
        if resp.status_code == 200:
            total_satoshis = int(resp.text.strip())
            total_btc = total_satoshis / 1e8
            max_supply = 21_000_000
            pct_mined = (total_btc / max_supply) * 100
            remaining = max_supply - total_btc

            return {
                "total_btc": round(total_btc, 2),
                "max_supply": max_supply,
                "pct_mined": round(pct_mined, 2),
                "remaining_btc": round(remaining, 2),
            }
    except Exception:
        pass
    return {}


def format_onchain_for_prompt(data: dict) -> str:
    """Format on-chain data as text for agent prompts."""
    if not data or not data.get("available"):
        return ""

    parts = ["ON-CHAIN DATA (Bitcoin-nätverket):"]

    # Mempool
    mp = data.get("mempool", {})
    if mp:
        parts.append(f"  Mempool: {mp.get('tx_count', '?'):,} transaktioner "
                     f"({mp.get('vsize_mb', '?')} MB, trängsel: {mp.get('congestion', '?')})")

    # Fees
    fees = data.get("fees", {})
    if fees:
        parts.append(f"  Avgifter: {fees.get('fastest', '?')} sat/vB snabbast, "
                     f"{fees.get('hour', '?')} sat/vB inom 1h "
                     f"(tryck: {fees.get('pressure', '?')})")

    # Hashrate
    hr = data.get("hashrate", {})
    if hr:
        parts.append(f"  Hashrate: {hr.get('current_eh', '?')} EH/s "
                     f"({hr.get('trend', '?')}, {hr.get('weekly_change_pct', 0):+.1f}% vecka)")

    # Difficulty
    diff = data.get("difficulty", {})
    if diff and diff.get("estimated_change_pct") is not None:
        parts.append(f"  Svårighetsgrad: nästa justering {diff['estimated_change_pct']:+.1f}% "
                     f"(progress: {diff.get('progress_pct', '?')}%)")

    # Supply
    supply = data.get("supply", {})
    if supply:
        parts.append(f"  Supply: {supply.get('total_btc', '?'):,.0f} BTC utvunna "
                     f"({supply.get('pct_mined', '?')}% av max 21M)")

    # High fee/congestion warning
    if fees.get("pressure") in ("hög", "extremt hög"):
        parts.append(f"  ⚠️ Höga avgifter – indikerar stark nätverksaktivitet")
    if mp.get("congestion") in ("hög", "extremt hög"):
        parts.append(f"  ⚠️ Mempoolträngsel – möjlig köptryck eller panikförsäljning")

    return "\n".join(parts)


# Convenience function for sync contexts
def get_cached_onchain() -> dict:
    """Return cached on-chain data (call fetch_onchain_data() to refresh)."""
    return _onchain_cache or {"available": False}
