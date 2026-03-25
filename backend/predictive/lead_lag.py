# ============================================================
# FIL: backend/predictive/lead_lag.py
# Detekterar vilka marknader som LEDER andra
# T.ex: US 10Y yield leder SP500 med 5 dagar
# Koppar leder industrikonjunkturen
# VIX leder aktienedgångar
# ============================================================

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Kända lead-lag-relationer att testa
KNOWN_PAIRS = [
    {"leader": "us10y", "follower": "sp500", "expected_direction": "INVERSE",
     "description": "Stigande räntor trycker aktier (med fördröjning)"},
    {"leader": "gold", "follower": "silver", "expected_direction": "SAME",
     "description": "Guld leder silver (men silver överskjuter)"},
    {"leader": "oil", "follower": "gold", "expected_direction": "SAME",
     "description": "Oljepris leder inflationshedge (guld)"},
    {"leader": "us10y", "follower": "gold", "expected_direction": "INVERSE",
     "description": "Stigande realräntor trycker guld"},
    {"leader": "sp500", "follower": "global-equity", "expected_direction": "SAME",
     "description": "US-marknaden leder globala aktier"},
    {"leader": "gold", "follower": "btc", "expected_direction": "SAME",
     "description": "Guld och Bitcoin som alternativa tillgångar"},
    {"leader": "us10y", "follower": "btc", "expected_direction": "INVERSE",
     "description": "Stigande räntor trycker riskfyllda tillgångar"},
    {"leader": "oil", "follower": "sp500", "expected_direction": "INVERSE",
     "description": "Stigande energikostnader trycker aktier"},
    {"leader": "eurusd", "follower": "gold", "expected_direction": "SAME",
     "description": "Svagare dollar = starkare guld"},
    {"leader": "sp500", "follower": "btc", "expected_direction": "SAME",
     "description": "Risk-on/off: BTC följer aktier med fördröjning"},
]


@dataclass
class LeadLagRelation:
    leader: str
    follower: str
    optimal_lag_days: int
    correlation: float
    direction: str
    strength: str
    is_active: bool
    recent_signal: str
    follower_prediction: str
    confidence: float


