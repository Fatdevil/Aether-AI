# ============================================================
# backend/lead_lag_trainer.py
# Data-validerar lead-lag-par med 20 ars historisk data.
#
# Beraknar:
# 1. Laggad korrelation for ALLA 400 par (20x20) vid lag 1-20
# 2. Stabilitet: 4 femar-perioder, minst 3 av 4 > 0.20
# 3. Regim-specifik korrelation (RISK_ON, RISK_OFF, CRISIS, NEUTRAL)
# 4. Jamfor med hardkodade KNOWN_PAIRS
# ============================================================

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("aether.lead_lag_trainer")

# Map between historical data column names and lead_lag.py asset IDs
HISTORICAL_TO_ASSET_ID = {
    "SP500": "sp500",
    "VIX": "vix",
    "US10Y_Yield": "us10y",
    "Gold": "gold",
    "Silver": "silver",
    "WTI_Oil": "oil",
    "Dollar_Index": "dxy",
    "Copper": "copper",
    "HY_Credit": "hyg",
    "OMXS30": "omxs30",
    "Tech_XLK": "sector-tech",
    "Energy_XLE": "sector-energy",
    "Finance_XLF": "sector-finance",
    "Health_XLV": "sector-health",
    "Defense_ITA": "sector-defense",
    "EM_EEM": "region-em",
    "Europe_VGK": "region-europe",
    "Japan_EWJ": "region-japan",
    "Bitcoin": "btc",
    "EURUSD": "eurusd",
}

ASSET_ID_TO_HISTORICAL = {v: k for k, v in HISTORICAL_TO_ASSET_ID.items()}

# Existing hardcoded pairs to compare against
HARDCODED_PAIRS = [
    {"leader": "us10y", "follower": "sp500", "expected_direction": "INVERSE"},
    {"leader": "gold", "follower": "silver", "expected_direction": "SAME"},
    {"leader": "oil", "follower": "gold", "expected_direction": "SAME"},
    {"leader": "us10y", "follower": "gold", "expected_direction": "INVERSE"},
    {"leader": "sp500", "follower": "global-equity", "expected_direction": "SAME"},
    {"leader": "gold", "follower": "btc", "expected_direction": "SAME"},
    {"leader": "us10y", "follower": "btc", "expected_direction": "INVERSE"},
    {"leader": "oil", "follower": "sp500", "expected_direction": "INVERSE"},
    {"leader": "eurusd", "follower": "gold", "expected_direction": "SAME"},
    {"leader": "sp500", "follower": "btc", "expected_direction": "SAME"},
]

STABILITY_PERIODS = [
    ("2005-01-01", "2010-01-01"),
    ("2010-01-01", "2015-01-01"),
    ("2015-01-01", "2020-01-01"),
    ("2020-01-01", "2025-01-01"),
]

REGIME_NAMES = {0: "RISK_ON", 1: "NEUTRAL", 2: "RISK_OFF", 3: "CRISIS"}


@dataclass
class ValidatedPair:
    leader: str
    follower: str
    optimal_lag_days: int
    correlation: float
    direction: str
    description: str
    historical_correlation: float
    stability_score: int  # out of 4 periods
    period_correlations: Dict[str, float] = field(default_factory=dict)
    regime_correlations: Dict[str, float] = field(default_factory=dict)
    regime_tags: List[str] = field(default_factory=list)
    is_universal: bool = False
    is_regime_specific: bool = False


# ============================================================
# CORE COMPUTATION
# ============================================================

def compute_lagged_correlation(
    leader_returns: np.ndarray,
    follower_returns: np.ndarray,
    max_lag: int = 20,
) -> Tuple[int, float]:
    """
    Berakna optimal lag och korrelation for ett par.
    Returns (optimal_lag, best_correlation).
    """
    best_lag = 0
    best_corr = 0.0

    for lag in range(1, max_lag + 1):
        if lag >= len(leader_returns):
            break

        leader_slice = leader_returns[:-lag]
        follower_slice = follower_returns[lag:]

        min_len = min(len(leader_slice), len(follower_slice))
        if min_len < 30:
            continue

        leader_slice = leader_slice[:min_len]
        follower_slice = follower_slice[:min_len]

        valid = ~(np.isnan(leader_slice) | np.isnan(follower_slice))
        if valid.sum() < 30:
            continue

        corr = float(np.corrcoef(leader_slice[valid], follower_slice[valid])[0, 1])
        if np.isnan(corr):
            continue

        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag

    return best_lag, best_corr


