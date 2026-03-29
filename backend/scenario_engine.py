# ============================================================
# SCENARIO ENGINE — Omega Portfolio Generator
#
# Weekly scenario generation + minimum-regret optimization
# Runs parallel to Alpha portfolio (L7) without modifying it.
#
# Flow:
# 1. Gemini generates 3-5 macro scenarios (weekly)
# 2. Monte Carlo simulates 1000 portfolios per scenario
# 3. Minimum-regret optimizer finds best worst-case portfolio
# 4. Portfolio Tracker compares Alpha vs Omega daily
# ============================================================

import json
import os
import logging
import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from scipy.optimize import minimize

logger = logging.getLogger("aether.scenario_engine")

DATA_FILE = "data/scenario_engine.json"

# Same asset universe as portfolio_optimizer.py
OMEGA_ASSETS = [
    "sp500", "gold", "us10y", "oil", "btc",
    "global-equity", "eurusd", "silver",
    "sector-tech", "sector-energy", "sector-finance", "sector-health",
    "region-em", "region-europe",
]

ASSET_LABELS = {
    "sp500": "S&P 500", "gold": "Guld", "us10y": "US 10Y",
    "oil": "Olja", "btc": "Bitcoin", "global-equity": "Globala Aktier",
    "eurusd": "EUR/USD", "silver": "Silver",
    "sector-tech": "Tech", "sector-energy": "Energi",
    "sector-finance": "Finans", "sector-health": "Halsa",
    "region-em": "EM", "region-europe": "Europa",
}

# Historical volatility estimates (annualized, approximate)
HIST_VOL = {
    "sp500": 0.16, "gold": 0.15, "us10y": 0.08, "oil": 0.35,
    "btc": 0.60, "global-equity": 0.17, "eurusd": 0.08, "silver": 0.25,
    "sector-tech": 0.22, "sector-energy": 0.28, "sector-finance": 0.20,
    "sector-health": 0.16, "region-em": 0.20, "region-europe": 0.18,
}


# ============================================================
# DATAMODELLER
# ============================================================

@dataclass
class Scenario:
    name: str
    probability: float
    description: str
    asset_returns: Dict[str, float]  # {"sp500": 0.08, "gold": -0.02, ...}
    timeframe: str = "6 months"

@dataclass
class OmegaPortfolio:
    weights: Dict[str, float]        # {"sp500": 0.20, "gold": 0.15, ...}
    scenarios: List[Scenario] = field(default_factory=list)
    expected_return: float = 0.0     # Probability-weighted
    worst_case_return: float = 0.0   # Minimum-regret number
    cvar_5pct: float = 0.0           # Monte Carlo CVaR
    sharpe_estimate: float = 0.0
    generated_at: str = ""
    generation_method: str = ""


# ============================================================
# SCENARIOGENERERING (1 Gemini-anrop/vecka)
# ============================================================

SCENARIO_PROMPT = """Du ar en makroekonomisk strateg. Generera 3-5 marknadscenarier
for de kommande 6 manaderna baserat pa nuvarande marknadsdata.

TILLGANGAR du maste inkludera i varje scenario:
{assets}

For varje scenario, ange:
- Namn (kort, beskrivande)
- Sannolikhet (0.0-1.0, summa = 1.0)
- Beskrivning (2-3 meningar)
- Forvantad avkastning for varje tillgang (i decimal, t.ex. 0.08 = +8%)

Svara ENBART med JSON:
{{
    "scenarios": [
        {{
            "name": "Soft Landing",
            "probability": 0.40,
            "description": "Fed lyckas sanka inflation utan recession...",
            "asset_returns": {{
                "sp500": 0.08,
                "gold": -0.02,
                ...
            }}
        }},
        ...
    ]
}}

REGLER:
- Sannolikheter MASTE summera till 1.0
- Inkludera minst ett negativt scenario (recession/kris)
- Avkastningar ska vara REALISTISKA (SP500 max +/-30%, Gold max +/-25%)
- Varje tillgang maste ha en avkastning i VARJE scenario"""


