# ============================================================
# FIL: backend/walkforward_backtest.py
# Walk-forward optimering med strikt temporal split
# ============================================================

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    train_months: int = 12        # Träningsperiod
    test_months: int = 3          # Testperiod
    min_train_samples: int = 200  # Minimum datapunkter för träning
    recalibrate_signals: bool = True


@dataclass
class WalkForwardResult:
    period_start: str
    period_end: str
    in_sample_sharpe: float
    out_sample_sharpe: float
    out_sample_return: float
    out_sample_drawdown: float
    n_trades: int
    regime_accuracy: float


class WalkForwardEngine:
    def __init__(self, config: WalkForwardConfig = None):
        self.config = config or WalkForwardConfig()
        self.results: List[WalkForwardResult] = []

    def run(self, price_data: pd.DataFrame, signals: pd.DataFrame) -> Dict:
        """
        price_data: DataFrame med datum-index, kolumner = tillgångar
        signals: DataFrame med datum-index, kolumner = signal-scores
        """
        results = []
        dates = price_data.index.sort_values()
        start = dates[0]
        end = dates[-1]

        train_delta = timedelta(days=self.config.train_months * 30)
        test_delta = timedelta(days=self.config.test_months * 30)

        current_start = start

        while current_start + train_delta + test_delta <= end:
            train_end = current_start + train_delta
            test_end = train_end + test_delta

            # Strikt temporal split
            train_prices = price_data[current_start:train_end]
            train_signals = signals[current_start:train_end]
            test_prices = price_data[train_end:test_end]
            test_signals = signals[train_end:test_end]

            if len(train_prices) < self.config.min_train_samples:
                current_start += test_delta
                continue

            # In-sample: optimera signalvikter
            optimal_weights = self._optimize_signal_weights(
                train_prices, train_signals
            )

            # Out-of-sample: testa med optimerade vikter
            oos_result = self._evaluate_period(
                test_prices, test_signals, optimal_weights
            )

            # In-sample resultat för jämförelse
            is_result = self._evaluate_period(
                train_prices, train_signals, optimal_weights
            )

            result = WalkForwardResult(
                period_start=str(train_end.date()),
                period_end=str(test_end.date()),
                in_sample_sharpe=is_result["sharpe"],
                out_sample_sharpe=oos_result["sharpe"],
                out_sample_return=oos_result["total_return"],
                out_sample_drawdown=oos_result["max_drawdown"],
                n_trades=oos_result["n_trades"],
                regime_accuracy=oos_result.get("regime_accuracy", 0)
            )
            results.append(result)

            # Flytta framåt
            current_start += test_delta

        self.results = results
        return self._aggregate_results(results)

    def _optimize_signal_weights(
        self, prices: pd.DataFrame, signals: pd.DataFrame
    ) -> np.ndarray:
        """Ridge regression med alpha=10 för signalvikter"""
        try:
            from sklearn.linear_model import Ridge
        except ImportError:
            # Fallback: equal weights if sklearn not available
            n_signals = signals.shape[1] if len(signals.shape) > 1 else 1
            return np.ones(n_signals) / n_signals

        returns = prices.pct_change().dropna()
        # Aligna signaler med nästa dags avkastning (T+1)
        min_len = min(len(signals) - 1, len(returns) - 1)
        if min_len < 30:
            n_signals = signals.shape[1] if len(signals.shape) > 1 else 1
            return np.ones(n_signals) / n_signals

        X = signals.iloc[:min_len].values
        y = returns.iloc[1:min_len + 1].mean(axis=1).values

        model = Ridge(alpha=10.0)
        model.fit(X, y)
        weights = model.coef_
        # Normalisera
        weights = weights / (np.abs(weights).sum() + 1e-8)
        return weights

    def _evaluate_period(
        self, prices: pd.DataFrame, signals: pd.DataFrame,
        signal_weights: np.ndarray
    ) -> Dict:
        """Utvärdera en period med givna signalvikter"""
        returns = prices.pct_change().dropna()

        if len(signals) == 0 or len(returns) == 0:
            return {"total_return": 0, "sharpe": 0, "max_drawdown": 0, "n_trades": 0}

        # Composite signal
        sig_values = signals.values
        if len(sig_values.shape) == 1:
            composite = sig_values * signal_weights[0] if len(signal_weights) > 0 else sig_values
        else:
            composite = sig_values @ signal_weights

        # Enkel strategi: long när composite > 0, flat annars
        # Med T+1 delay
        positions = np.zeros(len(composite))
        for i in range(1, len(composite)):
            positions[i] = 1.0 if composite[i-1] > 0 else 0.0

        min_len = min(len(returns), len(positions))
        strat_returns = returns.mean(axis=1).values[:min_len] * positions[:min_len]

        if len(strat_returns) == 0:
            return {"total_return": 0, "sharpe": 0, "max_drawdown": 0, "n_trades": 0}

        total_return = float((1 + pd.Series(strat_returns)).prod() - 1) * 100
        std = np.std(strat_returns)
        sharpe = float(np.mean(strat_returns) / (std + 1e-8) * np.sqrt(252)) if std > 0 else 0
        cumulative = (1 + pd.Series(strat_returns)).cumprod()
        max_dd = float((cumulative / cumulative.cummax() - 1).min() * 100)
        n_trades = int(np.sum(np.abs(np.diff(positions)) > 0))

        return {
            "total_return": round(total_return, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "n_trades": n_trades
        }

    def _aggregate_results(self, results: List[WalkForwardResult]) -> Dict:
        if not results:
            return {"error": "Inga perioder att utvärdera", "n_periods": 0}

        oos_sharpes = [r.out_sample_sharpe for r in results]
        is_sharpes = [r.in_sample_sharpe for r in results]
        oos_returns = [r.out_sample_return for r in results]

        avg_is = np.mean(is_sharpes)
        avg_oos = np.mean(oos_sharpes)

        return {
            "n_periods": len(results),
            "avg_oos_sharpe": round(float(avg_oos), 3),
            "avg_is_sharpe": round(float(avg_is), 3),
            "sharpe_decay": round(float(avg_is - avg_oos), 3),
            "avg_oos_return": round(float(np.mean(oos_returns)), 2),
            "worst_oos_return": round(float(min(oos_returns)), 2),
            "best_oos_return": round(float(max(oos_returns)), 2),
            "consistency": round(sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes), 2),
            "overfitting_ratio": round(float(avg_is / (avg_oos + 1e-8)), 2),
            "periods": [
                {
                    "start": r.period_start,
                    "end": r.period_end,
                    "is_sharpe": r.in_sample_sharpe,
                    "oos_sharpe": r.out_sample_sharpe,
                    "return": r.out_sample_return,
                    "drawdown": r.out_sample_drawdown,
                    "trades": r.n_trades
                }
                for r in results
            ]
        }