def compute_all_pairs(returns: pd.DataFrame, max_lag: int = 20) -> List[Dict]:
    """
    Berakna laggad korrelation for ALLA par (N x N).
    Returns list of dicts med leader, follower, lag, corr.
    """
    assets = list(returns.columns)
    results = []

    for leader in assets:
        for follower in assets:
            if leader == follower:
                continue

            lag, corr = compute_lagged_correlation(
                returns[leader].values,
                returns[follower].values,
                max_lag=max_lag,
            )

            if abs(corr) > 0.15:  # Low threshold — we filter later
                results.append({
                    "leader": leader,
                    "follower": follower,
                    "optimal_lag": lag,
                    "correlation": round(corr, 4),
                    "abs_corr": round(abs(corr), 4),
                    "direction": "SAME" if corr > 0 else "INVERSE",
                })

    results.sort(key=lambda x: x["abs_corr"], reverse=True)
    return results


def stability_test(
    returns: pd.DataFrame,
    leader: str,
    follower: str,
    optimal_lag: int,
    periods: List[Tuple[str, str]] = None,
    min_corr: float = 0.20,
) -> Tuple[int, Dict[str, float]]:
    """
    Test pair stability across time periods.
    Returns (stable_count, period_correlations).
    """
    if periods is None:
        periods = STABILITY_PERIODS

    stable_count = 0
    period_corrs = {}

    for start, end in periods:
        period_label = f"{start[:4]}-{end[:4]}"
        mask = (returns.index >= pd.Timestamp(start)) & (returns.index < pd.Timestamp(end))
        period_returns = returns[mask]

        if leader not in period_returns.columns or follower not in period_returns.columns:
            period_corrs[period_label] = 0.0
            continue

        leader_ret = period_returns[leader].values
        follower_ret = period_returns[follower].values

        if len(leader_ret) < 50:
            period_corrs[period_label] = 0.0
            continue

        _, corr = compute_lagged_correlation(leader_ret, follower_ret, max_lag=optimal_lag + 5)
        period_corrs[period_label] = round(corr, 4)

        if abs(corr) >= min_corr:
            stable_count += 1

    return stable_count, period_corrs


def regime_correlation(
    returns: pd.DataFrame,
    regime_labels: pd.Series,
    leader: str,
    follower: str,
    optimal_lag: int,
) -> Dict[str, float]:
    """
    Berakna lead-lag-korrelation per regim.
    """
    regime_corrs = {}

    for regime_code, regime_name in REGIME_NAMES.items():
        mask = regime_labels == regime_code
        regime_returns = returns[mask]

        if len(regime_returns) < 50:
            regime_corrs[regime_name] = 0.0
            continue

        if leader not in regime_returns.columns or follower not in regime_returns.columns:
            regime_corrs[regime_name] = 0.0
            continue

        _, corr = compute_lagged_correlation(
            regime_returns[leader].values,
            regime_returns[follower].values,
            max_lag=max(optimal_lag + 5, 10),
        )
        regime_corrs[regime_name] = round(corr, 4)

    return regime_corrs


# ============================================================
# MAIN TRAINING PIPELINE
# ============================================================