async def generate_scenarios(
    regime: str = "NEUTRAL",
    political_risk: str = "NORMAL",
    market_data: dict = None,
) -> List[Scenario]:
    """Generate 3-5 market scenarios via Gemini (1 call/week)."""
    try:
        from llm_provider import call_llm_tiered, parse_llm_json
    except ImportError:
        logger.warning("LLM provider not available, using fallback scenarios")
        return _fallback_scenarios(regime)

    assets_str = ", ".join(OMEGA_ASSETS)

    context_parts = [f"Aktuellt regime: {regime}", f"Politisk risk: {political_risk}"]
    if market_data:
        if "vix" in market_data:
            context_parts.append(f"VIX: {market_data['vix']}")
        if "sp500_ytd" in market_data:
            context_parts.append(f"SP500 YTD: {market_data['sp500_ytd']:.1%}")

    context = "\n".join(context_parts)
    prompt = SCENARIO_PROMPT.format(assets=assets_str) + f"\n\nKONTEXT:\n{context}"

    response, provider = await call_llm_tiered(
        1,  # Tier 1 (Flash) — cheap, sufficient for scenarios
        "Du ar en makroekonomisk strateg. Svara ENBART med JSON.",
        prompt,
        temperature=0.4,
        max_tokens=2000,
    )

    if not response:
        logger.warning("Scenario generation failed, using fallback")
        return _fallback_scenarios(regime)

    parsed = parse_llm_json(response)
    if not parsed or "scenarios" not in parsed:
        logger.warning("Could not parse scenario response")
        return _fallback_scenarios(regime)

    scenarios = []
    for s in parsed["scenarios"]:
        # Validate and clean
        returns = {}
        for asset in OMEGA_ASSETS:
            ret = s.get("asset_returns", {}).get(asset, 0)
            if isinstance(ret, (int, float)):
                returns[asset] = max(-0.50, min(0.50, ret))  # Cap at ±50%
            else:
                returns[asset] = 0.0

        prob = s.get("probability", 0.2)
        scenarios.append(Scenario(
            name=s.get("name", "Unknown"),
            probability=max(0.05, min(0.80, prob)),
            description=s.get("description", ""),
            asset_returns=returns,
        ))

    # Normalize probabilities to sum to 1.0
    total_prob = sum(s.probability for s in scenarios)
    if total_prob > 0:
        for s in scenarios:
            s.probability = round(s.probability / total_prob, 3)

    logger.info(f"Generated {len(scenarios)} scenarios via {provider}")
    return scenarios


