"""
Signal Optimizer & Momentum Ranking
====================================
#2: Data-driven signal weight optimization using Ridge regression
    - Builds historical signal features (RSI, SMA, volatility, momentum)
    - Regresses against 10-day forward returns
    - Produces optimal signal weights

#4: Sector momentum ranking
    - Calculates 3-month risk-adjusted momentum for each sector/region ETF
    - Ranks and assigns scores based on relative performance
"""
import logging
import json
import os
import time
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "data", "signal_weights.json")
MOMENTUM_CACHE = {"data": None, "timestamp": 0, "ttl": 600}  # 10 min cache


# ===== #2: Signal Weight Optimization =====

def _compute_signals(close_series) -> dict:
    """Compute technical signals from a price series."""
    close = np.array(close_series, dtype=float)
    n = len(close)
    if n < 50:
        return {}

    # RSI (14-period)
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gains, np.ones(14)/14, mode='valid')
    avg_loss = np.convolve(losses, np.ones(14)/14, mode='valid')
    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi = 100 - 100 / (1 + rs)

    # SMA crossover (20/50)
    sma20 = np.convolve(close, np.ones(20)/20, mode='valid')
    sma50 = np.convolve(close, np.ones(50)/50, mode='valid')
    min_len = min(len(sma20), len(sma50))
    sma_signal = (sma20[-min_len:] - sma50[-min_len:]) / sma50[-min_len:] * 100

    # Volatility (20-day rolling std of returns)
    returns = np.diff(close) / close[:-1]
    if len(returns) >= 20:
        vol = np.array([np.std(returns[max(0,i-20):i]) * np.sqrt(252) * 100
                        for i in range(20, len(returns))])
    else:
        vol = np.array([])

    # Momentum (20-day returns)
    if n >= 20:
        mom20 = (close[20:] - close[:-20]) / close[:-20] * 100
    else:
        mom20 = np.array([])

    # Rate of change (10-day)
    if n >= 10:
        roc10 = (close[10:] - close[:-10]) / close[:-10] * 100
    else:
        roc10 = np.array([])

    return {
        "rsi": rsi,
        "sma_cross": sma_signal,
        "volatility": vol,
        "momentum_20d": mom20,
        "roc_10d": roc10,
    }


def optimize_signal_weights(tickers: dict = None) -> dict:
    """Learn optimal signal weights from historical data using Ridge regression.

    For each asset, compute technical signals and regress against
    10-day forward returns. The resulting coefficients tell us which
    signals actually predict future returns.

    Returns:
        dict with signal names → optimized weights, plus model stats
    """
    import yfinance as yf
    import pandas as pd

    if tickers is None:
        from portfolio_optimizer import ASSET_TICKER_MAP
        # Use core macro assets for training (most liquid, most data)
        core_tickers = {k: v for k, v in ASSET_TICKER_MAP.items()
                        if not k.startswith("sector-") and not k.startswith("region-")}
        tickers = core_tickers

    logger.info("📊 Optimizing signal weights via Ridge regression...")

    # Get 2 years of data for training
    ticker_list = list(tickers.values())
    data = yf.download(ticker_list, period="2y", progress=False)
    if data is None or data.empty:
        raise ValueError("No data for signal optimization")

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
    else:
        close = data

    close = close.ffill().dropna(axis=1, thresh=int(len(close) * 0.5)).dropna()

    # Build feature matrix: for each asset, compute signals at each time step
    all_features = []
    all_targets = []
    signal_names = ["rsi", "sma_cross", "volatility", "momentum_20d", "roc_10d"]

    for col in close.columns:
        series = close[col].values
        signals = _compute_signals(series)
        if not signals:
            continue

        # Align all signals to same length
        min_len = min(len(v) for v in signals.values() if len(v) > 0)
        if min_len < 50:
            continue

        # 10-day forward returns as target
        returns = np.diff(series) / series[:-1]
        fwd_10d = np.array([
            np.sum(returns[i:i+10]) if i+10 <= len(returns) else 0
            for i in range(len(returns))
        ]) * 100  # Convert to percentage

        for t in range(50, min(min_len, len(fwd_10d) - 10)):
            feature_row = []
            for sig_name in signal_names:
                sig = signals[sig_name]
                if t < len(sig):
                    val = sig[t]
                    # Normalize RSI to [-1, 1] centered on 50
                    if sig_name == "rsi":
                        val = (val - 50) / 50
                    elif sig_name == "volatility":
                        val = val / 30 - 1  # Normalize around 30% vol
                    elif sig_name in ("momentum_20d", "roc_10d", "sma_cross"):
                        val = np.clip(val / 10, -2, 2)  # Clip extremes
                    feature_row.append(float(val))
                else:
                    feature_row.append(0.0)

            if len(feature_row) == len(signal_names):
                all_features.append(feature_row)
                all_targets.append(fwd_10d[t])

    if len(all_features) < 100:
        logger.warning("  ⚠️ Too few samples for optimization, using equal weights")
        return _default_weights()

    X = np.array(all_features)
    y = np.array(all_targets)

    # Ridge regression (L2 regularization prevents overfitting)
    alpha = 10.0  # Strong regularization
    n_features = X.shape[1]
    XtX = X.T @ X + alpha * np.eye(n_features)
    Xty = X.T @ y
    try:
        coefficients = np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        logger.warning("  ⚠️ Ridge regression failed, using equal weights")
        return _default_weights()

    # Normalize coefficients to sum to 1 (absolute values)
    abs_sum = np.sum(np.abs(coefficients))
    if abs_sum > 0:
        normalized = coefficients / abs_sum
    else:
        normalized = np.ones(n_features) / n_features

    # Calculate R² for quality assessment
    y_pred = X @ coefficients
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    weights = {}
    for i, name in enumerate(signal_names):
        weights[name] = {
            "weight": round(float(normalized[i]), 4),
            "raw_coefficient": round(float(coefficients[i]), 4),
            "direction": "positive" if coefficients[i] > 0 else "negative",
        }

    result = {
        "weights": weights,
        "r_squared": round(float(r_squared), 4),
        "n_samples": len(all_features),
        "n_assets": len(close.columns),
        "regularization_alpha": alpha,
        "confidence": "high" if r_squared > 0.05 else "medium" if r_squared > 0.01 else "low",
        "trained_at": datetime.now().isoformat(),
    }

    # Save to disk
    os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"  ✅ Signal weights optimized: R²={r_squared:.4f}, {len(all_features)} samples")
    for name, w in weights.items():
        logger.info(f"    {name}: {w['weight']:+.4f} ({w['direction']})")

    return result