def train_lead_lag(
    min_overall_corr: float = 0.20,
    min_stability_periods: int = 2,
    min_regime_corr: float = 0.20,
    min_regime_only_corr: float = 0.30,
) -> Dict:
    """
    Full lead-lag training pipeline:
    1. Load historical data + regime labels
    2. Compute all 380 pairs at lag 1-20
    3. PASS 1: Filter by |overall_corr| >= 0.20 + stability >= 2/4
    4. PASS 2: Regime-only pairs — |regime_corr| >= 0.30 in RISK_OFF/CRISIS
       even if overall correlation is weak (these pairs only activate in stress)
    5. Compare with hardcoded pairs
    """
    from historical_data_loader import load_all
    from regime_classifier import label_dates, REGIME_MAP

    print("\n  Loading historical data...")
    prices = load_all()
    returns = prices.pct_change().dropna(how="all")

    # Forward-fill for stability
    returns = returns.ffill(limit=5)

    # Regime labels
    regime_str_labels = label_dates(returns.index)
    regime_labels = regime_str_labels.map(REGIME_MAP)

    print(f"  Data: {len(returns)} days, {len(returns.columns)} assets")
    print(f"  Pairs to test: {len(returns.columns) * (len(returns.columns) - 1)}")

    # Step 1: Compute all pairs
    print("\n  Computing all lagged correlations...")
    all_pairs = compute_all_pairs(returns, max_lag=20)
    print(f"  Found {len(all_pairs)} pairs with |corr| > 0.15")

    # ============ PASS 1: Overall correlation + stability ============
    strong_pairs = [p for p in all_pairs if p["abs_corr"] >= min_overall_corr]
    print(f"  PASS 1 filter |corr| >= {min_overall_corr}: {len(strong_pairs)} pairs")

    print("  Running stability tests...")
    validated_pairs = []
    seen_keys = set()

    for pair in strong_pairs:
        leader = pair["leader"]
        follower = pair["follower"]
        lag = pair["optimal_lag"]

        stable_count, period_corrs = stability_test(
            returns, leader, follower, lag,
            min_corr=0.15,  # Lower for per-period check
        )

        if stable_count < min_stability_periods:
            continue

        regime_corrs = regime_correlation(
            returns, regime_labels, leader, follower, lag,
        )

        regime_tags = []
        universal = True
        for regime_name, r_corr in regime_corrs.items():
            if abs(r_corr) >= min_regime_corr:
                regime_tags.append(regime_name)
            else:
                universal = False

        is_regime_specific = len(regime_tags) > 0 and not universal

        leader_id = HISTORICAL_TO_ASSET_ID.get(leader, leader.lower())
        follower_id = HISTORICAL_TO_ASSET_ID.get(follower, follower.lower())

        pair_key = tuple(sorted([leader_id, follower_id]))
        if pair_key in seen_keys:
            continue
        seen_keys.add(pair_key)

        vp = ValidatedPair(
            leader=leader_id,
            follower=follower_id,
            optimal_lag_days=lag,
            correlation=pair["correlation"],
            direction=pair["direction"],
            description=_generate_description(leader_id, follower_id, pair["direction"], lag),
            historical_correlation=pair["correlation"],
            stability_score=stable_count,
            period_correlations=period_corrs,
            regime_correlations=regime_corrs,
            regime_tags=regime_tags,
            is_universal=universal and len(regime_tags) > 0,
            is_regime_specific=is_regime_specific,
        )
        validated_pairs.append(vp)

    print(f"  PASS 1 validated: {len(validated_pairs)} pairs")

    # ============ PASS 2: Regime-specific pairs ============
    # Check ALL candidate pairs (|corr| > 0.15) for strong regime-specific signal
    print("\n  PASS 2: Scanning for regime-specific pairs...")
    regime_only_count = 0

    for pair in all_pairs:
        leader = pair["leader"]
        follower = pair["follower"]
        lag = pair["optimal_lag"]

        leader_id = HISTORICAL_TO_ASSET_ID.get(leader, leader.lower())
        follower_id = HISTORICAL_TO_ASSET_ID.get(follower, follower.lower())

        pair_key = tuple(sorted([leader_id, follower_id]))
        if pair_key in seen_keys:
            continue

        regime_corrs = regime_correlation(
            returns, regime_labels, leader, follower, lag,
        )

        # Check if strong in at least one critical regime
        regime_tags = []
        for regime_name in ["RISK_OFF", "CRISIS", "RISK_ON"]:
            r_corr = regime_corrs.get(regime_name, 0)
            if abs(r_corr) >= min_regime_only_corr:
                regime_tags.append(regime_name)

        if not regime_tags:
            continue

        seen_keys.add(pair_key)
        stable_count, period_corrs = stability_test(
            returns, leader, follower, lag, min_corr=0.15,
        )

        vp = ValidatedPair(
            leader=leader_id,
            follower=follower_id,
            optimal_lag_days=lag,
            correlation=pair["correlation"],
            direction=pair["direction"],
            description=_generate_description(leader_id, follower_id, pair["direction"], lag),
            historical_correlation=pair["correlation"],
            stability_score=stable_count,
            period_correlations=period_corrs,
            regime_correlations=regime_corrs,
            regime_tags=regime_tags,
            is_universal=False,
            is_regime_specific=True,
        )
        validated_pairs.append(vp)
        regime_only_count += 1

    print(f"  PASS 2 regime-only pairs added: {regime_only_count}")

    # Sort by abs correlation
    validated_pairs.sort(key=lambda x: abs(x.correlation), reverse=True)

    print(f"  TOTAL validated pairs: {len(validated_pairs)}")

    # Compare with hardcoded pairs
    comparison = _compare_with_hardcoded(validated_pairs, returns)

    # Categorize
    universal = [vp for vp in validated_pairs if vp.is_universal]
    regime_specific = [vp for vp in validated_pairs if vp.is_regime_specific]
    other = [vp for vp in validated_pairs if not vp.is_universal and not vp.is_regime_specific]

    return {
        "validated_pairs": validated_pairs,
        "universal_pairs": universal,
        "regime_specific_pairs": regime_specific,
        "other_pairs": other,
        "comparison": comparison,
        "total_tested": len(returns.columns) * (len(returns.columns) - 1),
        "passed_corr_filter": len(strong_pairs),
        "passed_stability": len(validated_pairs),
    }


