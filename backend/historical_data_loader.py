# ============================================================
# backend/historical_data_loader.py
# Laddar 20 års historisk marknadsdata via yfinance.
# Sparar som CSV till backend/data/historical/.
#
# Funktioner:
#   download_all()          — Laddar ner allt, sparar till disk
#   load_all()              — Laddar från disk till DataFrame
#   compute_returns()       — Daglig avkastning (pct_change)
#   compute_rolling_features() — ROC, momentum, vol, RSI
#   validate()              — Visar statistik + varningar
# ============================================================

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger("aether.historical_data")

# ============================================================
# KONFIGURATION
# ============================================================

DATA_DIR = Path(__file__).parent / "data" / "historical"

# Tillgångar att ladda ner: ticker → (namn, startår)
TICKERS = {
    "^GSPC":     ("SP500",               "2005-01-01"),
    "^VIX":      ("VIX",                 "2005-01-01"),
    "^TNX":      ("US10Y_Yield",         "2005-01-01"),
    "GC=F":      ("Gold",                "2005-01-01"),
    "SI=F":      ("Silver",              "2005-01-01"),
    "CL=F":      ("WTI_Oil",             "2005-01-01"),
    "DX-Y.NYB":  ("Dollar_Index",        "2005-01-01"),
    "HG=F":      ("Copper",              "2005-01-01"),
    "HYG":       ("HY_Credit",           "2007-01-01"),
    "^OMX":      ("OMXS30",              "2005-01-01"),
    "XLK":       ("Tech_XLK",            "2005-01-01"),
    "XLE":       ("Energy_XLE",          "2005-01-01"),
    "XLF":       ("Finance_XLF",         "2005-01-01"),
    "XLV":       ("Health_XLV",          "2005-01-01"),
    "ITA":       ("Defense_ITA",         "2005-01-01"),
    "EEM":       ("EM_EEM",              "2005-01-01"),
    "VGK":       ("Europe_VGK",          "2005-01-01"),
    "EWJ":       ("Japan_EWJ",           "2005-01-01"),
    "BTC-USD":   ("Bitcoin",             "2015-01-01"),
    "EURUSD=X":  ("EURUSD",              "2005-01-01"),
}


# ============================================================
# DOWNLOAD
# ============================================================

def download_all(force: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Ladda ner 20 års daglig data via yfinance.
    Sparar varje tillgång som CSV i DATA_DIR.
    
    Args:
        force: Om True, ladda ner även om filen redan finns.
    
    Returns:
        Dict med {namn: DataFrame}
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance is not installed. Run: pip install yfinance")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    end_date = datetime.now().strftime("%Y-%m-%d")

    for ticker, (name, start_date) in TICKERS.items():
        csv_path = DATA_DIR / f"{name}.csv"

        if csv_path.exists() and not force:
            logger.info(f"  ⏭ {name} already exists, skipping (use force=True to re-download)")
            try:
                results[name] = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            except Exception:
                pass
            continue

        logger.info(f"  📥 Downloading {name} ({ticker}) from {start_date} to {end_date}...")
        try:
            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )

            if data.empty:
                logger.warning(f"  ⚠️ {name}: No data returned!")
                continue

            # Flatten MultiIndex columns if present (yfinance sometimes returns multi-level)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Keep only Close price
            if "Close" in data.columns:
                close_series = data[["Close"]].copy()
                close_series.columns = [name]
            else:
                # Some tickers may have different column names
                close_series = data.iloc[:, :1].copy()
                close_series.columns = [name]

            close_series.to_csv(csv_path)
            results[name] = close_series
            logger.info(f"  ✅ {name}: {len(close_series)} days ({close_series.index[0].strftime('%Y-%m-%d')} → {close_series.index[-1].strftime('%Y-%m-%d')})")

        except Exception as e:
            logger.error(f"  ❌ {name} ({ticker}): {e}")

    logger.info(f"  📊 Download complete: {len(results)}/{len(TICKERS)} tickers")
    return results


# ============================================================
# LOAD
# ============================================================

def load_all() -> pd.DataFrame:
    """
    Ladda alla sparade CSV:er och sammanfoga till en DataFrame.
    
    Returns:
        DataFrame med datum-index, kolumner = tillgångar, values = daglig stängningskurs.
    """
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data directory not found: {DATA_DIR}. Run download_all() first.")

    frames = {}
    for csv_file in sorted(DATA_DIR.glob("*.csv")):
        name = csv_file.stem
        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            if df.empty:
                continue
            # Ensure single column with correct name
            if len(df.columns) == 1:
                df.columns = [name]
            else:
                df = df.iloc[:, :1]
                df.columns = [name]
            frames[name] = df
        except Exception as e:
            logger.error(f"Failed to load {csv_file.name}: {e}")

    if not frames:
        raise FileNotFoundError("No data files found in historical directory.")

    # Outer-join all frames on date index
    combined = pd.concat(frames.values(), axis=1, join="outer")
    combined.index = pd.to_datetime(combined.index)
    combined.sort_index(inplace=True)

    # Convert to float
    for col in combined.columns:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    logger.info(f"  📊 Loaded {len(combined.columns)} assets, {len(combined)} trading days "
                f"({combined.index[0].strftime('%Y-%m-%d')} → {combined.index[-1].strftime('%Y-%m-%d')})")
    return combined


# ============================================================
# COMPUTE RETURNS
# ============================================================