def _fallback_scenarios(regime: str) -> List[Scenario]:
    """Rule-based fallback scenarios (no AI needed)."""
    if regime == "RISK_OFF":
        return [
            Scenario("Mild recession", 0.45, "Ekonomin saktar in men ingen kris.",
                     {"sp500": -0.08, "gold": 0.12, "us10y": -0.02, "oil": -0.15,
                      "btc": -0.15, "global-equity": -0.10, "eurusd": 0.03, "silver": 0.08,
                      "sector-tech": -0.12, "sector-energy": -0.18, "sector-finance": -0.10,
                      "sector-health": -0.03, "region-em": -0.12, "region-europe": -0.08}),
            Scenario("Deep recession", 0.25, "Kraftig nedgang, kreditstress.",
                     {"sp500": -0.25, "gold": 0.20, "us10y": -0.05, "oil": -0.30,
                      "btc": -0.35, "global-equity": -0.22, "eurusd": 0.05, "silver": 0.10,
                      "sector-tech": -0.30, "sector-energy": -0.28, "sector-finance": -0.25,
                      "sector-health": -0.10, "region-em": -0.25, "region-europe": -0.20}),
            Scenario("Recovery surprise", 0.30, "Centralbanker reagerar snabbt, marknaden aterhamtar.",
                     {"sp500": 0.10, "gold": 0.02, "us10y": 0.01, "oil": 0.08,
                      "btc": 0.15, "global-equity": 0.08, "eurusd": -0.02, "silver": 0.03,
                      "sector-tech": 0.12, "sector-energy": 0.10, "sector-finance": 0.08,
                      "sector-health": 0.05, "region-em": 0.10, "region-europe": 0.08}),
        ]
    elif regime == "RISK_ON":
        return [
            Scenario("Bull continuation", 0.45, "Stark tillvaxt, AI-rally fortsatter.",
                     {"sp500": 0.12, "gold": -0.03, "us10y": 0.02, "oil": 0.05,
                      "btc": 0.25, "global-equity": 0.10, "eurusd": -0.02, "silver": -0.02,
                      "sector-tech": 0.18, "sector-energy": 0.05, "sector-finance": 0.08,
                      "sector-health": 0.06, "region-em": 0.08, "region-europe": 0.06}),
            Scenario("Correction", 0.30, "Marknardsaterhamsning efter snabb uppgang.",
                     {"sp500": -0.08, "gold": 0.06, "us10y": -0.01, "oil": -0.05,
                      "btc": -0.12, "global-equity": -0.06, "eurusd": 0.02, "silver": 0.04,
                      "sector-tech": -0.12, "sector-energy": -0.06, "sector-finance": -0.05,
                      "sector-health": 0.02, "region-em": -0.08, "region-europe": -0.04}),
            Scenario("Inflation scare", 0.25, "Inflation atervanser, Fed hojhar ovantart.",
                     {"sp500": -0.15, "gold": 0.15, "us10y": 0.04, "oil": 0.10,
                      "btc": -0.20, "global-equity": -0.12, "eurusd": -0.04, "silver": 0.10,
                      "sector-tech": -0.20, "sector-energy": 0.12, "sector-finance": -0.08,
                      "sector-health": -0.05, "region-em": -0.15, "region-europe": -0.10}),
        ]
    else:  # NEUTRAL
        return [
            Scenario("Soft landing", 0.40, "Fed lyckas, mild tillvaxt.",
                     {"sp500": 0.06, "gold": 0.03, "us10y": 0.00, "oil": 0.02,
                      "btc": 0.10, "global-equity": 0.05, "eurusd": 0.01, "silver": 0.02,
                      "sector-tech": 0.08, "sector-energy": 0.03, "sector-finance": 0.05,
                      "sector-health": 0.04, "region-em": 0.06, "region-europe": 0.04}),
            Scenario("Stagflation", 0.30, "Lag tillvaxt + hog inflation.",
                     {"sp500": -0.05, "gold": 0.12, "us10y": 0.03, "oil": 0.08,
                      "btc": -0.08, "global-equity": -0.04, "eurusd": -0.03, "silver": 0.10,
                      "sector-tech": -0.08, "sector-energy": 0.10, "sector-finance": -0.06,
                      "sector-health": 0.02, "region-em": -0.06, "region-europe": -0.05}),
            Scenario("Recession", 0.30, "Arbetsmarknad sviktar, Fed sanker for sent.",
                     {"sp500": -0.18, "gold": 0.15, "us10y": -0.03, "oil": -0.20,
                      "btc": -0.25, "global-equity": -0.15, "eurusd": 0.04, "silver": 0.08,
                      "sector-tech": -0.22, "sector-energy": -0.15, "sector-finance": -0.18,
                      "sector-health": -0.05, "region-em": -0.18, "region-europe": -0.12}),
        ]


# ============================================================
# MINIMUM-REGRET OPTIMIZER (ren matematik, ingen AI)
# ============================================================

def optimize_minimum_regret(scenarios: List[Scenario]) -> Dict[str, float]:
    """
    Find portfolio weights that minimize the worst-case scenario loss.
    (Maximum of the minimum expected returns across all scenarios.)
    """
    assets = OMEGA_ASSETS
    n = len(assets)

    # Build scenario return matrix: (n_scenarios, n_assets)
    n_scenarios = len(scenarios)
    returns_matrix = np.zeros((n_scenarios, n))
    probs = np.array([s.probability for s in scenarios])

    for i, scenario in enumerate(scenarios):
        for j, asset in enumerate(assets):
            returns_matrix[i, j] = scenario.asset_returns.get(asset, 0)

    # Objective: maximize the minimum scenario return
    # (equivalently: minimize the negative of the minimum scenario return)
    def neg_min_return(weights):
        scenario_returns = returns_matrix @ weights  # (n_scenarios,)
        weighted_returns = scenario_returns * probs   # probability-weighted
        # Minimum regret: worst probability-weighted scenario
        return -np.min(scenario_returns)

    # Constraints
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # sum = 1
    ]
    bounds = [(0.02, 0.30)] * n  # 2% min, 30% max per asset

    best_result = None
    best_val = float("inf")

    for _ in range(10):
        w0 = np.random.dirichlet(np.ones(n))
        try:
            result = minimize(
                neg_min_return, w0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000},
            )
            if result.success and result.fun < best_val:
                best_val = result.fun
                best_result = result
        except Exception:
            continue

    if best_result is None:
        # Fallback: equal weight
        weights = np.ones(n) / n
    else:
        weights = best_result.x

    # Normalize
    weights = weights / weights.sum()

    return {assets[i]: round(float(weights[i]), 4) for i in range(n)}


