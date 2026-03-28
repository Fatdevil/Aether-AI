# ============================================================
# backend/regime_signal_trainer.py
# Traner regim-specifika signalvikter med Ridge regression.
#
# Del A: Dela data per regim (RISK_ON, NEUTRAL, RISK_OFF+CRISIS)
# Del B: Trana Ridge regression per regim + walk-forward
# Del C: Extrahera vikter, jamfor single vs regime-specific
# Del D: MetaStrategy-rekommendationer
# ============================================================

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger("aether.regime_signal_trainer")

MODEL_DIR = Path(__file__).parent / "models"

# Walk-forward folds (samma som Steg 2)
WALK_FORWARD_FOLDS = [
    {"train_end": "2015-01-01", "test_start": "2015-01-01", "test_end": "2017-01-01"},
    {"train_end": "2017-01-01", "test_start": "2017-01-01", "test_end": "2019-01-01"},
    {"train_end": "2019-01-01", "test_start": "2019-01-01", "test_end": "2021-01-01"},
    {"train_end": "2021-01-01", "test_start": "2021-01-01", "test_end": "2023-01-01"},
    {"train_end": "2023-01-01", "test_start": "2023-01-01", "test_end": "2025-01-01"},
]

# Regime groupings (CRISIS merged into RISK_OFF — too few CRISIS samples alone)
REGIME_GROUPS = {
    "RISK_ON": [0],       # RISK_ON=0
    "NEUTRAL": [1],       # NEUTRAL=1
    "RISK_OFF": [2, 3],   # RISK_OFF=2 + CRISIS=3
}


# ============================================================
# DEL A: PREPARE DATA PER REGIME
# ============================================================

