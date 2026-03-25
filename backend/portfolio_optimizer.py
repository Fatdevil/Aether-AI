"""
Markowitz Mean-Variance Portfolio Optimizer
==========================================
Uses scipy.optimize to find mathematically optimal portfolio weights
along the efficient frontier, with AI signal adjustments on expected returns.

Three portfolios:
  - Conservative: minimize variance, target max ~12% volatility
  - Balanced: maximize Sharpe ratio (tangent portfolio)
  - Aggressive: maximize return, target min ~20% volatility
"""
import logging
import time
import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger(__name__)

# Simple cache for market data (avoid re-downloading)
_market_data_cache = {"data": None, "timestamp": 0, "ttl": 300}  # 5 min TTL

# Asset ID → yfinance ticker mapping
ASSET_TICKER_MAP = {
    # Core macro assets
    "btc": "BTC-USD",
    "gold": "GC=F",
    "silver": "SI=F",
    "oil": "BZ=F",
    "sp500": "^GSPC",
    "global-equity": "ACWI",
    "eurusd": "EURUSD=X",
    "us10y": "^TNX",
    # Sector ETFs (Fas 2)
    "sector-finance": "XLF",
    "sector-energy": "XLE",
    "sector-tech": "XLK",
    "sector-health": "XLV",
    "sector-defense": "ITA",
    # Regional ETFs (Fas 3)
    "region-em": "EEM",
    "region-europe": "VGK",
    "region-japan": "EWJ",
    "region-india": "INDA",
    # Leveraged ETFs (Turbo)
    "leveraged-sp500": "SSO",
    "leveraged-nasdaq": "QLD",
}

ASSET_NAMES = {
    "btc": "Bitcoin",
    "gold": "Guld (XAU)",
    "silver": "Silver (XAG)",
    "oil": "Råolja (Brent)",
    "sp500": "S&P 500",
    "global-equity": "Globala Aktier (ACWI)",
    "eurusd": "EUR/USD",
    "us10y": "US 10Y Räntor",
    "sector-finance": "Finans (XLF)",
    "sector-energy": "Energi (XLE)",
    "sector-tech": "Tech (XLK)",
    "sector-health": "Hälsa (XLV)",
    "sector-defense": "Försvar (ITA)",
    "region-em": "Tillväxtmarknader (EEM)",
    "region-europe": "Europa (VGK)",
    "region-japan": "Japan (EWJ)",
    "region-india": "Indien (INDA)",
    "leveraged-sp500": "S&P 500 2x (SSO)",
    "leveraged-nasdaq": "Nasdaq 2x (QLD)",
}

ASSET_COLORS = {
    "btc": "#f7931a", "global-equity": "#4facfe", "sp500": "#6c5ce7",
    "gold": "#ffd700", "silver": "#c0c0c0", "eurusd": "#00f2fe",
    "oil": "#636e72", "us10y": "#9d4edd",
    "sector-finance": "#2ecc71", "sector-energy": "#e67e22",
    "sector-tech": "#3498db", "sector-health": "#e74c3c",
    "sector-defense": "#95a5a6",
    "region-em": "#e84393", "region-europe": "#0984e3",
    "region-japan": "#fd79a8", "region-india": "#00cec9",
    "leveraged-sp500": "#ff6b6b", "leveraged-nasdaq": "#ffa502",
}

# CAPM parameters
RISK_FREE_RATE = 0.04   # 4% annual
MARKET_PREMIUM = 0.06   # 6% equity risk premium

# Optimization constraints
MAX_WEIGHT = 0.35  # Max 35% in any single asset
MIN_WEIGHT = 0.01  # Min 1% in each asset (diversification floor, 17 assets)