# ============================================================
# MONTE CARLO CVaR (ren matematik, ingen AI)
# ============================================================

def monte_carlo_cvar(
    weights: Dict[str, float],
    scenarios: List[Scenario],
    n_simulations: int = 1000,
    alpha: float = 0.05,
) -> Dict:
    """
    Run Monte Carlo simulation to estimate CVaR.
    Samples from each scenario with probability weighting + noise.
    """
    assets = list(weights.keys())
    n = len(assets)
    w = np.array([weights.get(a, 0) for a in assets])

    # Build scenario data
    n_scenarios = len(scenarios)
    scenario_returns = np.zeros((n_scenarios, n))
    probs = np.array([s.probability for s in scenarios])
    for i, s in enumerate(scenarios):
        for j, a in enumerate(assets):
            scenario_returns[i, j] = s.asset_returns.get(a, 0)

    # Volatilities for noise
    vols = np.array([HIST_VOL.get(a, 0.20) for a in assets])

    # Sample scenarios by probability, add noise
    portfolio_returns = np.zeros(n_simulations)
    rng = np.random.default_rng(42)

    for sim in range(n_simulations):
        # Pick a scenario by probability
        idx = rng.choice(n_scenarios, p=probs)
        base_returns = scenario_returns[idx]

        # Add noise (normal, scaled by historical vol / sqrt(2) for 6-month horizon)
        noise = rng.normal(0, vols * 0.5, n)
        sim_returns = base_returns + noise

        # Portfolio return
        portfolio_returns[sim] = np.dot(w, sim_returns)

    # Sort and compute stats
    sorted_returns = np.sort(portfolio_returns)
    cutoff = int(np.floor(alpha * n_simulations))
    if cutoff < 1:
        cutoff = 1

    cvar = -np.mean(sorted_returns[:cutoff])
    var_alpha = -sorted_returns[cutoff]
    expected = np.mean(portfolio_returns)
    median = np.median(portfolio_returns)
    vol = np.std(portfolio_returns)

    return {
        "cvar_5pct": round(float(cvar), 4),
        "var_5pct": round(float(var_alpha), 4),
        "expected_return": round(float(expected), 4),
        "median_return": round(float(median), 4),
        "volatility": round(float(vol), 4),
        "best_case": round(float(sorted_returns[-1]), 4),
        "worst_case": round(float(sorted_returns[0]), 4),
        "n_simulations": n_simulations,
    }


# ============================================================
# SCENARIO ENGINE (ORCHESTRATOR)
# ============================================================

