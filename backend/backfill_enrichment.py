"""
============================================================
Fas 7 — Backfill Enrichment Features (20 år)
============================================================
Hämtar historisk data för alla enrichment-tickers,
beräknar 16 enrichment-features bakåt i tiden,
mergar med befintliga 15 base features → 31-feature dataset,
tränar om Random Forest och kör walk-forward-validering.

Körs EN gång. Tar ~10-15 minuter. Noll löpande kostnad.

Användning:
    python backfill_enrichment.py
============================================================
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

DATA_DIR = Path(__file__).parent / "data" / "historical"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# STEG 1: Hämta alla tickers (bas + enrichment)
# ============================================================

# Enrichment-specifika tickers (utöver det historical_data_loader redan har)
ENRICHMENT_TICKERS = {
    # Makro
    "TIP":       ("TIPS_ETF",       "2005-01-01"),   # Inflation-skyddade obligationer
    "IEF":       ("IEF_Treasury",   "2005-01-01"),   # 7-10Y Treasury
    "DJP":       ("CRB_Commodity",  "2007-01-01"),   # Commodity index proxy
    "LQD":       ("IG_Credit",      "2005-01-01"),   # Investment grade credit
    "TLT":       ("TLT_LongBond",   "2005-01-01"),   # Long-term treasury (liquidity proxy)

    # Bredd
    "RSP":       ("SP500_EqualWeight", "2005-01-01"),  # Equal-weight S&P 500

    # Options
    "^VIX3M":    ("VIX3M",          "2008-01-01"),   # 3-month VIX (term structure)

    # Momentum (de vi redan har i historical_data_loader + extras)
    "SPY":       ("SPY",            "2005-01-01"),

    # COT proxy
    "GLD":       ("GLD_ETF",        "2005-01-01"),   # Gold ETF (for volume flow proxy)
}

# Tickers vi redan har i historical_data_loader
EXISTING_TICKERS = {
    "^GSPC": "SP500", "^VIX": "VIX", "^TNX": "US10Y_Yield",
    "GC=F": "Gold", "CL=F": "WTI_Oil", "DX-Y.NYB": "Dollar_Index",
    "HYG": "HY_Credit", "HG=F": "Copper", "EEM": "EM_EEM",
    "XLK": "Tech_XLK", "XLE": "Energy_XLE", "EWJ": "Japan_EWJ", "VGK": "Europe_VGK",
}


def download_enrichment_data(force: bool = False) -> dict:
    """Hämta historisk data för enrichment-tickers."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance krävs. Kör: pip install yfinance")

    results = {}
    end_date = datetime.now().strftime("%Y-%m-%d")

    for ticker, (name, start_date) in ENRICHMENT_TICKERS.items():
        csv_path = DATA_DIR / f"{name}.csv"

        if csv_path.exists() and not force:
            logger.info(f"  ⏭ {name} finns redan, laddar från disk")
            try:
                results[name] = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            except Exception:
                pass
            continue

        logger.info(f"  📥 Hämtar {name} ({ticker}) {start_date} → {end_date}...")
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
            if data.empty:
                logger.warning(f"  ⚠️ {name}: Tom data!")
                continue

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            if "Close" in data.columns:
                close = data[["Close"]].copy()
                close.columns = [name]
            else:
                close = data.iloc[:, :1].copy()
                close.columns = [name]

            close.to_csv(csv_path)
            results[name] = close
            logger.info(f"  ✅ {name}: {len(close)} dagar ({close.index[0].strftime('%Y-%m-%d')} → {close.index[-1].strftime('%Y-%m-%d')})")

        except Exception as e:
            logger.error(f"  ❌ {name} ({ticker}): {e}")

    return results


def load_all_data() -> pd.DataFrame:
    """Ladda ALLA CSV:er (bas + enrichment) och sammanfoga."""
    frames = {}
    for csv_file in sorted(DATA_DIR.glob("*.csv")):
        name = csv_file.stem
        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            if not df.empty:
                if len(df.columns) >= 1:
                    df = df.iloc[:, :1]
                    df.columns = [name]
                frames[name] = df
        except Exception as e:
            logger.error(f"  ❌ {csv_file.name}: {e}")

    combined = pd.concat(frames.values(), axis=1, join="outer")
    combined.index = pd.to_datetime(combined.index)
    combined.sort_index(inplace=True)

    for col in combined.columns:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    # Forward-fill (max 5 dagar) för helgdagar etc
    combined = combined.ffill(limit=5)

    logger.info(f"  📊 Totalt: {len(combined.columns)} tillgångar, {len(combined)} handelsdagar")
    return combined


# ============================================================
# STEG 2: Beräkna enrichment features historiskt
# ============================================================