def _generate_description(leader: str, follower: str, direction: str, lag: int) -> str:
    """Generate human-readable description for a pair."""
    if direction == "SAME":
        return f"{leader} leder {follower} (samma riktning, {lag}d lag)"
    else:
        return f"{leader} leder {follower} (omvant, {lag}d lag)"


def _compare_with_hardcoded(validated_pairs: List[ValidatedPair], returns: pd.DataFrame) -> Dict:
    """Compare validated pairs with hardcoded KNOWN_PAIRS."""
    confirmed = []
    falsified = []

    validated_lookup = {}
    for vp in validated_pairs:
        validated_lookup[(vp.leader, vp.follower)] = vp

    for hp in HARDCODED_PAIRS:
        leader = hp["leader"]
        follower = hp["follower"]

        # Check if 'global-equity' exists in data (it doesn't)
        leader_hist = ASSET_ID_TO_HISTORICAL.get(leader)
        follower_hist = ASSET_ID_TO_HISTORICAL.get(follower)

        if leader_hist is None or follower_hist is None:
            falsified.append({
                **hp,
                "reason": f"Asset not in historical data ({leader if not leader_hist else follower})",
                "data_validated": False,
            })
            continue

        # Check if this pair is in validated set
        vp = validated_lookup.get((leader, follower))
        if vp:
            direction_match = vp.direction == hp["expected_direction"]
            confirmed.append({
                **hp,
                "validated_corr": vp.correlation,
                "validated_lag": vp.optimal_lag_days,
                "validated_direction": vp.direction,
                "direction_confirmed": direction_match,
                "stability": vp.stability_score,
                "regime_tags": vp.regime_tags,
            })
        else:
            # Compute directly to show why it failed
            if leader_hist in returns.columns and follower_hist in returns.columns:
                lag, corr = compute_lagged_correlation(
                    returns[leader_hist].values, returns[follower_hist].values
                )
                falsified.append({
                    **hp,
                    "actual_corr": round(corr, 4),
                    "actual_lag": lag,
                    "reason": f"|corr|={abs(corr):.3f} < 0.25 or unstable across periods",
                    "data_validated": False,
                })
            else:
                falsified.append({
                    **hp,
                    "reason": "Missing from returns data",
                    "data_validated": False,
                })

    return {"confirmed": confirmed, "falsified": falsified}