def _fetch_market_data(asset_ids: list[str]) -> tuple:
    """Fetch 1 year of historical data and compute returns, covariance, CAPM expected returns.

    Returns: (asset_ids_available, expected_returns, cov_matrix)
    """
    import yfinance as yf

    tickers = []
    valid_ids = []
    for aid in asset_ids:
        t = ASSET_TICKER_MAP.get(aid)
        if t:
            tickers.append(t)
            valid_ids.append(aid)

    if len(tickers) < 2:
        raise ValueError("Need at least 2 assets for optimization")

    data = yf.download(tickers, period="1y", progress=False)
    if data is None or data.empty:
        raise ValueError("Failed to download market data")

    # Handle MultiIndex columns from yfinance
    if isinstance(data.columns, __import__('pandas').MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            close = data["Close"]
        else:
            close = data
    elif "Close" in data.columns:
        close = data[["Close"]]
        close.columns = tickers[:1]  # single ticker case
    else:
        close = data

    # Forward-fill weekend/holiday gaps (BTC trades 7/7, stocks 5/7)
    close = close.ffill()

    # Drop columns with >50% missing (even after ffill)
    close = close.dropna(axis=1, thresh=int(len(close) * 0.5))
    close = close.dropna()

    if len(close.shape) < 2 or close.shape[1] < 2 or len(close) < 30:
        raise ValueError(f"Insufficient data: shape={close.shape}")

    returns = close.pct_change().dropna()

    # Map columns back to asset IDs
    ticker_to_id = {v: k for k, v in ASSET_TICKER_MAP.items()}
    cols = returns.columns.tolist()

    # Flatten any remaining multi-index
    if cols and hasattr(cols[0], '__len__') and not isinstance(cols[0], str):
        cols = [c[0] if isinstance(c, tuple) else c for c in cols]

    available_ids = []
    available_indices = []
    for i, col in enumerate(cols):
        col_str = str(col).strip()
        aid = ticker_to_id.get(col_str)
        if aid and aid in valid_ids:
            available_ids.append(aid)
            available_indices.append(i)

    logger.info(f"  Data columns: {cols}, mapped: {available_ids}")

    if len(available_ids) < 2:
        raise ValueError(f"Could not map tickers: cols={cols}, mapped={available_ids}")

    # Subset returns to available assets
    returns_subset = returns.iloc[:, available_indices]
    n = len(available_ids)

    # CAPM expected returns: E(Ri) = Rf + βi * Market Premium
    market_returns = returns_subset.mean(axis=1)
    market_var = market_returns.var()

    expected_returns = np.zeros(n)
    for i in range(n):
        if market_var > 0:
            beta = returns_subset.iloc[:, i].cov(market_returns) / market_var
            expected_returns[i] = RISK_FREE_RATE + beta * MARKET_PREMIUM
        else:
            expected_returns[i] = RISK_FREE_RATE

    cov_matrix = returns_subset.cov().values * 252  # Annualize

    return available_ids, expected_returns, cov_matrix


def _adjust_returns_with_ai(
    expected_returns: np.ndarray,
    asset_ids: list[str],
    assets_analysis: dict,
) -> np.ndarray:
    """Adjust CAPM expected returns with AI signals (±30% tilt).

    Strong buy signals increase expected return, strong sell signals decrease it.
    This makes the optimizer favor assets the AI is bullish on.
    """
    adjusted = expected_returns.copy()
    for i, aid in enumerate(asset_ids):
        analysis = assets_analysis.get(aid)
        if analysis:
            score = analysis.get("finalScore", 0)
            # Map score [-10, +10] to adjustment multiplier [0.7, 1.3]
            # Score +10 → 1.3x expected return
            # Score -10 → 0.7x expected return
            # Score 0  → 1.0x (no change)
            adjustment = 1.0 + (score / 10.0) * 0.3
            adjustment = max(0.7, min(1.3, adjustment))
            adjusted[i] *= adjustment
    return adjusted


def _portfolio_variance(weights, cov_matrix):
    """Portfolio variance given weights and covariance matrix."""
    return np.dot(weights.T, np.dot(cov_matrix, weights))


def _portfolio_volatility(weights, cov_matrix):
    """Portfolio annualized volatility."""
    return np.sqrt(_portfolio_variance(weights, cov_matrix))


def _negative_sharpe(weights, expected_returns, cov_matrix):
    """Negative Sharpe ratio (we minimize, so negate to maximize Sharpe)."""
    port_return = np.dot(weights, expected_returns)
    port_vol = _portfolio_volatility(weights, cov_matrix)
    if port_vol < 1e-10:
        return 0
    return -(port_return - RISK_FREE_RATE) / port_vol


def _optimize_max_sharpe(expected_returns, cov_matrix, n_assets):
    """Find the maximum Sharpe ratio portfolio (tangent portfolio)."""
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # weights sum to 1
    ]
    bounds = [(MIN_WEIGHT, MAX_WEIGHT)] * n_assets

    # Try multiple starting points to avoid local minima
    best_result = None
    best_sharpe = float('inf')

    for _ in range(5):
        w0 = np.random.dirichlet(np.ones(n_assets))
        result = minimize(
            _negative_sharpe,
            w0,
            args=(expected_returns, cov_matrix),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )
        if result.success and result.fun < best_sharpe:
            best_sharpe = result.fun
            best_result = result

    if best_result is None:
        # Fallback: equal weight
        return np.ones(n_assets) / n_assets

    return best_result.x