class LeadLagDetector:
    """
    Detekterar och utnyttjar lead-lag-relationer mellan marknader.

    Princip: Om marknad A konsekvent rör sig FÖRE marknad B
    kan vi använda A:s rörelser för att predicera B.
    """

    def __init__(self, max_lag_days: int = 20, min_correlation: float = 0.25):
        self.max_lag = max_lag_days
        self.min_corr = min_correlation

    def detect_all(self, returns: pd.DataFrame) -> List[LeadLagRelation]:
        """
        Testa alla kända par plus upptäck nya.
        returns: DataFrame med dagliga avkastningar, kolumner = tillgångar
        """
        results = []

        for pair in KNOWN_PAIRS:
            leader = pair["leader"]
            follower = pair["follower"]

            if leader not in returns.columns or follower not in returns.columns:
                continue

            result = self._test_pair(
                returns[leader].values,
                returns[follower].values,
                leader, follower,
                pair["expected_direction"]
            )
            if result:
                result.recent_signal = self._get_recent_signal(returns, leader)
                result.follower_prediction = self._predict_follower(result, returns, leader)
                results.append(result)

        results.sort(key=lambda x: abs(x.correlation), reverse=True)
        return results

    def _test_pair(
        self,
        leader_returns: np.ndarray,
        follower_returns: np.ndarray,
        leader_name: str,
        follower_name: str,
        expected_direction: str
    ) -> Optional[LeadLagRelation]:
        """Testa en specifik lead-lag-relation"""

        best_lag = 0
        best_corr = 0

        for lag in range(1, self.max_lag + 1):
            if lag >= len(leader_returns):
                break

            leader_slice = leader_returns[:-lag]
            follower_slice = follower_returns[lag:]

            min_length = min(len(leader_slice), len(follower_slice))
            if min_length < 30:
                continue

            leader_slice = leader_slice[:min_length]
            follower_slice = follower_slice[:min_length]

            # Remove NaN
            valid = ~(np.isnan(leader_slice) | np.isnan(follower_slice))
            if valid.sum() < 30:
                continue

            corr = float(np.corrcoef(leader_slice[valid], follower_slice[valid])[0, 1])

            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        if abs(best_corr) < self.min_corr:
            return None

        direction = "SAME" if best_corr > 0 else "INVERSE"
        strength = "STRONG" if abs(best_corr) > 0.5 else "MODERATE" if abs(best_corr) > 0.35 else "WEAK"

        # Är relationen aktiv på senaste 60 dagarna?
        is_active = True
        if len(leader_returns) >= 60 and len(follower_returns) >= 60 and best_lag > 0:
            recent_leader = leader_returns[-60:]
            recent_follower = follower_returns[-60:]
            try:
                rl = recent_leader[:-best_lag]
                rf = recent_follower[best_lag:]
                min_len = min(len(rl), len(rf))
                valid = ~(np.isnan(rl[:min_len]) | np.isnan(rf[:min_len]))
                if valid.sum() >= 10:
                    recent_corr = float(np.corrcoef(rl[:min_len][valid], rf[:min_len][valid])[0, 1])
                    is_active = abs(recent_corr) > self.min_corr * 0.8
            except Exception:
                is_active = True

        return LeadLagRelation(
            leader=leader_name,
            follower=follower_name,
            optimal_lag_days=best_lag,
            correlation=round(best_corr, 3),
            direction=direction,
            strength=strength,
            is_active=is_active,
            recent_signal="",
            follower_prediction="",
            confidence=round(abs(best_corr), 2)
        )

    def _get_recent_signal(self, returns: pd.DataFrame, leader: str) -> str:
        """Vad har ledaren gjort senaste dagarna?"""
        if leader not in returns.columns:
            return "INGEN DATA"

        recent = returns[leader].tail(5).dropna()
        if len(recent) == 0:
            return "INGEN DATA"

        cum_return = float((1 + recent).prod() - 1)

        if cum_return > 0.02:
            return f"STIGANDE (+{cum_return*100:.1f}% senaste 5d)"
        elif cum_return < -0.02:
            return f"FALLANDE ({cum_return*100:.1f}% senaste 5d)"
        else:
            return f"FLAT ({cum_return*100:.1f}% senaste 5d)"

    def _predict_follower(self, relation: LeadLagRelation, returns: pd.DataFrame, leader: str) -> str:
        """Predicera följarens rörelse baserat på ledarens senaste signal"""
        if leader not in returns.columns:
            return "INGEN PREDIKTION"

        recent = returns[leader].tail(5).dropna()
        if len(recent) == 0:
            return "INGEN PREDIKTION"

        cum_return = float((1 + recent).prod() - 1)

        if relation.direction == "SAME":
            predicted_direction = "UPP" if cum_return > 0 else "NER"
        else:
            predicted_direction = "NER" if cum_return > 0 else "UPP"

        magnitude = abs(cum_return) * abs(relation.correlation)
        time_note = f"inom {relation.optimal_lag_days} dagar"

        return f"{relation.follower} förväntad {predicted_direction} ({magnitude*100:.1f}%) {time_note} [konf: {relation.confidence:.0%}]"

    def get_actionable_signals(self, returns: pd.DataFrame) -> List[Dict]:
        """
        Hämta alla lead-lag-signaler som är aktionerbara just nu.
        Filtrerar: bara starka, aktiva relationer med tydlig signal.
        """
        relations = self.detect_all(returns)
        actionable = []

        for rel in relations:
            if not rel.is_active:
                continue
            if rel.strength == "WEAK":
                continue
            if "FLAT" in rel.recent_signal:
                continue

            actionable.append({
                "leader": rel.leader,
                "follower": rel.follower,
                "signal": rel.recent_signal,
                "prediction": rel.follower_prediction,
                "lag_days": rel.optimal_lag_days,
                "confidence": rel.confidence,
                "strength": rel.strength,
                "direction": rel.direction,
                "action": "KÖP" if "UPP" in rel.follower_prediction else "SÄLJ",
                "reasoning": f"{rel.leader} har rört sig → {rel.follower} följer typiskt efter {rel.optimal_lag_days}d"
            })

        return actionable
