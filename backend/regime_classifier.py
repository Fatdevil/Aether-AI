# ============================================================
# backend/regime_classifier.py
# ML-baserad regimklassificerare
#
# Del A: Manuella regimmärkningar (2005-2026)
# Del B: Feature engineering (15 features)
# Del C: Random Forest-träning
# Del D: Walk-forward-validering (5 folds)
# Del E: Integration med befintlig regelbaserad regime_detector
# ============================================================

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("aether.regime_classifier")

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "regime_classifier.joblib"


# ============================================================
# DEL A: KÄNDA REGIMPERIODER (manuell märkning)
# ============================================================

# Historiskt kända regimskiften. Allt som inte matchar = NEUTRAL.
# Konservativ märkning — hellre NEUTRAL än fel.

KNOWN_REGIMES = {
    # ---- 2005-2007: Pre-GFC bull market ----
    ("2005-01-01", "2007-06-30"): "RISK_ON",
    ("2007-07-01", "2007-10-31"): "NEUTRAL",       # Subprime-oro börjar
    ("2007-11-01", "2008-09-14"): "RISK_OFF",       # Bear Stearns, tilltagande kris

    # ---- 2008-2009: Global finanskris ----
    ("2008-09-15", "2009-03-09"): "CRISIS",         # Lehman → botten
    ("2009-03-10", "2009-12-31"): "RISK_ON",        # Recovery-rally

    # ---- 2010-2011 ----
    ("2010-01-01", "2010-04-22"): "RISK_ON",        # Post-GFC expansion
    ("2010-04-23", "2010-07-02"): "RISK_OFF",       # Flash crash / Euro-kris 1
    ("2010-07-03", "2011-04-29"): "RISK_ON",        # QE2-rally
    ("2011-05-01", "2011-07-31"): "NEUTRAL",        # Topp-oro
    ("2011-08-01", "2011-10-15"): "RISK_OFF",       # Europeisk skuldkris, US downgrade

    # ---- 2012-2014: QE-driven bull ----
    ("2011-10-16", "2012-05-01"): "RISK_ON",        # ECB LTRO-rally
    ("2012-05-02", "2012-06-04"): "RISK_OFF",       # Spanien / Grekland II
    ("2012-06-05", "2014-09-30"): "RISK_ON",        # Draghi "whatever it takes" + QE3

    # ---- 2014-2015 ----
    ("2014-10-01", "2014-10-15"): "RISK_OFF",       # Ebola + Fed taper
    ("2014-10-16", "2015-05-31"): "RISK_ON",        # Recovery
    ("2015-06-01", "2015-08-17"): "NEUTRAL",        # Grekland III
    ("2015-08-18", "2015-09-30"): "RISK_OFF",       # Kina-devalvering
    ("2015-10-01", "2015-12-31"): "RISK_ON",        # Återhämtning

    # ---- 2016 ----
    ("2016-01-01", "2016-02-11"): "RISK_OFF",       # Kina-oro + oljefall
    ("2016-02-12", "2016-06-23"): "RISK_ON",        # Recovery
    ("2016-06-24", "2016-07-08"): "RISK_OFF",       # Brexit-chock
    ("2016-07-09", "2016-12-31"): "RISK_ON",        # Trump-rally

    # ---- 2017: Low-vol bull ----
    ("2017-01-01", "2017-12-31"): "RISK_ON",        # Synkroniserad global tillväxt

    # ---- 2018: Volatilitets-comeback ----
    ("2018-01-01", "2018-01-26"): "RISK_ON",        # Melt-up
    ("2018-01-27", "2018-04-02"): "RISK_OFF",       # Volmageddon
    ("2018-04-03", "2018-09-30"): "RISK_ON",        # Återhämtning
    ("2018-10-01", "2018-12-24"): "RISK_OFF",       # Fed-åtstramning, handelskrig

    # ---- 2019 ----
    ("2018-12-25", "2019-04-30"): "RISK_ON",        # Powell-pivot
    ("2019-05-01", "2019-06-03"): "RISK_OFF",       # Trade war eskalering
    ("2019-06-04", "2019-07-31"): "RISK_ON",        # Fed rate cut expectations
    ("2019-08-01", "2019-10-02"): "RISK_OFF",       # Inverterad yield curve panic
    ("2019-10-03", "2020-02-19"): "RISK_ON",        # Phase 1 deal + repo calm

    # ---- 2020: COVID ----
    ("2020-02-20", "2020-03-23"): "CRISIS",         # COVID-krasch (-34% S&P 500)
    ("2020-03-24", "2020-08-31"): "RISK_ON",        # Monster-rally, Fed unlimited QE
    ("2020-09-01", "2020-10-30"): "NEUTRAL",        # Valoro + second wave
    ("2020-11-01", "2021-02-12"): "RISK_ON",        # Vaccin-rally, Biden
    ("2021-02-13", "2021-03-08"): "RISK_OFF",       # Ränteoro, tech-rotation
    ("2021-03-09", "2021-11-19"): "RISK_ON",        # Meme stocks, crypto-bull

    # ---- 2022: Inflation & Räntechock ----
    ("2021-11-20", "2021-12-31"): "RISK_OFF",       # Omikron-oro, Fed hawkish
    ("2022-01-03", "2022-06-16"): "RISK_OFF",       # Inflation + räntechock, bear market
    ("2022-06-17", "2022-08-15"): "RISK_ON",        # Sommar-rally
    ("2022-08-16", "2022-10-12"): "RISK_OFF",       # Jackson Hole, GBP-kris
    ("2022-10-13", "2023-02-01"): "RISK_ON",        # Botten + pivot-hopp

    # ---- 2023 ----
    ("2023-02-02", "2023-03-12"): "NEUTRAL",        # Stark arbetsmarknad, oklart
    ("2023-03-13", "2023-03-27"): "CRISIS",         # SVB + bankkollapser
    ("2023-03-28", "2023-07-31"): "RISK_ON",        # AI-rally (Nvidia, ChatGPT)
    ("2023-08-01", "2023-10-27"): "RISK_OFF",       # Ränteoro höst 2023, 10Y → 5%
    ("2023-10-28", "2024-03-31"): "RISK_ON",        # AI-rally + soft landing narrative

    # ---- 2024 ----
    ("2024-04-01", "2024-04-19"): "RISK_OFF",       # Iran-Israel eskalering
    ("2024-04-20", "2024-07-15"): "RISK_ON",        # AI-rally fortsätter, Nvidia
    ("2024-07-16", "2024-08-05"): "RISK_OFF",       # Yen carry unwind, vol-spike
    ("2024-08-06", "2024-12-31"): "RISK_ON",        # Fed cut, Trump-trade

    # ---- 2025-2026 ----
    ("2025-01-01", "2025-02-18"): "RISK_ON",        # Post-inauguration rally
    ("2025-02-19", "2025-04-07"): "RISK_OFF",       # Tariff-kris
    ("2025-04-08", "2025-07-31"): "NEUTRAL",        # Avmattning, osäkerhet
    ("2025-08-01", "2025-12-31"): "NEUTRAL",        # Sidleds
    ("2026-01-01", "2026-02-27"): "NEUTRAL",        # Avvaktande
    ("2026-02-28", "2026-03-28"): "RISK_OFF",       # Iran-kriget
}