def _optimize_min_variance(expected_returns, cov_matrix, n_assets, max_vol=None):
    """Find the minimum variance portfolio, optionally with a max volatility constraint."""
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
    ]
    if max_vol is not None:
        constraints.append(
            {"type": "ineq", "fun": lambda w: max_vol - _portfolio_volatility(w, cov_matrix)}
        )
    bounds = [(MIN_WEIGHT, MAX_WEIGHT)] * n_assets

    # Minimize variance
    best_result = None
    best_var = float('inf')

    for _ in range(5):
        w0 = np.random.dirichlet(np.ones(n_assets))
        result = minimize(
            _portfolio_variance,
            w0,
            args=(cov_matrix,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )
        if result.success and result.fun < best_var:
            best_var = result.fun
            best_result = result

    if best_result is None:
        return np.ones(n_assets) / n_assets

    return best_result.x


def _optimize_target_return(expected_returns, cov_matrix, n_assets, target_return):
    """Find the portfolio that minimizes variance for a given target return."""
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: np.dot(w, expected_returns) - target_return},
    ]
    bounds = [(MIN_WEIGHT, MAX_WEIGHT)] * n_assets

    best_result = None
    best_var = float('inf')

    for _ in range(5):
        w0 = np.random.dirichlet(np.ones(n_assets))
        result = minimize(
            _portfolio_variance,
            w0,
            args=(cov_matrix,),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )
        if result.success and result.fun < best_var:
            best_var = result.fun
            best_result = result

    if best_result is None:
        return _optimize_max_sharpe(expected_returns, cov_matrix, n_assets)

    return best_result.x