def compute_historical_enrichment(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Beräkna alla 16 enrichment features för varje dag i historien.
    Returnerar DataFrame med samma index som prices.
    """
    features = pd.DataFrame(index=prices.index)

    def safe_roc(series, periods):
        return series.pct_change(periods=periods) * 100

    # --- Makro ---

    # 1. credit_spread_level: HYG/LQD ratio
    hyg = prices.get("HY_Credit")
    lqd = prices.get("IG_Credit")
    if hyg is not None and lqd is not None:
        features["credit_spread_level"] = hyg / lqd
        features["credit_spread_change_10d"] = features["credit_spread_level"].pct_change(10) * 100

    # 2. breakeven_inflation_proxy: IEF/TIP ratio change
    ief = prices.get("IEF_Treasury")
    tip = prices.get("TIPS_ETF")
    if ief is not None and tip is not None:
        ratio = ief / tip
        features["breakeven_inflation_proxy"] = ratio.pct_change(20) * 100

    # 3. commodity_index_roc_20d
    crb = prices.get("CRB_Commodity")
    if crb is not None:
        features["commodity_index_roc_20d"] = safe_roc(crb, 20)

    # 4. liquidity_proxy_roc_20d
    tlt = prices.get("TLT_LongBond")
    if tlt is not None:
        features["liquidity_proxy_roc_20d"] = safe_roc(tlt, 20)

    # 5. copper_roc_20d (vi har redan copper_roc_10d i base, detta är 20d)
    copper = prices.get("Copper")
    if copper is not None:
        features["copper_roc_20d"] = safe_roc(copper, 20)

    # --- COT (percentil-baserat, behöver volume — använder pris-proxy) ---
    # gold_positioning_percentile: 60d percentil av daglig förändring
    gld = prices.get("GLD_ETF")
    if gld is not None:
        gld_change = gld.pct_change()
        features["gold_positioning_percentile"] = gld_change.rolling(60).apply(
            lambda x: (x.iloc[-1] > x).mean() * 100 if len(x) > 0 else 50, raw=False
        )

    # equity_positioning_percentile
    spy = prices.get("SPY")
    if spy is not None:
        spy_change = spy.pct_change()
        features["equity_positioning_percentile"] = spy_change.rolling(60).apply(
            lambda x: (x.iloc[-1] > x).mean() * 100 if len(x) > 0 else 50, raw=False
        )

    # --- Bredd ---
    rsp = prices.get("SP500_EqualWeight")
    sp500_for_breadth = prices.get("SPY")
    if rsp is not None and sp500_for_breadth is not None:
        ratio = rsp / sp500_for_breadth
        features["breadth_ratio_change_20d"] = ratio.pct_change(20) * 100

        # breadth_divergence: SPY stiger men ratio faller
        spy_up = sp500_for_breadth.diff(20) > 0
        ratio_down = ratio.diff(20) < 0
        features["breadth_divergence"] = (spy_up & ratio_down).astype(int)

    # --- Options ---
    vix = prices.get("VIX")
    vix3m = prices.get("VIX3M")
    if vix is not None and vix3m is not None:
        features["vix_term_structure"] = vix3m - vix
        features["vix_in_backwardation"] = (vix > vix3m).astype(int)

    if vix is not None:
        vix_sma20 = vix.rolling(20).mean()
        features["vix_fear_ratio"] = vix / vix_sma20

    # --- Korrelation (beräknas rullande, tungt) ---
    corr_assets = ["SPY", "GLD_ETF", "TLT_LongBond", "EM_EEM", "Energy_XLE", "Europe_VGK", "HY_Credit"]
    available_corr = [a for a in corr_assets if a in prices.columns]
    if len(available_corr) >= 4:
        returns = prices[available_corr].pct_change()
        # 20-dagars rullande genomsnittlig parvis korrelation
        avg_corr_list = []
        for i in range(len(returns)):
            if i < 60:
                avg_corr_list.append(np.nan)
                continue
            window = returns.iloc[i-20:i]
            corr_matrix = window.corr()
            n = len(corr_matrix.columns)
            vals = []
            for ci in range(n):
                for cj in range(ci+1, n):
                    v = corr_matrix.iloc[ci, cj]
                    if not np.isnan(v):
                        vals.append(abs(v))
            avg_corr_list.append(float(np.mean(vals)) if vals else np.nan)

        features["avg_cross_correlation_20d"] = avg_corr_list

        # correlation_regime_break: 20d korr vs 60d korr
        corr_series = pd.Series(avg_corr_list, index=prices.index)
        corr_60d = corr_series.rolling(60).mean()
        features["correlation_regime_break"] = ((corr_series > 0.50) & (corr_series > corr_60d + 0.10)).astype(float)

    # --- Momentum 12m-1m ---
    spy_for_mom = prices.get("SPY")
    if spy_for_mom is not None:
        # 12m-1m: (price_1m_ago / price_12m_ago - 1) * 100
        price_12m = spy_for_mom.shift(252)
        price_1m = spy_for_mom.shift(21)
        features["mom_12m1m_spy"] = (price_1m / price_12m - 1) * 100

    logger.info(f"  🔬 Enrichment features beräknade: {len(features.columns)} kolumner, {len(features)} rader")
    return features


# ============================================================
# STEG 3: Bygg 31-feature training data
# ============================================================

def build_enriched_training_data(prices: pd.DataFrame = None):
    """
    Bygg komplett 31-feature training data:
    15 base features + 16 enrichment features + labels.
    """
    from regime_classifier import (
        compute_regime_features, label_dates, REGIME_MAP,
        FEATURE_NAMES, ENRICHMENT_FEATURE_NAMES,
    )

    if prices is None:
        prices = load_all_data()

    # Base 15 features
    logger.info("  📊 Beräknar base features (15)...")
    base_features = compute_regime_features(prices)

    # Enrichment 16 features
    logger.info("  🔬 Beräknar enrichment features (16)...")
    enrichment_features = compute_historical_enrichment(prices)

    # Merge
    all_features = pd.concat([base_features, enrichment_features], axis=1)

    # Labels
    labels = label_dates(all_features.index)
    y = labels.map(REGIME_MAP)

    # Droppa NaN (warm-up period: 252 dagar för 12m momentum)
    valid_mask = all_features.notna().all(axis=1) & y.notna()
    X = all_features[valid_mask]
    y = y[valid_mask].astype(int)

    # Verifiera feature-antal
    expected_features = FEATURE_NAMES + ENRICHMENT_FEATURE_NAMES
    missing = [f for f in expected_features if f not in X.columns]
    extra = [f for f in X.columns if f not in expected_features]

    logger.info(f"\n  📊 ENRICHED TRAINING DATA:")
    logger.info(f"  Samples: {len(X)}")
    logger.info(f"  Features: {len(X.columns)} (mål: 31)")
    logger.info(f"  Feature-namn: {list(X.columns)}")
    logger.info(f"  Datum: {X.index[0].strftime('%Y-%m-%d')} → {X.index[-1].strftime('%Y-%m-%d')}")
    logger.info(f"  Klasser: {dict(y.value_counts().sort_index())}")
    if missing:
        logger.warning(f"  ⚠️ Saknade features: {missing}")
    if extra:
        logger.info(f"  ℹ️ Extra features (bonus): {extra}")

    return X, y


# ============================================================
# STEG 4: Träna + Walk-forward validering (31 features)
# ============================================================

def train_enriched_model(X, y, save=True):
    """Träna RF med 31 features och spara modell."""
    from sklearn.ensemble import RandomForestClassifier
    import joblib

    model = RandomForestClassifier(
        n_estimators=300,       # Fler träd för fler features
        max_depth=10,           # Något djupare (31 features)
        min_samples_leaf=15,    # Något lägre (mer data)
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )

    model.fit(X, y)

    if save:
        model_dir = Path(__file__).parent / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "regime_rf_v2_enriched.joblib"
        joblib.dump(model, model_path)
        logger.info(f"  💾 Modell sparad: {model_path}")

        # Spara feature importance
        importance = pd.DataFrame({
            "feature": list(X.columns),
            "importance": model.feature_importances_,
        }).sort_values("importance", ascending=False)
        logger.info(f"\n  📊 FEATURE IMPORTANCE (top 15):")
        for _, row in importance.head(15).iterrows():
            bar = "█" * int(row["importance"] * 100)
            logger.info(f"    {row['feature']:<35} {row['importance']:.4f} {bar}")

    return model


def walk_forward_enriched(X, y):
    """Walk-forward validering med 31 features."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

    FOLDS = [
        {"train_end": "2015-01-01", "test_start": "2015-01-01", "test_end": "2017-01-01"},
        {"train_end": "2017-01-01", "test_start": "2017-01-01", "test_end": "2019-01-01"},
        {"train_end": "2019-01-01", "test_start": "2019-01-01", "test_end": "2021-01-01"},
        {"train_end": "2021-01-01", "test_start": "2021-01-01", "test_end": "2023-01-01"},
        {"train_end": "2023-01-01", "test_start": "2023-01-01", "test_end": "2025-01-01"},
    ]

    all_y_true, all_y_pred = [], []
    regime_names = ["RISK_ON", "NEUTRAL", "RISK_OFF", "CRISIS"]

    for i, fold in enumerate(FOLDS):
        train_mask = X.index < pd.Timestamp(fold["train_end"])
        test_mask = (X.index >= pd.Timestamp(fold["test_start"])) & (X.index < pd.Timestamp(fold["test_end"]))

        X_train, y_train = X[train_mask], y[train_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        if len(X_train) < 100 or len(X_test) < 50:
            logger.info(f"  Fold {i+1}: Hoppas (train={len(X_train)}, test={len(X_test)})")
            continue

        model = RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=15,
            random_state=42, n_jobs=-1, class_weight="balanced",
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2, 3])

        all_y_true.extend(y_test.tolist())
        all_y_pred.extend(y_pred.tolist())

        print(f"\n  {'='*60}")
        print(f"  FOLD {i+1}: Train →{fold['train_end']} | Test {fold['test_start']}→{fold['test_end']}")
        print(f"  {'='*60}")
        print(f"  Train: {len(X_train)} | Test: {len(X_test)} | Accuracy: {acc:.1%}")
        print(f"  {'':>12} RISK_ON  NEUTRAL  RISK_OFF  CRISIS")
        for row_idx, name in enumerate(regime_names):
            row_vals = "  ".join(f"{v:>7}" for v in cm[row_idx])
            print(f"  {name:<10} {row_vals}")

    # Overall
    if all_y_true:
        overall_acc = accuracy_score(all_y_true, all_y_pred)
        print(f"\n  {'='*60}")
        print(f"  🎯 OVERALL OOS ACCURACY: {overall_acc:.1%}")
        print(f"  {'='*60}")

        if overall_acc >= 0.78:
            print(f"  ✅ MÅL UPPNÅTT! {overall_acc:.1%} >= 78%")
        elif overall_acc >= 0.72:
            print(f"  📈 Förbättring! {overall_acc:.1%} (före: 72%)")
        else:
            print(f"  ⚠️ Ingen förbättring ({overall_acc:.1%})")

        return overall_acc
    return 0.0


