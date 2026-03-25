# ============================================================
# FIL: backend/predictive/convexity_optimizer.py
# Scenario-baserad portföljoptimering
#
# ISTÄLLET för att optimera på HISTORISK data (som standard MPT)
# optimerar vi på FRAMTIDA SCENARION från event trees.
# ============================================================

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from scipy.optimize import minimize
import logging

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    name: str
    probability: float
    asset_returns: Dict[str, float]


@dataclass
class ConvexPortfolio:
    weights: Dict[str, float]
    expected_return: float
    worst_case_return: float
    best_case_return: float
    probability_of_loss: float
    convexity_score: float
    scenario_returns: Dict[str, float]


class ConvexityOptimizer:
    def __init__(self, assets: List[str], risk_free_rate: float = 0.035):
        self.assets = assets
        self.n = len(assets)
        self.rf = risk_free_rate

    def build_scenarios_from_trees(self, event_trees: List[Dict]) -> List[Scenario]:
        scenarios = []
        for tree in event_trees:
            leaves = self._extract_leaves(tree)
            for leaf in leaves:
                scenarios.append(Scenario(
                    name=leaf.get("event", "Scenario"),
                    probability=float(leaf.get("probability", 0.1)),
                    asset_returns={
                        a: float(leaf.get("asset_impacts", {}).get(a, 0)) / 100
                        for a in self.assets
                    }
                ))

        total_prob = sum(s.probability for s in scenarios)
        if total_prob > 0:
            for s in scenarios:
                s.probability /= total_prob

        return scenarios

    def _extract_leaves(self, node: Dict, path_prob: float = 1.0) -> List[Dict]:
        prob = path_prob * float(node.get("probability", 1.0))
        branches = node.get("branches", node.get("children", []))
        if not branches:
            result = dict(node)
            result["probability"] = prob
            return [result]
        leaves = []
        for branch in branches:
            leaves.extend(self._extract_leaves(branch, prob))
        return leaves

    def optimize_max_expected(
        self,
        scenarios: List[Scenario],
        max_worst_case_loss: float = -0.10,
        max_single_weight: float = 0.25,
    ) -> ConvexPortfolio:
        n = self.n
        n_scenarios = len(scenarios)
        if n_scenarios == 0 or n == 0:
            return ConvexPortfolio({}, 0, 0, 0, 0, 0, {})

        R = np.zeros((n_scenarios, n))
        probs = np.zeros(n_scenarios)
        for i, scenario in enumerate(scenarios):
            probs[i] = scenario.probability
            for j, asset in enumerate(self.assets):
                R[i, j] = scenario.asset_returns.get(asset, 0)

        def neg_expected_return(w):
            scenario_returns = R @ w
            return -float(np.dot(probs, scenario_returns))

        def worst_case_constraint(w):
            scenario_returns = R @ w
            return float(np.min(scenario_returns)) - max_worst_case_loss

        constraints = [
            {"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0},
            {"type": "ineq", "fun": worst_case_constraint},
        ]
        bounds = [(0, max_single_weight) for _ in range(n)]
        w0 = np.ones(n) / n

        result = minimize(neg_expected_return, w0, method="SLSQP",
                         bounds=bounds, constraints=constraints,
                         options={"maxiter": 1000})

        weights = result.x
        scenario_returns = R @ weights
        expected = float(np.dot(probs, scenario_returns))
        worst = float(np.min(scenario_returns))
        best = float(np.max(scenario_returns))
        prob_loss = float(np.sum(probs[scenario_returns < 0]))
        convexity = float(np.sum(scenario_returns > 0)) / n_scenarios

        return ConvexPortfolio(
            weights={self.assets[i]: round(float(weights[i]) * 100, 2) for i in range(n)},
            expected_return=round(expected * 100, 2),
            worst_case_return=round(worst * 100, 2),
            best_case_return=round(best * 100, 2),
            probability_of_loss=round(prob_loss * 100, 1),
            convexity_score=round(convexity, 2),
            scenario_returns={
                scenarios[i].name: round(float(scenario_returns[i]) * 100, 2)
                for i in range(n_scenarios)
            }
        )

    def optimize_max_convexity(
        self,
        scenarios: List[Scenario],
        min_expected_return: float = 0.03,
        max_single_weight: float = 0.25
    ) -> ConvexPortfolio:
        n = self.n
        n_scenarios = len(scenarios)
        if n_scenarios == 0 or n == 0:
            return ConvexPortfolio({}, 0, 0, 0, 0, 0, {})

        R = np.zeros((n_scenarios, n))
        probs = np.zeros(n_scenarios)
        for i, scenario in enumerate(scenarios):
            probs[i] = scenario.probability
            for j, asset in enumerate(self.assets):
                R[i, j] = scenario.asset_returns.get(asset, 0)

        def neg_convexity(w):
            scenario_returns = R @ w
            softmax_positive = np.sum(1 / (1 + np.exp(-50 * scenario_returns)))
            return -float(softmax_positive)

        def min_return_constraint(w):
            scenario_returns = R @ w
            return float(np.dot(probs, scenario_returns)) - min_expected_return

        constraints = [
            {"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0},
            {"type": "ineq", "fun": min_return_constraint},
        ]
        bounds = [(0, max_single_weight) for _ in range(n)]
        w0 = np.ones(n) / n

        result = minimize(neg_convexity, w0, method="SLSQP",
                         bounds=bounds, constraints=constraints,
                         options={"maxiter": 1000})

        weights = result.x
        scenario_returns = R @ weights
        expected = float(np.dot(probs, scenario_returns))
        worst = float(np.min(scenario_returns))
        best = float(np.max(scenario_returns))
        prob_loss = float(np.sum(probs[scenario_returns < 0]))
        convexity = float(np.sum(scenario_returns > 0)) / n_scenarios

        return ConvexPortfolio(
            weights={self.assets[i]: round(float(weights[i]) * 100, 2) for i in range(n)},
            expected_return=round(expected * 100, 2),
            worst_case_return=round(worst * 100, 2),
            best_case_return=round(best * 100, 2),
            probability_of_loss=round(prob_loss * 100, 1),
            convexity_score=round(convexity, 2),
            scenario_returns={
                scenarios[i].name: round(float(scenario_returns[i]) * 100, 2)
                for i in range(n_scenarios)
            }
        )

    def compare_portfolios(self, current_weights: Dict[str, float], scenarios: List[Scenario]) -> Dict:
        if not scenarios or not self.assets:
            return {"error": "No scenarios or assets"}

        n_scenarios = len(scenarios)
        w_current = np.array([current_weights.get(a, 0) / 100 for a in self.assets])
        R = np.zeros((n_scenarios, len(self.assets)))
        probs = np.zeros(n_scenarios)
        for i, s in enumerate(scenarios):
            probs[i] = s.probability
            for j, a in enumerate(self.assets):
                R[i, j] = s.asset_returns.get(a, 0)

        current_returns = R @ w_current
        current_expected = float(np.dot(probs, current_returns))
        current_worst = float(np.min(current_returns))
        current_prob_loss = float(np.sum(probs[current_returns < 0]))

        opt_expected = self.optimize_max_expected(scenarios)
        opt_convex = self.optimize_max_convexity(scenarios)

        return {
            "current_portfolio": {
                "expected_return": round(current_expected * 100, 2),
                "worst_case": round(current_worst * 100, 2),
                "prob_loss": round(current_prob_loss * 100, 1),
            },
            "max_expected_portfolio": {
                "weights": opt_expected.weights,
                "expected_return": opt_expected.expected_return,
                "worst_case": opt_expected.worst_case_return,
                "improvement": round(opt_expected.expected_return - current_expected * 100, 2)
            },
            "max_convexity_portfolio": {
                "weights": opt_convex.weights,
                "convexity_score": opt_convex.convexity_score,
                "prob_loss": opt_convex.probability_of_loss,
            },
            "recommendation": "MAX_EXPECTED" if current_prob_loss < 0.3 else "MAX_CONVEXITY"
        }