REGIME_MAP = {"RISK_ON": 0, "NEUTRAL": 1, "RISK_OFF": 2, "CRISIS": 3}
REGIME_NAMES = {v: k for k, v in REGIME_MAP.items()}


def label_dates(dates: pd.DatetimeIndex) -> pd.Series:
    """Tilldela regimklass till varje datum baserat på KNOWN_REGIMES."""
    labels = pd.Series("NEUTRAL", index=dates)

    for (start, end), regime in KNOWN_REGIMES.items():
        mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        labels[mask] = regime

    return labels


# ============================================================
# DEL B: FEATURE ENGINEERING (15 base + 16 enrichment features)
# ============================================================

FEATURE_NAMES = [
    "sp500_roc_10d",
    "sp500_roc_20d",
    "sp500_momentum_50d",
    "sp500_vol_20d",
    "vix_level",
    "vix_change_5d",
    "us10y_level",
    "us10y_change_20d",
    "gold_roc_10d",
    "gold_vs_sp500_20d",
    "oil_roc_10d",
    "dxy_roc_10d",
    "hyg_roc_10d",
    "copper_roc_10d",
    "em_vs_sp500_20d",
]

# Fas 7: 16 enrichment features (from DataEnrichmentLoader)
ENRICHMENT_FEATURE_NAMES = [
    "credit_spread_level",
    "credit_spread_change_10d",
    "breakeven_inflation_proxy",
    "commodity_index_roc_20d",
    "liquidity_proxy_roc_20d",
    "copper_roc_20d",
    "gold_positioning_percentile",
    "equity_positioning_percentile",
    "breadth_ratio_change_20d",
    "breadth_divergence",
    "vix_term_structure",
    "vix_in_backwardation",
    "vix_fear_ratio",
    "avg_cross_correlation_20d",
    "correlation_regime_break",
    "mom_12m1m_spy",
]