# ============================================================
# STEG 5: Jämför 15 vs 31 features
# ============================================================

def compare_models(prices):
    """Kör walk-forward med 15 features vs 31 features och jämför."""
    from regime_classifier import build_training_data, walk_forward_validation

    print("\n" + "=" * 70)
    print("  JÄMFÖRELSE: 15 features (nuvarande) vs 31 features (enriched)")
    print("=" * 70)

    # 15 features (nuvarande)
    print("\n" + "─" * 70)
    print("  📊 MODELL A: 15 BASE FEATURES (nuvarande)")
    print("─" * 70)
    X_base, y_base = build_training_data(prices)
    result_base = walk_forward_validation(X_base, y_base)
    acc_base = result_base["overall_accuracy"]

    # 31 features (enriched)
    print("\n" + "─" * 70)
    print("  🔬 MODELL B: 31 ENRICHED FEATURES (ny)")
    print("─" * 70)
    X_enr, y_enr = build_enriched_training_data(prices)
    acc_enr = walk_forward_enriched(X_enr, y_enr)

    # Resultat
    print("\n" + "=" * 70)
    print("  📊 SLUTRESULTAT")
    print("=" * 70)
    print(f"  Modell A (15 features): {acc_base:.1%}")
    print(f"  Modell B (31 features): {acc_enr:.1%}")
    delta = acc_enr - acc_base
    print(f"  Förändring:             {delta:+.1%}")
    if delta > 0:
        print(f"  🎉 Enrichment förbättrade accuracy med {delta:.1%}!")
    elif delta == 0:
        print(f"  ⚖️ Ingen skillnad — enrichment features behöver finjusteras")
    else:
        print(f"  ⚠️ Regression — enrichment features adderar brus")

    return {"base_accuracy": acc_base, "enriched_accuracy": acc_enr, "delta": delta}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n🚀 Fas 7 — Backfill Enrichment Pipeline")
    print("=" * 60)

    # Steg 1: Hämta data
    print("\n📥 STEG 1: Hämta historisk data (bas + enrichment)...")
    from historical_data_loader import download_all
    print("  Bas-tickers...")
    download_all(force=False)
    print("  Enrichment-tickers...")
    download_enrichment_data(force=False)

    # Steg 2: Ladda allt
    print("\n📊 STEG 2: Ladda all data...")
    prices = load_all_data()

    # Steg 3: Jämför modeller
    print("\n🔬 STEG 3: Jämför 15 vs 31 features...")
    result = compare_models(prices)

    # Steg 4: Träna slutlig modell (om förbättring)
    if result["delta"] >= 0:
        print("\n💾 STEG 4: Tränar slutlig enriched modell...")
        X_enr, y_enr = build_enriched_training_data(prices)
        model = train_enriched_model(X_enr, y_enr, save=True)
        print("\n✅ Backfill pipeline klar!")
    else:
        print("\n⚠️ Ingen förbättring — behåller nuvarande 15-feature modell")
        print("  Enrichment features används fortfarande som live-signaler")

    print("\n" + "=" * 60)
    print("  🏁 DONE")
    print("=" * 60)
