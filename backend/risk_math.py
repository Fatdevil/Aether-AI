"""
Risk Mathematics Module - CVaR, Monte Carlo, Sharpe Ratio, Max Drawdown.
Inspired by NVIDIA Quantitative Portfolio Optimization Blueprint.
Uses numpy only (no GPU required).
"""

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger("aether.risk")


def calculate_cvar(returns: np.ndarray, confidence: float = 0.95) -> dict:
    """
    Calculate Historical CVaR (Conditional Value-at-Risk).
    
    CVaR answers: "In the worst X% of days, what is the AVERAGE loss?"
    More conservative than VaR because it accounts for tail risk.
    
    Args:
        returns: Array of daily returns (e.g., [-0.02, 0.01, -0.05, ...])
        confidence: 0.95 = 95% confidence level
    
    Returns:
        {"var_95": -2.1, "cvar_95": -3.4, "var_99": -4.2, "cvar_99": -5.8}
    """
    if len(returns) < 10:
        return {"var_95": 0, "cvar_95": 0, "var_99": 0, "cvar_99": 0}
    
    sorted_returns = np.sort(returns)
    
    # VaR: the threshold at which X% of returns are worse
    var_95_idx = int(len(sorted_returns) * (1 - 0.95))
    var_99_idx = int(len(sorted_returns) * (1 - 0.99))
    
    var_95 = float(sorted_returns[var_95_idx]) * 100  # as percentage
    var_99 = float(sorted_returns[max(var_99_idx, 0)]) * 100
    
    # CVaR: average of all returns worse than VaR
    cvar_95 = float(sorted_returns[:var_95_idx].mean()) * 100 if var_95_idx > 0 else var_95
    cvar_99 = float(sorted_returns[:max(var_99_idx, 1)].mean()) * 100 if var_99_idx > 0 else var_99
    
    return {
        "var_95": round(var_95, 2),
        "cvar_95": round(cvar_95, 2),
        "var_99": round(var_99, 2),
        "cvar_99": round(cvar_99, 2),
    }


def monte_carlo_simulation(
    returns: np.ndarray,
    days: int = 30,
    simulations: int = 10000,
    initial_value: float = 100.0,
) -> dict:
    """
    Monte Carlo simulation of portfolio value over N days.
    
    Generates random future scenarios based on historical return distribution.
    
    Returns:
        {
            "positive_prob": 0.73,        # P(gain) after N days
            "median_return_pct": 2.1,     # Median outcome
            "worst_5pct": -8.3,           # 5th percentile (bad case)
            "best_5pct": 14.2,            # 95th percentile (good case)
            "expected_return_pct": 1.8,   # Mean outcome
            "percentiles": [5, 25, 50, 75, 95] mapped to values
        }
    """
    if len(returns) < 10:
        return {
            "positive_prob": 0.5, "median_return_pct": 0,
            "worst_5pct": 0, "best_5pct": 0, "expected_return_pct": 0,
            "fan_chart": [],
        }
    
    mu = np.mean(returns)
    sigma = np.std(returns)
    
    # Generate random daily returns for each simulation
    random_returns = np.random.normal(mu, sigma, (simulations, days))
    
    # Cumulative returns → portfolio values
    cumulative = np.cumprod(1 + random_returns, axis=1) * initial_value
    
    # Final values
    final_values = cumulative[:, -1]
    final_returns = ((final_values - initial_value) / initial_value) * 100
    
    # Fan chart data: percentiles at each day
    fan_chart = []
    for d in range(days):
        day_values = ((cumulative[:, d] - initial_value) / initial_value) * 100
        fan_chart.append({
            "day": d + 1,
            "p5": round(float(np.percentile(day_values, 5)), 2),
            "p25": round(float(np.percentile(day_values, 25)), 2),
            "p50": round(float(np.percentile(day_values, 50)), 2),
            "p75": round(float(np.percentile(day_values, 75)), 2),
            "p95": round(float(np.percentile(day_values, 95)), 2),
        })
    
    return {
        "positive_prob": round(float((final_returns > 0).mean()), 3),
        "median_return_pct": round(float(np.median(final_returns)), 2),
        "worst_5pct": round(float(np.percentile(final_returns, 5)), 2),
        "best_5pct": round(float(np.percentile(final_returns, 95)), 2),
        "expected_return_pct": round(float(np.mean(final_returns)), 2),
        "fan_chart": fan_chart,
        "days": days,
        "simulations": simulations,
    }


def calculate_sharpe_ratio(returns: np.ndarray, risk_free_annual: float = 0.043) -> float:
    """
    Annualized Sharpe Ratio.
    Higher = better risk-adjusted return. >1 is good, >2 is excellent.
    """
    if len(returns) < 10 or np.std(returns) == 0:
        return 0.0
    
    daily_rf = risk_free_annual / 252
    excess_returns = returns - daily_rf
    
    sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252)
    return round(float(sharpe), 2)