# Defaults for when enrichment features are missing
ENRICHMENT_DEFAULTS = {
    "credit_spread_level": 0,
    "credit_spread_change_10d": 0,
    "breakeven_inflation_proxy": 0,
    "commodity_index_roc_20d": 0,
    "liquidity_proxy_roc_20d": 0,
    "copper_roc_20d": 0,
    "gold_positioning_percentile": 50,
    "equity_positioning_percentile": 50,
    "breadth_ratio_change_20d": 0,
    "breadth_divergence": 0,
    "vix_term_structure": 0,
    "vix_in_backwardation": 0,
    "vix_fear_ratio": 1.0,
    "avg_cross_correlation_20d": 0.25,
    "correlation_regime_break": 0,
    "mom_12m1m_spy": 0,
}


def compute_regime_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Beräkna 15 features för regimklassificering.
    
    Kräver kolumnerna: SP500, VIX, US10Y_Yield, Gold, WTI_Oil,
                       Dollar_Index, HY_Credit, Copper, EM_EEM
    """

    features = pd.DataFrame(index=prices.index)

    # Helper: Rate of Change
    def roc(col, periods):
        return col.pct_change(periods=periods)

    sp = prices.get("SP500")
    vix = prices.get("VIX")
    us10y = prices.get("US10Y_Yield")
    gold = prices.get("Gold")
    oil = prices.get("WTI_Oil")
    dxy = prices.get("Dollar_Index")
    hyg = prices.get("HY_Credit")
    copper = prices.get("Copper")
    em = prices.get("EM_EEM")

    # 1-4: S&P 500 features
    if sp is not None:
        features["sp500_roc_10d"] = roc(sp, 10)
        features["sp500_roc_20d"] = roc(sp, 20)
        sma50 = sp.rolling(50).mean()
        features["sp500_momentum_50d"] = (sp / sma50) - 1
        features["sp500_vol_20d"] = sp.pct_change().rolling(20).std() * np.sqrt(252)

    # 5-6: VIX features
    if vix is not None:
        features["vix_level"] = vix
        features["vix_change_5d"] = vix.diff(5)

    # 7-8: US 10Y Yield
    if us10y is not None:
        features["us10y_level"] = us10y
        features["us10y_change_20d"] = us10y.diff(20)

    # 9-10: Gold
    if gold is not None:
        features["gold_roc_10d"] = roc(gold, 10)
        if sp is not None:
            gold_ret_20d = roc(gold, 20)
            sp_ret_20d = roc(sp, 20)
            features["gold_vs_sp500_20d"] = gold_ret_20d - sp_ret_20d

    # 11: Oil
    if oil is not None:
        features["oil_roc_10d"] = roc(oil, 10)

    # 12: DXY
    if dxy is not None:
        features["dxy_roc_10d"] = roc(dxy, 10)

    # 13: HYG (kredit-proxy)
    if hyg is not None:
        features["hyg_roc_10d"] = roc(hyg, 10)

    # 14: Copper (konjunktur-proxy)
    if copper is not None:
        features["copper_roc_10d"] = roc(copper, 10)

    # 15: EM vs S&P 500
    if em is not None and sp is not None:
        em_ret_20d = roc(em, 20)
        sp_ret_20d_2 = roc(sp, 20)
        features["em_vs_sp500_20d"] = em_ret_20d - sp_ret_20d_2

    return features


REQUIRED_ASSETS = ["SP500", "VIX", "US10Y_Yield", "Gold", "WTI_Oil",
                    "Dollar_Index", "HY_Credit", "Copper", "EM_EEM"]


def build_training_data(prices: pd.DataFrame = None) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Bygg komplett träningsdata: features + labels.
    
    Steg:
    1. Ladda alla priser
    2. Filtrera till de 9 tillgångar som behövs för features
    3. Forward-fill för att hantera icke-exakta handelsdagar
    4. Beräkna features + labels
    5. Droppa rader med NaN (bara initial warm-up-period, ~50 dagar)
    
    Returns:
        (X, y) — features DataFrame och labels Series
    """
    if prices is None:
        from historical_data_loader import load_all
        prices = load_all()

    # Filtrera till bara de 9 kolumner som features behöver
    available = [c for c in REQUIRED_ASSETS if c in prices.columns]
    if len(available) < 7:
        raise ValueError(f"Need at least 7 of 9 required assets. Found: {available}")

    prices_filtered = prices[available].copy()

    # Forward-fill: om en marknad är stängd (t.ex. helgdag i en zon), 
    # behåll senaste kända pris. Limit=5 för att inte fylla extremt långa gap.
    prices_filtered = prices_filtered.ffill(limit=5)

    # Droppa rader där ALLA är NaN (före tidigaste tillgång)
    prices_filtered = prices_filtered.dropna(how="all")

    features = compute_regime_features(prices_filtered)
    labels = label_dates(features.index)

    # Numeriska labels
    y = labels.map(REGIME_MAP)

    # Droppa rader med NaN i features (bara de första ~50 warm-up-dagarna)
    valid_mask = features.notna().all(axis=1) & y.notna()
    X = features[valid_mask]
    y = y[valid_mask].astype(int)

    logger.info(f"  Training data: {len(X)} samples, {len(X.columns)} features")
    logger.info(f"  Date range: {X.index[0].strftime('%Y-%m-%d')} → {X.index[-1].strftime('%Y-%m-%d')}")
    logger.info(f"  Class distribution: {dict(y.value_counts().sort_index())}")

    return X, y