# ============================================================
# GENERATE KNOWN_PAIRS REPLACEMENT
# ============================================================

def generate_known_pairs_code(validated_pairs: List[ValidatedPair], top_n: int = 20) -> str:
    """Generate Python code for new KNOWN_PAIRS list."""
    lines = ["KNOWN_PAIRS = ["]
    for vp in validated_pairs[:top_n]:
        regime_note = ""
        if vp.is_universal:
            regime_note = " | Universal"
        elif vp.regime_tags:
            regime_note = f" | Regim: {', '.join(vp.regime_tags)}"

        lines.append(f'    {{"leader": "{vp.leader}", "follower": "{vp.follower}", '
                     f'"expected_direction": "{vp.direction}",')
        lines.append(f'     "optimal_lag_days": {vp.optimal_lag_days}, '
                     f'"historical_correlation": {vp.correlation},')
        lines.append(f'     "stability": {vp.stability_score}, '
                     f'"description": "{vp.description}{regime_note}"}},')
    lines.append("]")
    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n" + "=" * 70)
    print("  AETHER AI -- LEAD-LAG TRAINER")
    print("=" * 70)

    results = train_lead_lag()

    # Print results
    print("\n" + "=" * 70)
    print(f"  RESULTS: {results['passed_stability']} validated pairs "
          f"(from {results['total_tested']} tested)")
    print("=" * 70)

    # Top 10 pairs
    print("\n  TOP 10 VALIDATED PAIRS:")
    print(f"  {'Leader':<16} {'Follower':<16} {'Lag':>4} {'Corr':>7} {'Dir':>8} {'Stab':>5} {'Regime Tags'}")
    print(f"  {'-'*16} {'-'*16} {'-'*4} {'-'*7} {'-'*8} {'-'*5} {'-'*30}")
    for vp in results["validated_pairs"][:10]:
        tags = ", ".join(vp.regime_tags) if vp.regime_tags else "none"
        print(f"  {vp.leader:<16} {vp.follower:<16} {vp.optimal_lag_days:>4} "
              f"{vp.correlation:>+7.3f} {vp.direction:>8} {vp.stability_score:>3}/4 {tags}")

    # Universal pairs
    print(f"\n  UNIVERSAL PAIRS (work in all regimes): {len(results['universal_pairs'])}")
    for vp in results["universal_pairs"]:
        print(f"    {vp.leader} -> {vp.follower}: corr={vp.correlation:+.3f}, lag={vp.optimal_lag_days}d")

    # Regime-specific pairs
    print(f"\n  REGIME-SPECIFIC PAIRS: {len(results['regime_specific_pairs'])}")
    for vp in results["regime_specific_pairs"][:10]:
        tags = ", ".join(vp.regime_tags)
        print(f"    {vp.leader} -> {vp.follower}: corr={vp.correlation:+.3f}, "
              f"lag={vp.optimal_lag_days}d [{tags}]")

    # Comparison with hardcoded
    comp = results["comparison"]
    print(f"\n  HARDCODED PAIRS COMPARISON:")
    print(f"  Confirmed: {len(comp['confirmed'])}")
    for c in comp["confirmed"]:
        dir_ok = "OK" if c["direction_confirmed"] else "WRONG DIR"
        print(f"    {c['leader']} -> {c['follower']}: corr={c['validated_corr']:+.3f}, "
              f"lag={c['validated_lag']}d, dir={dir_ok}, stab={c['stability']}/4")

    print(f"  Falsified: {len(comp['falsified'])}")
    for f in comp["falsified"]:
        print(f"    {f['leader']} -> {f['follower']}: {f['reason']}")

    # Generate new KNOWN_PAIRS code
    print("\n  GENERATED KNOWN_PAIRS CODE:")
    print("  " + "-" * 60)
    code = generate_known_pairs_code(results["validated_pairs"])
    print(code)