def prepare_data() -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Bygg features + next-day SP500 return + regime labels.
    Returns (features, target, regime_labels).
    """
    from historical_data_loader import load_all
    from regime_classifier import (
        compute_regime_features, label_dates, REGIME_MAP,
        REQUIRED_ASSETS,
    )

    prices = load_all()

    # Filter to required assets + forward-fill
    available = [c for c in REQUIRED_ASSETS if c in prices.columns]
    prices_filtered = prices[available].copy()
    prices_filtered = prices_filtered.ffill(limit=5)
    prices_filtered = prices_filtered.dropna(how="all")

    # Compute features
    features = compute_regime_features(prices_filtered)

    # Target: next-day SP500 return
    sp500_returns = prices_filtered["SP500"].pct_change()
    target = sp500_returns.shift(-1)  # Shift by -1 = NEXT day's return

    # Regime labels
    regime_str = label_dates(features.index)
    regime_labels = regime_str.map(REGIME_MAP)

    # Align and drop NaN
    valid = features.notna().all(axis=1) & target.notna() & regime_labels.notna()
    features = features[valid]
    target = target[valid]
    regime_labels = regime_labels[valid].astype(int)

    return features, target, regime_labels


def split_by_regime(
    features: pd.DataFrame,
    target: pd.Series,
    regime_labels: pd.Series,
) -> Dict[str, Tuple[pd.DataFrame, pd.Series]]:
    """Dela data i tre regimgrupper."""
    splits = {}
    for group_name, codes in REGIME_GROUPS.items():
        mask = regime_labels.isin(codes)
        splits[group_name] = (features[mask], target[mask])
    return splits


# ============================================================
# DEL B: TRAIN RIDGE REGRESSION PER REGIME
# ============================================================

def train_single_model(X: pd.DataFrame, y: pd.Series, alpha: float = 10.0):
    """Trana en Ridge-modell."""
    from sklearn.linear_model import Ridge
    model = Ridge(alpha=alpha)
    model.fit(X, y)
    return model


def walk_forward_regime(
    features: pd.DataFrame,
    target: pd.Series,
    regime_labels: pd.Series,
    alpha: float = 10.0,
) -> Dict:
    """
    Walk-forward-validering: trana per-regim Ridge + single Ridge.
    Rapporterar R^2 per fold for bade regim-specifik och enstaka modell.
    """
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score, mean_squared_error

    results = {
        "per_regime": {name: [] for name in REGIME_GROUPS},
        "single_model": [],
        "fold_details": [],
    }

    for fold_idx, fold in enumerate(WALK_FORWARD_FOLDS):
        train_mask = features.index < pd.Timestamp(fold["train_end"])
        test_mask = (
            (features.index >= pd.Timestamp(fold["test_start"]))
            & (features.index < pd.Timestamp(fold["test_end"]))
        )

        X_train_all, y_train_all = features[train_mask], target[train_mask]
        X_test_all, y_test_all = features[test_mask], target[test_mask]
        rl_train = regime_labels[train_mask]
        rl_test = regime_labels[test_mask]

        if len(X_train_all) < 200 or len(X_test_all) < 100:
            continue

        fold_detail = {"fold": fold_idx + 1, "test_period": f"{fold['test_start']}→{fold['test_end']}"}

        # --- SINGLE MODEL (baseline) ---
        single = Ridge(alpha=alpha)
        single.fit(X_train_all, y_train_all)
        y_pred_single = single.predict(X_test_all)
        r2_single = r2_score(y_test_all, y_pred_single)
        mse_single = mean_squared_error(y_test_all, y_pred_single)
        results["single_model"].append({"fold": fold_idx + 1, "r2": r2_single, "mse": mse_single})
        fold_detail["single_r2"] = round(r2_single, 6)

        # --- PER-REGIME MODELS ---
        y_pred_regime = pd.Series(np.nan, index=X_test_all.index)

        for group_name, codes in REGIME_GROUPS.items():
            # Train on regime-specific data
            train_regime_mask = rl_train.isin(codes)
            X_train_r = X_train_all[train_regime_mask]
            y_train_r = y_train_all[train_regime_mask]

            if len(X_train_r) < 30:
                # Fallback to single model for this regime
                fold_detail[f"{group_name}_r2"] = None
                fold_detail[f"{group_name}_n_train"] = len(X_train_r)
                continue

            model_r = Ridge(alpha=alpha)
            model_r.fit(X_train_r, y_train_r)

            # Predict test days that belong to this regime
            test_regime_mask = rl_test.isin(codes)
            X_test_r = X_test_all[test_regime_mask]
            y_test_r = y_test_all[test_regime_mask]

            if len(X_test_r) < 10:
                fold_detail[f"{group_name}_r2"] = None
                fold_detail[f"{group_name}_n_test"] = len(X_test_r)
                continue

            y_pred_r = model_r.predict(X_test_r)
            r2_r = r2_score(y_test_r, y_pred_r)
            y_pred_regime[test_regime_mask] = y_pred_r

            results["per_regime"][group_name].append({
                "fold": fold_idx + 1,
                "r2": r2_r,
                "n_train": len(X_train_r),
                "n_test": len(X_test_r),
            })
            fold_detail[f"{group_name}_r2"] = round(r2_r, 6)
            fold_detail[f"{group_name}_n_train"] = len(X_train_r)
            fold_detail[f"{group_name}_n_test"] = len(X_test_r)

        # Combined regime R² (using regime-specific predictions)
        valid_pred = y_pred_regime.notna()
        if valid_pred.sum() > 50:
            r2_combined = r2_score(y_test_all[valid_pred], y_pred_regime[valid_pred])
            fold_detail["combined_regime_r2"] = round(r2_combined, 6)

        results["fold_details"].append(fold_detail)

    return results


# ============================================================
# DEL C: EXTRACT WEIGHTS + FINAL TRAINING
# ============================================================

def train_final_models(
    features: pd.DataFrame,
    target: pd.Series,
    regime_labels: pd.Series,
    alpha: float = 10.0,
) -> Dict:
    """
    Trana slutliga modeller pa ALL data. Extrahera vikter per regim.
    Spara modeller till disk.
    """
    from sklearn.linear_model import Ridge

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    weights = {}

    # Single model
    single = Ridge(alpha=alpha)
    single.fit(features, target)
    joblib.dump(single, MODEL_DIR / "signal_weights_single.joblib")
    weights["SINGLE"] = _extract_weights(single, features.columns)

    # Per-regime models
    for group_name, codes in REGIME_GROUPS.items():
        mask = regime_labels.isin(codes)
        X_r = features[mask]
        y_r = target[mask]

        if len(X_r) < 50:
            continue

        model = Ridge(alpha=alpha)
        model.fit(X_r, y_r)
        joblib.dump(model, MODEL_DIR / f"signal_weights_{group_name.lower()}.joblib")
        weights[group_name] = _extract_weights(model, features.columns)

    return weights


def _extract_weights(model, feature_names) -> pd.DataFrame:
    """Extrahera normaliserade vikter fran Ridge-modell."""
    coefs = model.coef_
    abs_sum = np.sum(np.abs(coefs))
    if abs_sum == 0:
        abs_sum = 1

    df = pd.DataFrame({
        "feature": list(feature_names),
        "raw_weight": coefs,
        "normalized_weight": coefs / abs_sum,
        "abs_normalized": np.abs(coefs) / abs_sum,
        "direction": ["+" if c > 0 else "-" for c in coefs],
    }).sort_values("abs_normalized", ascending=False)

    return df


# ============================================================
# DEL D: METASTRATEGY RECOMMENDATIONS
# ============================================================

def generate_meta_recommendations(
    wf_results: Dict,
    weights: Dict,
) -> Dict:
    """
    Generera MetaStrategy-vikter baserat pa:
    - Steg 2: Regimklassificering = 72% OOS (systemets starkaste modul)
    - Steg 3: Lead-lag = svaga korrelationer (0.20-0.27)
    - Steg 4: Ridge R^2 per regim
    """
    # Base recommendations
    recommendations = {
        "module_weights": {
            "regime_detection": {
                "weight": 0.30,
                "justification": "72% OOS accuracy - strongest predictive module",
            },
            "causal_chains": {
                "weight": 0.25,
                "justification": "Complementary to regime; domain-knowledge-driven",
            },
            "agent_consensus": {
                "weight": 0.20,
                "justification": "Multi-agent agreement still valuable as ensemble signal",
            },
            "lead_lag_signals": {
                "weight": 0.10,
                "justification": "Weak correlations (0.20-0.27); only 6 validated pairs; mostly timezone effects",
            },
            "technical_signals": {
                "weight": 0.10,
                "justification": "ROC/momentum features contribute ~20% to regime classifier",
            },
            "narrative_tracking": {
                "weight": 0.05,
                "justification": "Qualitative; hard to validate with historical data",
            },
        },
    }

    # Compute average R² per regime from walk-forward
    regime_r2 = {}
    for regime_name, fold_results in wf_results["per_regime"].items():
        if fold_results:
            avg_r2 = np.mean([f["r2"] for f in fold_results])
            regime_r2[regime_name] = round(avg_r2, 6)

    single_r2_avg = 0
    if wf_results["single_model"]:
        single_r2_avg = np.mean([f["r2"] for f in wf_results["single_model"]])

    # Decision: use regime-specific weights or single model?
    any_regime_better = any(
        regime_r2.get(r, -999) > single_r2_avg
        for r in REGIME_GROUPS
    )

    recommendations["regime_weights_decision"] = {
        "single_model_avg_r2": round(single_r2_avg, 6),
        "per_regime_avg_r2": regime_r2,
        "use_regime_specific": any_regime_better,
        "reasoning": (
            "Regime-specific weights recommended" if any_regime_better
            else "Single model sufficient — regime-specific models don't improve OOS R²"
        ),
    }

    # Top features per regime
    regime_top_features = {}
    for regime_name, w_df in weights.items():
        if regime_name == "SINGLE":
            continue
        top5 = w_df.head(5)[["feature", "normalized_weight", "direction"]].to_dict("records")
        regime_top_features[regime_name] = top5

    recommendations["regime_top_features"] = regime_top_features

    return recommendations


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n" + "=" * 70)
    print("  AETHER AI -- REGIME SIGNAL WEIGHT TRAINER")
    print("=" * 70)

    # Step 1: Prepare data
    print("\n  Preparing data...")
    features, target, regime_labels = prepare_data()
    print(f"  Total samples: {len(features)}")
    print(f"  Features: {len(features.columns)}")
    print(f"  Target: next-day SP500 return")

    # Show regime distribution
    splits = split_by_regime(features, target, regime_labels)
    for name, (X_r, y_r) in splits.items():
        avg_ret = y_r.mean() * 100
        std_ret = y_r.std() * 100
        print(f"  {name}: {len(X_r)} days (avg return: {avg_ret:+.3f}%, std: {std_ret:.3f}%)")

    # Step 2: Walk-forward validation
    print("\n  Walk-forward validation (5 folds)...")
    wf_results = walk_forward_regime(features, target, regime_labels)

    print(f"\n  {'='*70}")
    print(f"  WALK-FORWARD RESULTS")
    print(f"  {'='*70}")

    for fd in wf_results["fold_details"]:
        print(f"\n  Fold {fd['fold']}: {fd.get('test_period', '')}")
        print(f"    Single model R2:        {fd.get('single_r2', 'N/A')}")
        for regime in REGIME_GROUPS:
            r2 = fd.get(f"{regime}_r2", "N/A")
            n_train = fd.get(f"{regime}_n_train", "?")
            n_test = fd.get(f"{regime}_n_test", "?")
            print(f"    {regime:<10} R2: {r2}  (train={n_train}, test={n_test})")
        combined = fd.get("combined_regime_r2", "N/A")
        print(f"    Combined regime R2:     {combined}")

    # Averages
    if wf_results["single_model"]:
        avg_single = np.mean([f["r2"] for f in wf_results["single_model"]])
        print(f"\n  Average single model R2: {avg_single:.6f}")
    for regime in REGIME_GROUPS:
        folds = wf_results["per_regime"][regime]
        if folds:
            avg = np.mean([f["r2"] for f in folds])
            print(f"  Average {regime} R2: {avg:.6f}")

    # Step 3: Train final models + extract weights
    print("\n  Training final models on all data...")
    weights = train_final_models(features, target, regime_labels)

    for regime_name, w_df in weights.items():
        print(f"\n  {'='*50}")
        print(f"  SIGNAL WEIGHTS: {regime_name}")
        print(f"  {'='*50}")
        for _, row in w_df.head(8).iterrows():
            bar = "+" * int(abs(row["normalized_weight"]) * 80) if row["normalized_weight"] > 0 else "-" * int(abs(row["normalized_weight"]) * 80)
            print(f"    {row['feature']:<25} {row['normalized_weight']:+.4f}  {bar}")

    # Step 4: MetaStrategy recommendations
    print("\n  Generating MetaStrategy recommendations...")
    recommendations = generate_meta_recommendations(wf_results, weights)

    print(f"\n  {'='*70}")
    print(f"  METASTRATEGY MODULE WEIGHTS (recommended)")
    print(f"  {'='*70}")
    for module, info in recommendations["module_weights"].items():
        print(f"    {module:<25} {info['weight']:.2f}  ({info['justification']})")

    print(f"\n  REGIME-SPECIFIC WEIGHTS DECISION:")
    decision = recommendations["regime_weights_decision"]
    print(f"    Single model avg R2:    {decision['single_model_avg_r2']}")
    print(f"    Per-regime avg R2:      {decision['per_regime_avg_r2']}")
    print(f"    Recommendation:         {'USE REGIME-SPECIFIC' if decision['use_regime_specific'] else 'USE SINGLE MODEL'}")
    print(f"    Reasoning:              {decision['reasoning']}")

    if recommendations.get("regime_top_features"):
        print(f"\n  TOP FEATURES PER REGIME:")
        for regime, top_features in recommendations["regime_top_features"].items():
            print(f"    {regime}:")
            for f in top_features:
                print(f"      {f['direction']}{f['feature']:<23} w={f['normalized_weight']:+.4f}")

    print("\n  Models saved:")
    for f in MODEL_DIR.glob("signal_weights_*.joblib"):
        print(f"    {f.name}")

    print("\n  Done!")