# ============================================================
# DEL C: RANDOM FOREST-TRÄNING
# ============================================================

def train_model(X: pd.DataFrame, y: pd.Series, save: bool = True):
    """
    Träna RandomForestClassifier och (valfritt) spara till disk.
    
    Hyperparametrar valda för att förhindra overfitting:
    - max_depth=8: begränsar träddjup
    - min_samples_leaf=20: kräver minst 20 samples per löv
    - n_estimators=200: tillräckligt för stabil prediktion
    """
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",  # Hantera obalanserade klasser (CRISIS sällan)
    )

    model.fit(X, y)

    if save:
        import joblib
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        logger.info(f"  💾 Model saved to {MODEL_PATH}")

    return model


def load_model():
    """Ladda tränad modell från disk."""
    import joblib
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No trained model at {MODEL_PATH}. Run train_model() first.")
    return joblib.load(MODEL_PATH)


# ============================================================
# DEL D: WALK-FORWARD-VALIDERING
# ============================================================

WALK_FORWARD_FOLDS = [
    {"train_end": "2015-01-01", "test_start": "2015-01-01", "test_end": "2017-01-01"},
    {"train_end": "2017-01-01", "test_start": "2017-01-01", "test_end": "2019-01-01"},
    {"train_end": "2019-01-01", "test_start": "2019-01-01", "test_end": "2021-01-01"},
    {"train_end": "2021-01-01", "test_start": "2021-01-01", "test_end": "2023-01-01"},
    {"train_end": "2023-01-01", "test_start": "2023-01-01", "test_end": "2025-01-01"},
]