class ScenarioEngine:
    """Orchestrates weekly scenario generation and Omega portfolio."""

    def __init__(self):
        self.scenarios: List[Scenario] = []
        self.omega: Optional[OmegaPortfolio] = None
        self.last_generation: Optional[str] = None
        self._load()

    def _load(self):
        """Load from KV store or file."""
        data = None
        try:
            from db import kv_get
            data = kv_get("scenario_engine")
        except Exception:
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass

        if data and isinstance(data, dict):
            self.last_generation = data.get("last_generation")
            # Restore scenarios
            for s in data.get("scenarios", []):
                self.scenarios.append(Scenario(**s))
            # Restore omega
            omega_data = data.get("omega")
            if omega_data:
                # Remove scenarios from omega_data (stored separately)
                omega_data.pop("scenarios", None)
                self.omega = OmegaPortfolio(**omega_data)
                self.omega.scenarios = self.scenarios

    def _save(self):
        """Save to KV store or file."""
        data = {
            "last_generation": self.last_generation,
            "scenarios": [asdict(s) for s in self.scenarios],
            "omega": {
                "weights": self.omega.weights if self.omega else {},
                "expected_return": self.omega.expected_return if self.omega else 0,
                "worst_case_return": self.omega.worst_case_return if self.omega else 0,
                "cvar_5pct": self.omega.cvar_5pct if self.omega else 0,
                "sharpe_estimate": self.omega.sharpe_estimate if self.omega else 0,
                "generated_at": self.omega.generated_at if self.omega else "",
                "generation_method": self.omega.generation_method if self.omega else "",
            } if self.omega else None,
        }
        try:
            from db import kv_set
            kv_set("scenario_engine", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, default=str)

    async def refresh_scenarios(
        self,
        regime: str = "NEUTRAL",
        political_risk: str = "NORMAL",
        market_data: dict = None,
        force: bool = False,
    ) -> OmegaPortfolio:
        """Generate new scenarios and optimize Omega portfolio."""
        # Check if refresh needed (weekly)
        if not force and self.last_generation:
            try:
                last = datetime.fromisoformat(self.last_generation)
                age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                if age_hours < 7 * 24 and self.omega:  # 7 days
                    logger.info(f"Scenarios still fresh ({age_hours:.0f}h old)")
                    return self.omega
            except Exception:
                pass

        # Step 1: Generate scenarios
        logger.info("Generating new market scenarios...")
        self.scenarios = await generate_scenarios(regime, political_risk, market_data)

        if not self.scenarios:
            logger.warning("No scenarios generated, using fallback")
            self.scenarios = _fallback_scenarios(regime)

        # Step 2: Minimum-regret optimization
        weights = optimize_minimum_regret(self.scenarios)

        # Step 3: Monte Carlo CVaR
        mc_results = monte_carlo_cvar(weights, self.scenarios)

        # Step 4: Build Omega portfolio
        expected = sum(
            s.probability * sum(
                weights.get(a, 0) * s.asset_returns.get(a, 0)
                for a in weights
            )
            for s in self.scenarios
        )

        worst = min(
            sum(weights.get(a, 0) * s.asset_returns.get(a, 0) for a in weights)
            for s in self.scenarios
        )

        sharpe = expected / mc_results["volatility"] if mc_results["volatility"] > 0 else 0

        self.omega = OmegaPortfolio(
            weights=weights,
            scenarios=self.scenarios,
            expected_return=round(expected, 4),
            worst_case_return=round(worst, 4),
            cvar_5pct=mc_results["cvar_5pct"],
            sharpe_estimate=round(sharpe, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
            generation_method="gemini" if len(self.scenarios) > 0 else "fallback",
        )

        self.last_generation = datetime.now(timezone.utc).isoformat()
        self._save()

        logger.info(
            f"Omega portfolio generated: {len(self.scenarios)} scenarios, "
            f"E(R)={expected:.1%}, worst={worst:.1%}, CVaR={mc_results['cvar_5pct']:.1%}"
        )

        return self.omega

    def get_current_portfolio(self) -> Optional[Dict]:
        """Return current Omega portfolio for pipeline integration."""
        if not self.omega:
            return None
        return {
            "weights": self.omega.weights,
            "expected_return": self.omega.expected_return,
            "worst_case_return": self.omega.worst_case_return,
            "cvar_5pct": self.omega.cvar_5pct,
            "sharpe_estimate": self.omega.sharpe_estimate,
            "generated_at": self.omega.generated_at,
            "n_scenarios": len(self.scenarios),
        }

    def get_scenarios(self) -> List[Dict]:
        """Return current scenarios for API."""
        return [asdict(s) for s in self.scenarios]

    def get_dashboard(self) -> Dict:
        """Full dashboard data for /api/portfolio/dual."""
        return {
            "omega_portfolio": self.get_current_portfolio(),
            "scenarios": self.get_scenarios(),
            "last_generation": self.last_generation,
            "n_scenarios": len(self.scenarios),
        }


# Singleton
scenario_engine = ScenarioEngine()