def get_signal_weights() -> dict:
    """Get cached signal weights, or train if not available."""
    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE, "r") as f:
                data = json.load(f)
            # Retrain if older than 7 days
            trained = data.get("trained_at", "")
            if trained:
                age = (datetime.now() - datetime.fromisoformat(trained)).days
                if age < 7:
                    return data
        except Exception:
            pass

    return optimize_signal_weights()


def _default_weights() -> dict:
    """Equal weights fallback."""
    signal_names = ["rsi", "sma_cross", "volatility", "momentum_20d", "roc_10d"]
    return {
        "weights": {name: {"weight": 0.2, "raw_coefficient": 1.0, "direction": "positive"}
                    for name in signal_names},
        "r_squared": 0,
        "n_samples": 0,
        "confidence": "low",
        "trained_at": None,
    }


# ===== #4: Sector & Region Momentum Ranking =====

def compute_momentum_scores() -> dict:
    """Compute 3-month risk-adjusted momentum for sector and region ETFs.

    Uses Sharpe-like ratio: momentum / volatility
    Ranks all ETFs and assigns scores from -5 to +5.

    Returns:
        dict with asset_id → {score, momentum_3m, volatility, rank, total}
    """
    import yfinance as yf
    import pandas as pd

    # Check cache
    now = time.time()
    if MOMENTUM_CACHE["data"] and now - MOMENTUM_CACHE["timestamp"] < MOMENTUM_CACHE["ttl"]:
        return MOMENTUM_CACHE["data"]

    logger.info("📈 Computing sector/region momentum rankings...")

    from portfolio_optimizer import ASSET_TICKER_MAP, ASSET_NAMES

    # Get sector + region tickers
    etf_tickers = {k: v for k, v in ASSET_TICKER_MAP.items()
                   if k.startswith("sector-") or k.startswith("region-")}

    ticker_list = list(etf_tickers.values())
    data = yf.download(ticker_list, period="6mo", progress=False)
    if data is None or data.empty:
        return {}

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
    else:
        close = data

    close = close.ffill().dropna()

    # Compute 3-month (63 trading days) momentum and volatility
    scores = {}
    reverse_map = {v: k for k, v in etf_tickers.items()}

    for col in close.columns:
        series = close[col].values
        ticker_str = str(col).strip()
        asset_id = reverse_map.get(ticker_str)
        if not asset_id:
            continue

        if len(series) < 63:
            continue

        # 3-month return
        mom_3m = (series[-1] / series[-63] - 1) * 100

        # Annualized volatility (last 63 days)
        returns = np.diff(series[-63:]) / series[-63:-1]
        vol = float(np.std(returns) * np.sqrt(252) * 100)

        # Risk-adjusted momentum (Sharpe-like)
        risk_adj_mom = mom_3m / max(vol, 1)

        scores[asset_id] = {
            "momentum_3m": round(float(mom_3m), 2),
            "volatility": round(vol, 2),
            "risk_adj_momentum": round(float(risk_adj_mom), 3),
            "name": ASSET_NAMES.get(asset_id, asset_id),
        }

    if not scores:
        return {}

    # Rank by risk-adjusted momentum
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x]["risk_adj_momentum"], reverse=True)
    n = len(sorted_ids)

    for rank, asset_id in enumerate(sorted_ids):
        # Map rank to score: top → +5, bottom → -5
        # Linear interpolation from rank 0 (best) to rank n-1 (worst)
        if n > 1:
            normalized = (rank / (n - 1))  # 0 = best, 1 = worst
        else:
            normalized = 0.5
        score = round(5 - normalized * 10, 1)  # +5 to -5
        score = max(-5, min(5, score))

        scores[asset_id]["score"] = score
        scores[asset_id]["rank"] = rank + 1
        scores[asset_id]["total"] = n

    # Cache result
    MOMENTUM_CACHE["data"] = scores
    MOMENTUM_CACHE["timestamp"] = now

    logger.info(f"  ✅ Momentum ranking complete ({n} ETFs):")
    for asset_id in sorted_ids:
        s = scores[asset_id]
        logger.info(f"    #{s['rank']}: {s['name']:25s} mom={s['momentum_3m']:+.1f}%, vol={s['volatility']:.1f}%, score={s['score']:+.1f}")

    return scores