def walk_forward_validation(X: pd.DataFrame, y: pd.Series) -> Dict:
    """
    Walk-forward cross-validation.
    Tränar på all data FÖRE testperioden, testar på NÄSTA period.
    Beräknar accuracy, confusion matrix, classification report per fold.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

    results = []
    all_y_true = []
    all_y_pred = []

    for i, fold in enumerate(WALK_FORWARD_FOLDS):
        train_mask = X.index < pd.Timestamp(fold["train_end"])
        test_mask = (X.index >= pd.Timestamp(fold["test_start"])) & (X.index < pd.Timestamp(fold["test_end"]))

        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        if len(X_train) < 100 or len(X_test) < 50:
            print(f"  Fold {i+1}: Skipped (train={len(X_train)}, test={len(X_test)})")
            continue

        model = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=20,
            random_state=42, n_jobs=-1, class_weight="balanced",
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2, 3])
        report = classification_report(
            y_test, y_pred, labels=[0, 1, 2, 3],
            target_names=["RISK_ON", "NEUTRAL", "RISK_OFF", "CRISIS"],
            output_dict=True, zero_division=0,
        )

        all_y_true.extend(y_test.tolist())
        all_y_pred.extend(y_pred.tolist())

        fold_result = {
            "fold": i + 1,
            "train_period": f"2005 → {fold['train_end']}",
            "test_period": f"{fold['test_start']} → {fold['test_end']}",
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "accuracy": round(acc, 4),
            "confusion_matrix": cm.tolist(),
            "classification_report": report,
        }
        results.append(fold_result)

        print(f"\n  {'='*60}")
        print(f"  FOLD {i+1}: Train 2005→{fold['train_end']} | Test {fold['test_start']}→{fold['test_end']}")
        print(f"  {'='*60}")
        print(f"  Train: {len(X_train)} | Test: {len(X_test)}")
        print(f"  Accuracy: {acc:.1%}")
        print(f"  Confusion Matrix (rows=true, cols=pred):")
        print(f"            RISK_ON  NEUTRAL  RISK_OFF  CRISIS")
        for row_idx, row_name in enumerate(["RISK_ON", "NEUTRAL", "RISK_OFF", "CRISIS"]):
            row_vals = "  ".join(f"{v:>7}" for v in cm[row_idx])
            print(f"  {row_name:<10} {row_vals}")

    # Overall metrics
    if all_y_true:
        overall_acc = accuracy_score(all_y_true, all_y_pred)
        overall_cm = confusion_matrix(all_y_true, all_y_pred, labels=[0, 1, 2, 3])
        overall_report = classification_report(
            all_y_true, all_y_pred, labels=[0, 1, 2, 3],
            target_names=["RISK_ON", "NEUTRAL", "RISK_OFF", "CRISIS"],
            output_dict=True, zero_division=0,
        )
    else:
        overall_acc = 0
        overall_cm = [[0]*4]*4
        overall_report = {}

    print(f"\n  {'='*60}")
    print(f"  OVERALL OUT-OF-SAMPLE ACCURACY: {overall_acc:.1%}")
    print(f"  {'='*60}")

    if overall_acc < 0.55:
        print(f"  ⚠️ OOS accuracy ({overall_acc:.1%}) < 55% — modellen behöver justeras!")
    else:
        print(f"  ✅ OOS accuracy ({overall_acc:.1%}) >= 55% — modellen är godkänd")

    return {
        "folds": results,
        "overall_accuracy": round(overall_acc, 4),
        "overall_confusion_matrix": overall_cm.tolist() if hasattr(overall_cm, 'tolist') else overall_cm,
        "overall_report": overall_report,
        "passed": overall_acc >= 0.55,
    }


def get_feature_importance(model=None, feature_names=None) -> pd.DataFrame:
    """Returnera feature importance sorterat fallande."""
    if model is None:
        model = load_model()
    if feature_names is None:
        feature_names = FEATURE_NAMES

    importances = model.feature_importances_
    df = pd.DataFrame({
        "feature": feature_names[:len(importances)],
        "importance": importances,
    }).sort_values("importance", ascending=False)

    return df


# ============================================================
# DEL E-FAS7: ENRICHED FEATURES + SEKUNDÄR REGIM
# ============================================================

def build_enriched_features(base_features: Dict, enrichment: Dict) -> Dict:
    """
    Lägg till enrichment-features till befintliga 15 base features.
    Returnerar dict med 31 features (15 base + 16 enrichment).
    """
    enriched = dict(base_features)  # Copy base 15 features

    for fname in ENRICHMENT_FEATURE_NAMES:
        enriched[fname] = enrichment.get(fname, ENRICHMENT_DEFAULTS.get(fname, 0))

    return enriched


# ============================================================
# SEKUNDÄR REGIM: Konjunktur × Inflation (Fas 7)
# ============================================================

SECONDARY_REGIMES = {
    # (tillväxt_signal, inflation_signal) -> sekundär regim
    (1, -1):  "EXPANSION_DISINFLATION",     # Bästa miljön: aktier + obligationer
    (1, 0):   "EXPANSION_STABLE",            # Bra: aktier
    (1, 1):   "EXPANSION_RISING_INFLATION",  # OK: råvaror, energi, TIPS
    (0, -1):  "SLOWDOWN_DISINFLATION",       # Varning: obligationer, guld, defensivt
    (0, 0):   "SLOWDOWN_STABLE",             # Neutral: balanserat
    (0, 1):   "STAGFLATION_RISK",            # FARLIGT: guld, råvaror, kassa
    (-1, -1): "CONTRACTION_DISINFLATION",    # Kris: kassa, guld, kort ränta
    (-1, 0):  "CONTRACTION_STABLE",          # Kris: defensivt
    (-1, 1):  "STAGFLATION",                 # VÄRST: bara guld och kassa
}

REGIME_IMPLICATIONS = {
    "EXPANSION_DISINFLATION": {
        "description": "Bästa miljön. Aktier + obligationer stiger.",
        "favor": ["sp500", "xlk", "tlt"],
        "avoid": ["gold", "oil"],
        "core_adjustment": {"equity": 1.2, "gold": 0.7, "bonds": 1.1},
    },
    "EXPANSION_STABLE": {
        "description": "Bra tillväxt, stabil inflation. Aktier gynnas.",
        "favor": ["sp500", "xlk", "eem"],
        "avoid": [],
        "core_adjustment": {"equity": 1.1, "gold": 0.9, "bonds": 1.0},
    },
    "EXPANSION_RISING_INFLATION": {
        "description": "Tillväxt + inflation. Råvaror och energi.",
        "favor": ["oil", "xle", "gold", "silver"],
        "avoid": ["tlt", "xlk"],
        "core_adjustment": {"equity": 0.9, "gold": 1.3, "bonds": 0.7},
    },
    "SLOWDOWN_DISINFLATION": {
        "description": "Avmattning med fallande inflation. Obligationer och guld.",
        "favor": ["tlt", "gold", "xlv"],
        "avoid": ["xle", "eem"],
        "core_adjustment": {"equity": 0.8, "gold": 1.2, "bonds": 1.3},
    },
    "SLOWDOWN_STABLE": {
        "description": "Avmattning, stabil inflation. Neutral miljö.",
        "favor": ["tlt", "xlv"],
        "avoid": ["xle"],
        "core_adjustment": {"equity": 0.9, "gold": 1.1, "bonds": 1.1},
    },
    "STAGFLATION_RISK": {
        "description": "FARLIGT. Svag tillväxt + stigande inflation. Bara guld och kassa.",
        "favor": ["gold", "kassa"],
        "avoid": ["sp500", "tlt", "xlk", "eem"],
        "core_adjustment": {"equity": 0.5, "gold": 1.5, "bonds": 0.6},
    },
    "STAGFLATION": {
        "description": "VÄRST. Kontraktion + inflation. Maximera kassa.",
        "favor": ["gold", "kassa"],
        "avoid": ["sp500", "tlt", "xlk", "xle", "eem"],
        "core_adjustment": {"equity": 0.3, "gold": 1.5, "bonds": 0.4},
    },
    "CONTRACTION_DISINFLATION": {
        "description": "Kris med deflationsrisk. Kassa, guld, kort ränta.",
        "favor": ["gold", "kassa", "tlt"],
        "avoid": ["sp500", "xle", "eem", "btc"],
        "core_adjustment": {"equity": 0.4, "gold": 1.4, "bonds": 1.2},
    },
    "CONTRACTION_STABLE": {
        "description": "Kontraktion med stabil inflation. Defensivt.",
        "favor": ["gold", "kassa", "xlv"],
        "avoid": ["sp500", "xle", "eem"],
        "core_adjustment": {"equity": 0.5, "gold": 1.3, "bonds": 1.0},
    },
}


def detect_secondary_regime(enrichment: Dict) -> Dict:
    """
    Bestäm sekundär regim baserat på tillväxt + inflation-signaler.

    Tillväxt-signal: koppar + bredd + momentum
    Inflation-signal: breakeven + commodities

    Returns dict with:
      secondary_regime, growth_signal, inflation_signal,
      description, favor, avoid, core_adjustment
    """
    # Tillväxt-signal: koppar + bredd + momentum
    copper = enrichment.get("copper_roc_20d", 0)
    breadth = enrichment.get("breadth_ratio_change_20d", 0)
    mom = enrichment.get("mom_12m1m_spy", 0)

    growth_score = 0
    if copper > 3: growth_score += 1
    if copper < -3: growth_score -= 1
    if breadth > 1: growth_score += 1
    if breadth < -1: growth_score -= 1
    if mom > 5: growth_score += 1
    if mom < -5: growth_score -= 1

    growth_signal = 1 if growth_score >= 2 else -1 if growth_score <= -2 else 0

    # Inflation-signal: breakeven + commodities
    breakeven = enrichment.get("breakeven_inflation_proxy", 0)
    commodities = enrichment.get("commodity_index_roc_20d", 0)

    inflation_score = 0
    if breakeven > 2: inflation_score += 1
    if breakeven < -2: inflation_score -= 1
    if commodities > 5: inflation_score += 1
    if commodities < -5: inflation_score -= 1

    inflation_signal = 1 if inflation_score >= 1 else -1 if inflation_score <= -1 else 0

    # Matcha till sekundär regim
    secondary = SECONDARY_REGIMES.get((growth_signal, inflation_signal), "SLOWDOWN_STABLE")

    implications = REGIME_IMPLICATIONS.get(secondary, {
        "description": "Neutral miljö.",
        "favor": [],
        "avoid": [],
        "core_adjustment": {"equity": 1.0, "gold": 1.0, "bonds": 1.0},
    })

    logger.info(f"  🌡 Secondary regime: {secondary} (growth={growth_signal}, inflation={inflation_signal})")

    return {
        "secondary_regime": secondary,
        "growth_signal": growth_signal,
        "inflation_signal": inflation_signal,
        "growth_score": growth_score,
        "inflation_score": inflation_score,
        "description": implications["description"],
        "favor": implications.get("favor", []),
        "avoid": implications.get("avoid", []),
        "core_adjustment": implications.get("core_adjustment", {}),
    }


# ============================================================
# DEL F: INTEGRATION MED BEFINTLIG REGIMDETEKTERING
# ============================================================

def detect_regime_ml(features_dict: Dict) -> Dict:
    """
    Prediktera regim med tränad ML-modell.
    
    Args:
        features_dict: Dict med samma nycklar som FEATURE_NAMES.
                       Kan komma från live-data eller historisk data.
    
    Returns:
        {"regime": "risk-on", "confidence": 0.72, "probabilities": {...}, "method": "ml"}
    """
    try:
        model = load_model()
    except FileNotFoundError:
        logger.warning("No trained model found. Falling back to rule-based.")
        return None

    # Bygg feature-vektor i rätt ordning
    feature_values = []
    for name in FEATURE_NAMES:
        val = features_dict.get(name)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            logger.warning(f"Missing feature: {name}. Falling back to rule-based.")
            return None
        feature_values.append(float(val))

    X = np.array([feature_values])

    # Prediktera
    prediction = model.predict(X)[0]
    probabilities = model.predict_proba(X)[0]

    regime_name = REGIME_NAMES.get(prediction, "NEUTRAL").lower().replace("_", "-")

    # Bygg probability dict
    prob_dict = {}
    for i, class_label in enumerate(model.classes_):
        rname = REGIME_NAMES.get(class_label, f"CLASS_{class_label}")
        prob_dict[rname] = round(float(probabilities[i]), 3)

    confidence = float(max(probabilities))

    return {
        "regime": regime_name,
        "confidence": round(confidence, 3),
        "probabilities": prob_dict,
        "method": "ml",
        "predicted_class": int(prediction),
    }


def compute_live_features() -> Optional[Dict]:
    """
    Beräkna features från LIVE yfinance-data (samma 15 features som träning).
    Returnerar dict med feature-namn → värde.
    """
    try:
        import yfinance as yf

        # Hämta 60 dagars data (behöver 50d SMA)
        tickers = {
            "^GSPC": "SP500",
            "^VIX": "VIX",
            "^TNX": "US10Y_Yield",
            "GC=F": "Gold",
            "CL=F": "WTI_Oil",
            "DX-Y.NYB": "Dollar_Index",
            "HYG": "HY_Credit",
            "HG=F": "Copper",
            "EEM": "EM_EEM",
        }

        data_frames = {}
        for ticker, name in tickers.items():
            try:
                df = yf.download(ticker, period="90d", progress=False, auto_adjust=True)
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    data_frames[name] = df["Close"]
            except Exception as e:
                logger.warning(f"Failed to fetch {name}: {e}")

        if len(data_frames) < 5:
            logger.warning(f"Only got {len(data_frames)}/9 tickers. Insufficient for ML regime.")
            return None

        prices = pd.DataFrame(data_frames)

        # Compute features
        features_df = compute_regime_features(prices)
        if features_df.empty:
            return None

        # Take latest row
        latest = features_df.iloc[-1]
        result = {}
        for name in FEATURE_NAMES:
            val = latest.get(name)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                result[name] = float(val)
            else:
                result[name] = None

        # Check completeness
        missing = [k for k, v in result.items() if v is None]
        if missing:
            logger.warning(f"Missing live features: {missing}")
            return None

        return result

    except Exception as e:
        logger.error(f"compute_live_features failed: {e}")
        return None


def detect_regime_with_fallback(enrichment_features: Dict = None) -> Dict:
    """
    Primär: ML-modell (med optional enrichment features)
    Fallback: Regelbaserad regime_detector

    Args:
        enrichment_features: Optional dict from DataEnrichmentLoader.get_features().
                             If provided, enriched features are logged alongside
                             base ML prediction for future model upgrade.

    Returnerar alltid ett giltigt resultat.
    """
    # Försök ML först
    try:
        live_features = compute_live_features()
        if live_features:
            ml_result = detect_regime_ml(live_features)
            if ml_result and ml_result.get("confidence", 0) > 0.4:
                logger.info(f"  🤖 ML regime: {ml_result['regime']} (conf: {ml_result['confidence']:.0%})")

                # Fas 7: Log enrichment features alongside ML prediction
                # (Not used in prediction yet — requires retraining with backfilled data)
                if enrichment_features:
                    enriched = build_enriched_features(live_features, enrichment_features)
                    ml_result["enrichment_available"] = True
                    ml_result["enrichment_feature_count"] = len(enrichment_features)
                    logger.info(f"  🔬 Enrichment: {len(enrichment_features)} features attached (31 total)")
                else:
                    ml_result["enrichment_available"] = False

                return ml_result
            elif ml_result:
                logger.info(f"  🤖 ML regime low confidence ({ml_result['confidence']:.0%}), using fallback")
    except Exception as e:
        logger.warning(f"ML regime detection failed: {e}")

    # Fallback: regelbaserad
    try:
        from regime_detector import regime_detector
        rule_result = regime_detector.detect_regime()
        rule_result["method"] = "rule-based"
        rule_result["enrichment_available"] = enrichment_features is not None
        logger.info(f"  📏 Rule-based regime: {rule_result.get('regime', '?')}")
        return rule_result
    except Exception as e:
        logger.error(f"Both ML and rule-based failed: {e}")
        return {
            "regime": "neutral",
            "confidence": 0.1,
            "method": "default-fallback",
            "enrichment_available": False,
            "error": str(e),
        }


# ============================================================
# CLI: TRAIN + VALIDATE
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n" + "=" * 60)
    print("  AETHER AI — REGIME CLASSIFIER TRAINING")
    print("=" * 60)

    # Step 1: Build training data
    print("\n📊 Building training data...")
    X, y = build_training_data()
    print(f"  Samples: {len(X)} | Features: {len(X.columns)}")
    print(f"  Class distribution:")
    for cls_id, cls_name in sorted(REGIME_NAMES.items()):
        count = (y == cls_id).sum()
        pct = count / len(y) * 100
        print(f"    {cls_name}: {count} ({pct:.1f}%)")

    # Step 2: Walk-forward validation
    print("\n🔄 Walk-forward validation (5 folds)...")
    wf_results = walk_forward_validation(X, y)

    # Step 3: Feature importance
    print("\n📈 Training full model on all data...")
    model = train_model(X, y, save=True)
    fi = get_feature_importance(model, list(X.columns))
    print("\n  Top 5 feature importance:")
    for _, row in fi.head(5).iterrows():
        bar = "█" * int(row["importance"] * 50)
        print(f"    {row['feature']:<25} {row['importance']:.3f}  {bar}")

    # Step 4: Compare with rule-based on test period (2023-2025)
    print("\n🔍 Comparing ML vs rule-based on 2023-2025...")
    test_mask = (X.index >= "2023-01-01") & (X.index < "2025-01-01")
    if test_mask.sum() > 0:
        X_test = X[test_mask]
        y_test = y[test_mask]
        y_pred = model.predict(X_test)

        from sklearn.metrics import accuracy_score
        acc = accuracy_score(y_test, y_pred)
        print(f"  ML accuracy (2023-2025): {acc:.1%}")

    print("\n✅ Training complete!")
    print(f"  Model saved to: {MODEL_PATH}")
    print(f"  Overall OOS accuracy: {wf_results['overall_accuracy']:.1%}")
    print(f"  Status: {'✅ PASS' if wf_results['passed'] else '⚠️ NEEDS IMPROVEMENT'}")
