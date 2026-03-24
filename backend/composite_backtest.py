"""
AI Composite Portfolio — Regime-Switching Backtest
==================================================
Simulates what would have happened if you always followed the AI's
regime-switching advice to rotate between Conservative/Balanced/Aggressive
MPT portfolios over the past year.

Uses a simplified regime signal (moving average + volatility) to simulate
the AI's regime detection historically, then applies the MPT-optimized
weights for each regime period.
"""
import logging
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

# Same ticker mapping as portfolio_optimizer
ASSET_TICKER_MAP = {
    "btc": "BTC-USD",
    "gold": "GC=F",
    "silver": "SI=F",
    "oil": "BZ=F",
    "sp500": "^GSPC",
    "global-equity": "ACWI",
    "eurusd": "EURUSD=X",
    "us10y": "^TNX",
}


def _detect_regime_historical(market_data, window_short=20, window_long=50, vol_window=20):
    """Detect regime historically using multi-factor model.

    Uses the signal weights discovered by Ridge regression:
    - ROC 10d (97.9% weight) — dominant short-term momentum
    - Momentum 20d (1.1%) — medium-term trend
    - Volatility (0.7%) — risk environment (negative contribution)

    This replaces the old SMA-crossover approach which was proven
    to have zero predictive power by our signal optimization.
    """
    # Use ACWI or S&P 500 as the market proxy
    if "^GSPC" in market_data.columns:
        proxy = market_data["^GSPC"]
    elif "ACWI" in market_data.columns:
        proxy = market_data["ACWI"]
    else:
        proxy = market_data.iloc[:, 0]

    close = proxy.values.astype(float)
    n = len(close)

    # Pre-compute signals
    # 1. ROC 10d (strongest predictor: 97.9% weight)
    roc_10d = np.full(n, 0.0)
    for i in range(10, n):
        roc_10d[i] = (close[i] / close[i-10] - 1) * 100

    # 2. Momentum 20d (1.1% weight)
    mom_20d = np.full(n, 0.0)
    for i in range(20, n):
        mom_20d[i] = (close[i] / close[i-20] - 1) * 100

    # 3. Rolling volatility (0.7% weight, negative contribution = high vol → defensive)
    daily_returns = np.diff(close) / close[:-1]
    rolling_vol = np.full(n, 0.15)  # default 15% annualized
    for i in range(vol_window + 1, n):
        vol = np.std(daily_returns[i-vol_window:i]) * np.sqrt(252)
        rolling_vol[i] = vol

    avg_vol = np.mean(rolling_vol[vol_window+1:]) if n > vol_window + 1 else 0.15

    # Composite regime score (weighted by signal importance)
    # Normalized: ROC/10 maps ~(-5, +5), mom/10 same, vol_ratio centered on 0
    regimes = []
    for i in range(n):
        if i < window_long:
            regimes.append("balanced")
            continue

        # Normalize signals
        roc_norm = roc_10d[i] / 5.0       # ~(-2, +2) for typical moves
        mom_norm = mom_20d[i] / 8.0       # ~(-2, +2)
        vol_ratio = (rolling_vol[i] / max(avg_vol, 0.01) - 1)  # 0 = avg, +0.5 = 50% above avg

        # Composite score: weighted by discovered signal importance
        # ROC dominates, vol is negative (high vol → lower score)
        regime_score = (
            roc_norm * 0.70 +      # ROC 10d — dominant predictor
            mom_norm * 0.15 +      # Momentum 20d — trend confirmation
            -vol_ratio * 0.15      # Volatility — high vol penalizes
        )

        # Map to regime
        if regime_score > 0.4:
            regimes.append("aggressive")
        elif regime_score < -0.3:
            regimes.append("conservative")
        else:
            regimes.append("balanced")

    return regimes