def optimize_portfolios(assets_analysis: dict) -> dict:
    """Main entry: compute 3 MPT-optimized portfolios.

    Returns dict with 'conservative', 'balanced', 'aggressive' portfolios,
    each containing optimal weights, expected return, volatility, and Sharpe ratio.
    """
    asset_ids = list(assets_analysis.keys())

    try:
        available_ids, base_returns, cov_matrix = _fetch_market_data(asset_ids)
    except Exception as e:
        logger.error(f"MPT data fetch failed: {e}")
        return None

    n = len(available_ids)
    logger.info(f"🧮 MPT Optimization: {n} assets available: {available_ids}")

    # Adjust expected returns with AI signals
    expected_returns = _adjust_returns_with_ai(base_returns, available_ids, assets_analysis)

    logger.info(f"  CAPM returns: {dict(zip(available_ids, [f'{r:.4f}' for r in base_returns]))}")
    logger.info(f"  AI-adjusted:  {dict(zip(available_ids, [f'{r:.4f}' for r in expected_returns]))}")

    # === Balanced: Max Sharpe (tangent portfolio) ===
    w_balanced = _optimize_max_sharpe(expected_returns, cov_matrix, n)
    ret_balanced = np.dot(w_balanced, expected_returns)
    vol_balanced = _portfolio_volatility(w_balanced, cov_matrix)

    # === Conservative: Target the return that's 60% of the balanced return ===
    # This gives a point significantly to the left on the frontier
    target_conservative_return = RISK_FREE_RATE + (ret_balanced - RISK_FREE_RATE) * 0.5
    w_conservative = _optimize_target_return(expected_returns, cov_matrix, n, target_conservative_return)
    ret_conservative = np.dot(w_conservative, expected_returns)
    vol_conservative = _portfolio_volatility(w_conservative, cov_matrix)

    # If conservative ended up riskier than balanced (can happen with constraints), use min variance
    if vol_conservative >= vol_balanced:
        w_conservative = _optimize_min_variance(expected_returns, cov_matrix, n)
        ret_conservative = np.dot(w_conservative, expected_returns)
        vol_conservative = _portfolio_volatility(w_conservative, cov_matrix)

    # === Aggressive: Target return that's 140% of balanced ===
    target_aggressive_return = RISK_FREE_RATE + (ret_balanced - RISK_FREE_RATE) * 1.5
    w_aggressive = _optimize_target_return(expected_returns, cov_matrix, n, target_aggressive_return)
    ret_aggressive = np.dot(w_aggressive, expected_returns)
    vol_aggressive = _portfolio_volatility(w_aggressive, cov_matrix)

    # If aggressive couldn't achieve higher return, maximize return instead
    if ret_aggressive <= ret_balanced:
        # Maximize return (minimize negative return)
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(MIN_WEIGHT, MAX_WEIGHT)] * n
        best_result = None
        best_ret = -float('inf')
        for _ in range(5):
            w0 = np.random.dirichlet(np.ones(n))
            result = minimize(
                lambda w: -np.dot(w, expected_returns),
                w0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )
            if result.success and -result.fun > best_ret:
                best_ret = -result.fun
                best_result = result
        if best_result:
            w_aggressive = best_result.x
            ret_aggressive = np.dot(w_aggressive, expected_returns)
            vol_aggressive = _portfolio_volatility(w_aggressive, cov_matrix)

    # Build result
    def _build_portfolio(weights, exp_return, volatility, profile_id, name, emoji, description):
        allocations = []
        cash_weight = 0
        for i, aid in enumerate(available_ids):
            w_pct = round(float(weights[i]) * 100, 1)
            if w_pct < 1:
                cash_weight += w_pct
                w_pct = 0

            analysis = assets_analysis.get(aid, {})
            score = analysis.get("finalScore", 0)
            action = "buy" if score >= 0 else "sell"

            allocations.append({
                "assetId": aid,
                "name": ASSET_NAMES.get(aid, aid),
                "weight": round(w_pct),
                "action": action,
                "color": ASSET_COLORS.get(aid, "#888"),
                "score": score,
            })

        total_weight = sum(a["weight"] for a in allocations)
        sharpe = (exp_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0

        return {
            "id": profile_id,
            "name": name,
            "emoji": emoji,
            "description": description,
            "allocations": allocations,
            "cash": max(0, 100 - total_weight),
            "total_weight": total_weight,
            "expected_return": round(float(exp_return * 100), 1),
            "volatility": round(float(volatility * 100), 1),
            "sharpe_ratio": round(float(sharpe), 2),
        }

    # === Turbo: Aggressive base + leveraged ETFs (max 20%) ===
    # Start from aggressive weights, then replace up to 20% with 2x instruments
    w_turbo = w_aggressive.copy()
    lev_ids = ["leveraged-sp500", "leveraged-nasdaq"]
    lev_indices = [available_ids.index(lid) for lid in lev_ids if lid in available_ids]

    if lev_indices:
        # Allocate 10% to each leveraged ETF (20% total)
        lev_allocation = 0.10  # 10% each
        total_lev = lev_allocation * len(lev_indices)

        # Scale down non-leveraged weights to make room
        non_lev_mask = np.ones(n, dtype=bool)
        for idx in lev_indices:
            non_lev_mask[idx] = False

        non_lev_sum = w_turbo[non_lev_mask].sum()
        if non_lev_sum > 0:
            w_turbo[non_lev_mask] *= (1.0 - total_lev) / non_lev_sum

        for idx in lev_indices:
            w_turbo[idx] = lev_allocation

        # Normalize to sum to 1
        w_turbo = w_turbo / w_turbo.sum()

    # Turbo returns: leveraged ETFs have ~2x the expected return but ~2x vol
    ret_turbo = np.dot(w_turbo, expected_returns)
    vol_turbo = _portfolio_volatility(w_turbo, cov_matrix)

    profiles = {
        "conservative": _build_portfolio(
            w_conservative, ret_conservative, vol_conservative,
            "conservative", "Försiktig", "🛡️",
            f"MPT-optimerad lågrisportfölj. Förväntad avk: {ret_conservative*100:.1f}%, Vol: {vol_conservative*100:.1f}%"
        ),
        "balanced": _build_portfolio(
            w_balanced, ret_balanced, vol_balanced,
            "balanced", "Balanserad", "⚖️",
            f"Max Sharpe-portfölj (tangentportföljen). Förväntad avk: {ret_balanced*100:.1f}%, Vol: {vol_balanced*100:.1f}%"
        ),
        "aggressive": _build_portfolio(
            w_aggressive, ret_aggressive, vol_aggressive,
            "aggressive", "Aggressiv", "🚀",
            f"MPT-optimerad tillväxtportfölj. Förväntad avk: {ret_aggressive*100:.1f}%, Vol: {vol_aggressive*100:.1f}%"
        ),
        "turbo": _build_portfolio(
            w_turbo, ret_turbo, vol_turbo,
            "turbo", "Turbo", "🔥",
            f"Hävstångsportfölj med 2x ETF:er (max 20%). Förväntad avk: {ret_turbo*100:.1f}%, Vol: {vol_turbo*100:.1f}%. ⚠️ Mycket hög risk."
        ),
    }

    logger.info(f"  ✅ Conservative: ret={ret_conservative*100:.1f}%, vol={vol_conservative*100:.1f}%")
    logger.info(f"  ✅ Balanced:     ret={ret_balanced*100:.1f}%, vol={vol_balanced*100:.1f}%, sharpe={profiles['balanced']['sharpe_ratio']}")
    logger.info(f"  ✅ Aggressive:   ret={ret_aggressive*100:.1f}%, vol={vol_aggressive*100:.1f}%")
    logger.info(f"  ✅ Turbo:        ret={ret_turbo*100:.1f}%, vol={vol_turbo*100:.1f}%")

    return profiles


# ============================================================
# RegimeAwareOptimizer: Separate covariance matrices per regime
# ============================================================

import pandas as pd

class RegimeAwareOptimizer:
    """
    Tre kovariansmatriser: RISK_ON, NEUTRAL, RISK_OFF
    Väljer matris baserat på detekterad regim
    """

    def __init__(self, price_data: pd.DataFrame, regime_labels: pd.Series):
        """
        price_data: dagliga priser (datum-index, tillgångs-kolumner)
        regime_labels: Series med "RISK_ON", "NEUTRAL", "RISK_OFF" per datum
        """
        self.returns = price_data.pct_change().dropna()
        self.regime_labels = regime_labels
        self.cov_matrices = {}
        self.mean_returns = {}
        self._build_regime_matrices()

    def _build_regime_matrices(self):
        for regime in ["RISK_ON", "NEUTRAL", "RISK_OFF"]:
            mask = self.regime_labels == regime
            regime_returns = self.returns[mask]

            if len(regime_returns) < 30:
                # Fallback till full sample med shrinkage
                regime_returns = self.returns

            # Ledoit-Wolf shrinkage för stabilitet
            cov = self._shrink_covariance(regime_returns)
            self.cov_matrices[regime] = cov
            self.mean_returns[regime] = regime_returns.mean() * 252  # Annualisera

    def _shrink_covariance(self, returns: pd.DataFrame, shrinkage: float = 0.3) -> np.ndarray:
        """Ledoit-Wolf-liknande shrinkage mot diagonal"""
        sample_cov = returns.cov().values * 252
        target = np.diag(np.diag(sample_cov))  # Diagonal matris
        return (1 - shrinkage) * sample_cov + shrinkage * target

    def optimize(
        self,
        regime: str,
        profile: str = "balanced",
        risk_free_rate: float = 0.035
    ) -> dict:
        """Mean-CVaR optimering för given regim och profil"""
        cov = self.cov_matrices.get(regime, self.cov_matrices.get("NEUTRAL"))
        mu = self.mean_returns.get(regime, self.mean_returns.get("NEUTRAL"))
        n_assets = len(mu)
        assets = self.returns.columns.tolist()

        # Profilbegränsningar
        PROFILE_CONSTRAINTS = {
            "conservative": {"max_risk": 0.35, "min_cash": 0.30, "max_single": 0.10},
            "balanced":     {"max_risk": 0.55, "min_cash": 0.15, "max_single": 0.15},
            "aggressive":   {"max_risk": 0.75, "min_cash": 0.05, "max_single": 0.20},
            "turbo":        {"max_risk": 1.00, "min_cash": 0.03, "max_single": 0.25},
        }
        pc = PROFILE_CONSTRAINTS.get(profile, PROFILE_CONSTRAINTS["balanced"])

        def neg_sharpe(weights):
            port_return = np.dot(weights, mu)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            return -(port_return - risk_free_rate) / (port_vol + 1e-8)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0, pc["max_single"]) for _ in range(n_assets)]
        w0 = np.ones(n_assets) / n_assets

        result = minimize(
            neg_sharpe, w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000}
        )

        weights = result.x
        port_return = float(np.dot(weights, mu))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov, weights))))
        sharpe = (port_return - risk_free_rate) / (port_vol + 1e-8)

        return {
            "weights": {assets[i]: round(float(weights[i]) * 100, 2) for i in range(n_assets)},
            "expected_return": round(port_return * 100, 2),
            "volatility": round(port_vol * 100, 2),
            "sharpe": round(float(sharpe), 3),
            "regime_used": regime,
            "profile": profile
        }