def compute_returns(prices: pd.DataFrame = None) -> pd.DataFrame:
    """
    Beräkna daglig avkastning via pct_change.
    
    Returns:
        DataFrame med daglig procentuell förändring per tillgång.
    """
    if prices is None:
        prices = load_all()

    returns = prices.pct_change().dropna(how="all")
    return returns


# ============================================================
# COMPUTE ROLLING FEATURES
# ============================================================

def compute_rolling_features(
    prices: pd.DataFrame = None,
    window: int = 20,
) -> pd.DataFrame:
    """
    Beräkna tekniska features per tillgång:
    - ROC (Rate of Change): price[t] / price[t-window] - 1
    - Momentum: price[t] - price[t-window]
    - Volatilitet: rolling std av daglig avkastning
    - RSI: Relative Strength Index (14-period)
    
    Returns:
        DataFrame med MultiIndex-kolumner: (tillgång, feature)
    """
    if prices is None:
        prices = load_all()

    returns = prices.pct_change()
    features = {}

    for col in prices.columns:
        price_col = prices[col].dropna()
        ret_col = returns[col].dropna()

        if len(price_col) < window * 2:
            logger.warning(f"  ⚠️ {col}: Only {len(price_col)} data points, skipping features")
            continue

        # ROC (Rate of Change)
        roc = price_col.pct_change(periods=window)

        # Momentum (absolute price change)
        momentum = price_col.diff(periods=window)

        # Volatility (rolling std of returns, annualized)
        volatility = ret_col.rolling(window=window).std() * np.sqrt(252)

        # RSI (14-period default)
        rsi = _compute_rsi(price_col, period=14)

        # Moving average ratio (price / SMA)
        sma = price_col.rolling(window=window).mean()
        ma_ratio = price_col / sma

        # Combine
        features[f"{col}_ROC"] = roc
        features[f"{col}_Momentum"] = momentum
        features[f"{col}_Volatility"] = volatility
        features[f"{col}_RSI"] = rsi
        features[f"{col}_MA_Ratio"] = ma_ratio

    result = pd.DataFrame(features)
    result.sort_index(inplace=True)
    return result


def _compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Beräkna RSI (Relative Strength Index)."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ============================================================
# VALIDATION
# ============================================================

def validate(prices: pd.DataFrame = None) -> Dict:
    """
    Validera data: rader per tillgång, saknade datapunkter, datum-intervall.
    Varnar om >5% saknade dagar.
    
    Returns:
        Dict med validerings-statistik.
    """
    if prices is None:
        prices = load_all()

    total_days = len(prices)
    stats = {}
    warnings = []

    for col in prices.columns:
        col_data = prices[col].dropna()
        missing = total_days - len(col_data)
        missing_pct = (missing / total_days * 100) if total_days > 0 else 0

        first_date = col_data.index[0].strftime("%Y-%m-%d") if len(col_data) > 0 else "N/A"
        last_date = col_data.index[-1].strftime("%Y-%m-%d") if len(col_data) > 0 else "N/A"

        stats[col] = {
            "rows": len(col_data),
            "missing": missing,
            "missing_pct": round(missing_pct, 1),
            "start": first_date,
            "end": last_date,
        }

        if missing_pct > 5:
            msg = f"⚠️ {col}: {missing_pct:.1f}% missing data ({missing}/{total_days} days)"
            warnings.append(msg)
            logger.warning(msg)

    summary = {
        "total_assets": len(prices.columns),
        "total_trading_days": total_days,
        "date_range": f"{prices.index[0].strftime('%Y-%m-%d')} → {prices.index[-1].strftime('%Y-%m-%d')}",
        "assets": stats,
        "warnings": warnings,
        "warnings_count": len(warnings),
    }

    # Print summary table
    print(f"\n{'='*80}")
    print(f"  HISTORICAL DATA VALIDATION")
    print(f"  {summary['total_assets']} assets | {summary['total_trading_days']} trading days | {summary['date_range']}")
    print(f"{'='*80}")
    print(f"  {'Asset':<20} {'Rows':>6} {'Missing':>8} {'Missing%':>9} {'Start':>12} {'End':>12}")
    print(f"  {'-'*20} {'-'*6} {'-'*8} {'-'*9} {'-'*12} {'-'*12}")
    for col, s in sorted(stats.items()):
        flag = " ⚠️" if s["missing_pct"] > 5 else ""
        print(f"  {col:<20} {s['rows']:>6} {s['missing']:>8} {s['missing_pct']:>8.1f}% {s['start']:>12} {s['end']:>12}{flag}")
    print(f"{'='*80}")
    if warnings:
        print(f"  ⚠️ {len(warnings)} warnings (>5% missing data)")
    else:
        print(f"  ✅ All assets have <5% missing data")
    print()

    return summary


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("\n🚀 Aether AI — Historical Data Loader")
    print("=" * 50)

    # Step 1: Download
    print("\n📥 Step 1: Downloading data...")
    data = download_all(force=False)

    # Step 2: Load and validate
    print("\n📊 Step 2: Loading and validating...")
    prices = load_all()
    validation = validate(prices)

    # Step 3: Compute returns
    print("\n📈 Step 3: Computing returns...")
    returns = compute_returns(prices)
    print(f"  Returns shape: {returns.shape}")

    # Step 4: Compute features
    print("\n🔧 Step 4: Computing rolling features (window=20)...")
    features = compute_rolling_features(prices, window=20)
    print(f"  Features shape: {features.shape}")
    print(f"  Feature columns: {list(features.columns[:10])}...")

    print("\n✅ Done!")