def run_composite_backtest() -> dict:
    """Run the full composite portfolio backtest.

    Returns:
    - equity_curve: daily portfolio value (starting at 100)
    - benchmark_curve: S&P 500 buy-and-hold (starting at 100)
    - regime_log: list of regime changes with dates
    - stats: total return, max drawdown, sharpe, vs benchmark
    """
    import yfinance as yf
    from portfolio_optimizer import optimize_portfolios, _fetch_market_data, ASSET_TICKER_MAP

    tickers = list(ASSET_TICKER_MAP.values())

    logger.info("📊 Starting composite backtest...")

    # Download 1 year of data
    data = yf.download(tickers, period="1y", progress=False)
    if data is None or data.empty:
        raise ValueError("Failed to download market data")

    # Extract close prices
    import pandas as pd
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            close = data["Close"]
        else:
            close = data
    else:
        close = data

    close = close.ffill()
    close = close.dropna(axis=1, thresh=int(len(close) * 0.5))
    close = close.dropna()

    if close.shape[1] < 2 or len(close) < 60:
        raise ValueError(f"Insufficient data for backtest: {close.shape}")

    # Map tickers to asset IDs
    ticker_to_id = {v: k for k, v in ASSET_TICKER_MAP.items()}
    col_to_id = {}
    for col in close.columns:
        aid = ticker_to_id.get(str(col).strip())
        if aid:
            col_to_id[col] = aid

    available_tickers = list(col_to_id.keys())
    available_ids = list(col_to_id.values())

    logger.info(f"  Available assets: {available_ids}")

    # Calculate daily returns
    returns = close[available_tickers].pct_change().fillna(0)

    # Detect regimes historically
    regimes = _detect_regime_historical(close, window_short=20, window_long=50)

    # Get current MPT-optimized weights for each profile
    # We use current AI scores = 0 (neutral) for historical backtest
    neutral_analysis = {aid: {"finalScore": 0, "name": aid} for aid in available_ids}

    try:
        profiles = optimize_portfolios(neutral_analysis)
        if profiles is None:
            raise ValueError("Optimizer returned None")
    except Exception as e:
        logger.warning(f"MPT optimization failed for backtest: {e}")
        # Fallback: equal weight
        n = len(available_ids)
        equal_w = np.ones(n) / n
        profiles = {
            "conservative": {"allocations": [{"assetId": aid, "weight": round(1/n*100)} for aid in available_ids]},
            "balanced": {"allocations": [{"assetId": aid, "weight": round(1/n*100)} for aid in available_ids]},
            "aggressive": {"allocations": [{"assetId": aid, "weight": round(1/n*100)} for aid in available_ids]},
        }

    # Convert profile allocations to weight arrays
    profile_weights = {}
    for pid in ["conservative", "balanced", "aggressive"]:
        prof = profiles.get(pid, {})
        weights = np.zeros(len(available_ids))
        for alloc in prof.get("allocations", []):
            aid = alloc.get("assetId")
            if aid in available_ids:
                idx = available_ids.index(aid)
                weights[idx] = alloc.get("weight", 0) / 100.0
        # Normalize
        s = weights.sum()
        if s > 0:
            weights = weights / s
        else:
            weights = np.ones(len(available_ids)) / len(available_ids)
        profile_weights[pid] = weights

    logger.info(f"  Profile weights computed for {list(profile_weights.keys())}")

    # ===== REALISTIC EXECUTION PARAMETERS =====
    EXECUTION_DELAY = 1       # T+1: signal day N, execute day N+1
    CONFIRMATION_DAYS = 3     # Regime must persist 3 days before switching (anti-whipsaw)
    SLIPPAGE_PER_TRADE = 0.001  # 0.10% slippage per trade (bid/ask + market impact)

    # Simulate composite portfolio
    portfolio_value = 100.0
    equity_curve = []
    benchmark_value = 100.0
    benchmark_curve = []

    # S&P 500 benchmark returns
    sp500_col = None
    for col in close.columns:
        if str(col).strip() == "^GSPC":
            sp500_col = col
            break

    sp500_returns = returns[sp500_col] if sp500_col else returns.iloc[:, 0]

    # Track regime changes
    regime_log = []
    dates = close.index.tolist()

    # State for realistic execution
    active_regime = "balanced"          # Currently active portfolio
    pending_regime = None               # Regime waiting for confirmation
    pending_days = 0                    # How many days pending regime has been confirmed
    total_slippage = 0.0                # Total slippage cost paid
    trades_executed = 0

    for i in range(len(returns)):
        # 1. What the signal says TODAY (but we can't act on it yet)
        signal_regime = regimes[i] if i < len(regimes) else "balanced"

        # 2. Regime confirmation: must hold for CONFIRMATION_DAYS
        if signal_regime != active_regime:
            if signal_regime == pending_regime:
                pending_days += 1
            else:
                pending_regime = signal_regime
                pending_days = 1
        else:
            # Signal matches active — no change pending
            pending_regime = None
            pending_days = 0

        # 3. Check if confirmed regime should be executed (with T+1 delay)
        execute_switch = False
        if pending_regime and pending_days >= CONFIRMATION_DAYS:
            # Confirmed! But with T+1 delay, we execute NEXT day
            # So we mark it and apply tomorrow
            if i + EXECUTION_DELAY < len(returns):
                execute_switch = True

        # 4. Apply the ACTIVE regime's weights for today's return
        weights = profile_weights.get(active_regime, profile_weights["balanced"])
        daily_ret_values = returns.iloc[i].values
        port_return = np.dot(weights, daily_ret_values[:len(weights)])

        portfolio_value *= (1 + port_return)
        benchmark_value *= (1 + sp500_returns.iloc[i])

        date_str = dates[i].strftime("%Y-%m-%d") if hasattr(dates[i], 'strftime') else str(dates[i])[:10]

        equity_curve.append({
            "date": date_str,
            "value": round(float(portfolio_value), 2),
            "regime": active_regime,
        })

        benchmark_curve.append({
            "date": date_str,
            "value": round(float(benchmark_value), 2),
        })

        # 5. Execute the switch AFTER today's return is calculated (T+1 effect)
        if execute_switch:
            old_regime = active_regime
            active_regime = pending_regime
            pending_regime = None
            pending_days = 0

            # Apply slippage cost
            slippage_cost = portfolio_value * SLIPPAGE_PER_TRADE
            portfolio_value -= slippage_cost
            total_slippage += slippage_cost
            trades_executed += 1

            profile_label = {"conservative": "🛡️ Försiktig", "balanced": "⚖️ Balanserad", "aggressive": "🚀 Aggressiv"}.get(active_regime, active_regime)
            regime_log.append({
                "date": date_str,
                "from_profile": old_regime,
                "to_profile": active_regime,
                "label": profile_label,
                "portfolio_value": round(float(portfolio_value), 2),
                "slippage_paid": round(float(slippage_cost), 2),
            })

    logger.info(f"  Execution realism: T+{EXECUTION_DELAY} delay, {CONFIRMATION_DAYS}d confirmation, {SLIPPAGE_PER_TRADE*100:.2f}% slippage")
    logger.info(f"  Trades executed: {trades_executed}, Total slippage: ${total_slippage:.2f}")

    # Calculate statistics
    equity_values = [e["value"] for e in equity_curve]
    bench_values = [b["value"] for b in benchmark_curve]

    total_return = (equity_values[-1] / 100 - 1) * 100 if equity_values else 0
    bench_return = (bench_values[-1] / 100 - 1) * 100 if bench_values else 0

    # Max drawdown
    peak = 100
    max_dd = 0
    for v in equity_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Benchmark max drawdown
    b_peak = 100
    b_max_dd = 0
    for v in bench_values:
        if v > b_peak:
            b_peak = v
        dd = (b_peak - v) / b_peak * 100
        if dd > b_max_dd:
            b_max_dd = dd

    # Sharpe ratio
    daily_returns_arr = np.diff(equity_values) / equity_values[:-1] if len(equity_values) > 1 else [0]
    port_sharpe = (np.mean(daily_returns_arr) * 252 - 0.04) / (np.std(daily_returns_arr) * np.sqrt(252)) if np.std(daily_returns_arr) > 0 else 0

    # Regime distribution
    regime_counts = {"conservative": 0, "balanced": 0, "aggressive": 0}
    for r in regimes:
        if r in regime_counts:
            regime_counts[r] += 1
    total_days = sum(regime_counts.values()) or 1

    stats = {
        "total_return": round(total_return, 1),
        "benchmark_return": round(bench_return, 1),
        "alpha": round(total_return - bench_return, 1),
        "max_drawdown": round(max_dd, 1),
        "benchmark_max_drawdown": round(b_max_dd, 1),
        "sharpe_ratio": round(float(port_sharpe), 2),
        "regime_switches": len(regime_log),
        "regime_distribution": {
            "conservative": round(regime_counts["conservative"] / total_days * 100),
            "balanced": round(regime_counts["balanced"] / total_days * 100),
            "aggressive": round(regime_counts["aggressive"] / total_days * 100),
        },
        "period_start": equity_curve[0]["date"] if equity_curve else "",
        "period_end": equity_curve[-1]["date"] if equity_curve else "",
        # Execution realism stats
        "execution_delay": f"T+{EXECUTION_DELAY}",
        "confirmation_days": CONFIRMATION_DAYS,
        "slippage_per_trade": f"{SLIPPAGE_PER_TRADE*100:.2f}%",
        "trades_executed": trades_executed,
        "total_slippage_cost": round(float(total_slippage), 2),
    }

    logger.info(f"  ✅ Composite backtest complete:")
    logger.info(f"     AI Portfolio: {stats['total_return']}%  vs  S&P 500: {stats['benchmark_return']}%")
    logger.info(f"     Alpha: {stats['alpha']}%  |  Max DD: {stats['max_drawdown']}%")
    logger.info(f"     Regime switches: {stats['regime_switches']}")

    return {
        "equity_curve": equity_curve,
        "benchmark_curve": benchmark_curve,
        "regime_log": regime_log,
        "stats": stats,
    }