# ============================================================
# Mean-CVaR optimering (bättre tail-risk-hantering)
# ============================================================

def compute_cvar(returns: np.ndarray, weights: np.ndarray, alpha: float = 0.05) -> float:
    """
    Conditional Value at Risk (CVaR) at alpha confidence level.
    = Genomsnittlig förlust de alpha% sämsta dagarna.
    """
    portfolio_returns = returns @ weights
    sorted_returns = np.sort(portfolio_returns)
    cutoff_index = int(np.floor(alpha * len(sorted_returns)))
    if cutoff_index == 0:
        cutoff_index = 1
    cvar = -np.mean(sorted_returns[:cutoff_index])
    return float(cvar)


def optimize_mean_cvar(
    returns_df: pd.DataFrame,
    risk_free_rate: float = 0.035,
    alpha: float = 0.05,
    max_cvar: float = 0.15,
    bounds: list = None
) -> dict:
    """
    Maximera Sharpe-kvot med CVaR-begränsning
    istället för volatilitetsbegränsning.
    """
    mu = returns_df.mean().values * 252
    ret_matrix = returns_df.values
    n = len(mu)
    assets = returns_df.columns.tolist()

    if bounds is None:
        bounds = [(0, 0.15) for _ in range(n)]

    def neg_sharpe_cvar(weights):
        port_return = np.dot(weights, mu)
        cvar = compute_cvar(ret_matrix, weights, alpha)
        return -(port_return - risk_free_rate) / (cvar * np.sqrt(252) + 1e-8)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "ineq", "fun": lambda w: max_cvar - compute_cvar(ret_matrix, w, alpha)},
    ]

    w0 = np.ones(n) / n
    result = minimize(
        neg_sharpe_cvar, w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000}
    )

    weights = result.x
    port_return = float(np.dot(weights, mu))
    cvar_val = compute_cvar(ret_matrix, weights, alpha)
    port_vol = float(np.sqrt(np.dot(weights.T, np.dot(returns_df.cov().values * 252, weights))))

    return {
        "weights": {assets[i]: round(float(weights[i]) * 100, 2) for i in range(n)},
        "expected_return_pct": round(port_return * 100, 2),
        "volatility_pct": round(port_vol * 100, 2),
        "cvar_95_pct": round(cvar_val * np.sqrt(252) * 100, 2),
        "sharpe_cvar": round((port_return - risk_free_rate) / (cvar_val * np.sqrt(252) + 1e-8), 3)
    }