def calculate_max_drawdown(prices: np.ndarray) -> dict:
    """
    Maximum drawdown: largest peak-to-trough decline.
    
    Returns:
        {"max_drawdown_pct": -15.3, "recovery_days": 12}
    """
    if len(prices) < 2:
        return {"max_drawdown_pct": 0, "peak_idx": 0, "trough_idx": 0}
    
    cummax = np.maximum.accumulate(prices)
    drawdowns = (prices - cummax) / cummax
    
    trough_idx = int(np.argmin(drawdowns))
    peak_idx = int(np.argmax(prices[:trough_idx + 1])) if trough_idx > 0 else 0
    
    max_dd = float(drawdowns[trough_idx]) * 100
    
    return {
        "max_drawdown_pct": round(max_dd, 2),
        "peak_idx": peak_idx,
        "trough_idx": trough_idx,
    }


def get_portfolio_risk_metrics(ticker_weights: dict, lookback_days: int = 90) -> dict:
    """
    Calculate full risk metrics for a weighted portfolio.
    
    Args:
        ticker_weights: {"BTC-USD": 0.3, "GC=F": 0.2, ...} (weights sum to 1)
        lookback_days: Days of history to use
    
    Returns combined risk metrics.
    """
    import yfinance as yf
    
    if not ticker_weights:
        return _empty_risk()
    
    # Fetch historical data for all tickers
    tickers = list(ticker_weights.keys())
    weights = np.array([ticker_weights[t] for t in tickers])
    
    try:
        data = yf.download(
            tickers, period=f"{lookback_days}d", interval="1d",
            auto_adjust=True, progress=False, threads=True,
        )
        
        if data.empty:
            return _empty_risk()
        
        # Handle single ticker vs multiple tickers
        if len(tickers) == 1:
            closes = data["Close"].values.reshape(-1, 1)
        else:
            closes = data["Close"][tickers].values
        
        # Drop rows with NaN
        mask = ~np.isnan(closes).any(axis=1)
        closes = closes[mask]
        
        if len(closes) < 15:
            return _empty_risk()
        
        # Daily returns per asset
        returns_matrix = np.diff(closes, axis=0) / closes[:-1]
        
        # Portfolio daily returns (weighted sum)
        portfolio_returns = returns_matrix @ weights
        
        # Portfolio value series (for max drawdown)
        portfolio_values = np.cumprod(1 + portfolio_returns) * 100
        
    except Exception as e:
        logger.warning(f"Failed to fetch risk data: {e}")
        return _empty_risk()
    
    # Calculate all metrics
    cvar = calculate_cvar(portfolio_returns)
    monte_carlo = monte_carlo_simulation(portfolio_returns, days=30)
    sharpe = calculate_sharpe_ratio(portfolio_returns)
    max_dd = calculate_max_drawdown(portfolio_values)
    
    volatility = float(np.std(portfolio_returns) * np.sqrt(252) * 100)  # Annualized
    
    result = {
        "cvar": cvar,
        "monte_carlo": monte_carlo,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "annualized_volatility": round(volatility, 2),
        "data_points": len(portfolio_returns),
        "lookback_days": lookback_days,
    }
    
    # Risk level classification based on CVaR
    cvar95 = abs(cvar["cvar_95"])
    if cvar95 > 5:
        result["risk_level"] = "hög"
        result["risk_label"] = f"Hög risk – CVaR 95%: {cvar['cvar_95']}%/dag"
    elif cvar95 > 2:
        result["risk_level"] = "medel"
        result["risk_label"] = f"Medelhög risk – CVaR 95%: {cvar['cvar_95']}%/dag"
    else:
        result["risk_level"] = "låg"
        result["risk_label"] = f"Låg risk – CVaR 95%: {cvar['cvar_95']}%/dag"
    
    logger.info(f"📊 Risk: CVaR95={cvar['cvar_95']}%, Sharpe={sharpe}, MaxDD={max_dd['max_drawdown_pct']}%")
    return result


def _empty_risk() -> dict:
    return {
        "cvar": {"var_95": 0, "cvar_95": 0, "var_99": 0, "cvar_99": 0},
        "monte_carlo": {
            "positive_prob": 0.5, "median_return_pct": 0,
            "worst_5pct": 0, "best_5pct": 0, "expected_return_pct": 0,
            "fan_chart": [],
        },
        "sharpe_ratio": 0,
        "max_drawdown": {"max_drawdown_pct": 0},
        "annualized_volatility": 0,
        "data_points": 0,
        "risk_level": "okänd",
        "risk_label": "Otillräcklig data",
    }
