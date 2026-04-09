"""
Asset Scenario Generator — Layered Architecture
================================================
Generates forward-looking bull/base/bear scenarios per asset.

CONTRACT (ScenarioResult) is frozen across all levels:
  Level 1 (this file) — Gemini narratives + formula-based prices
  Level 2 (future)    — Monte Carlo prices, inherits narratives
  Level 3 (future)    — Bayesian probability adjustment, inherits rest

Frontend NEVER needs to change after Level 1 is deployed.
"""

import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("aether.scenarios")

# ── Historical volatility estimates (annualised %) ──
# Used to calculate price path spread. Refreshed at Level 2 via yfinance.
_HIST_VOL: Dict[str, float] = {
    "btc": 0.65,   "gold": 0.14,   "silver": 0.28, "oil": 0.38,
    "sp500": 0.17, "global-equity": 0.18, "eurusd": 0.07, "us10y": 0.09,
    "sector-tech": 0.25, "sector-energy": 0.30, "sector-finance": 0.22,
    "sector-health": 0.17, "region-em": 0.22, "region-europe": 0.19,
}

# ── Historical max-drawdown estimates (fraction, 2-year window) ──
_HIST_MAX_DD: Dict[str, float] = {
    "btc": -0.78, "gold": -0.18, "silver": -0.48, "oil": -0.55,
    "sp500": -0.34, "global-equity": -0.30, "eurusd": -0.14, "us10y": -0.22,
    "sector-tech": -0.38, "sector-energy": -0.42, "sector-finance": -0.35,
    "sector-health": -0.28, "region-em": -0.32, "region-europe": -0.28,
}

# ── Bull/bear price multipliers per month (relative to vol) ──
BULL_MULT  = [0.4, 0.8, 1.3, 1.8, 2.2, 2.7]   # months 1-6
BASE_MULT  = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
BEAR_MULT  = [-0.5, -1.0, -1.5, -2.0, -2.4, -2.8]

MONTH_LABELS = ["Mån 1", "Mån 2", "Mån 3", "Mån 4", "Mån 5", "Mån 6"]


# ── Frozen contract, shared by all levels ───────────────────────
@dataclass
class ScenarioResult:
    """The single contract all generator levels must satisfy."""

    # Price paths (6 monthly data points)
    price_paths: Dict[str, List[float]]     # keys: "bull", "base", "bear"

    # Probabilities summing to ~100
    probabilities: Dict[str, int]           # keys: "bull", "base", "bear"

    # Narrative text per scenario
    narratives: Dict[str, str]              # keys: "bull", "base", "bear"

    # Short bullet drivers
    drivers: Dict[str, List[str]]           # keys: "bull", "base", "bear"

    # Worst-case historical drawdown %
    worst_case_pct: float                   # e.g. -78.0 = -78%

    # Which level generated this
    level: str                              # "1", "2", or "3"

    # ★ Level 1.5: What must happen / what triggers worst case
    key_trigger: Optional[str] = None       # What must happen for bull scenario
    worst_case_catalyst: Optional[str] = None  # What triggers the worst case

    # When this was generated
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_frontend(self, asset_name: str) -> dict:
        """Serialize to exact format expected by frontend."""
        price_data = self.price_paths
        scenario_data = [
            {
                "name": MONTH_LABELS[i],
                "bull": round(price_data["bull"][i], 4),
                "base": round(price_data["base"][i], 4),
                "bear": round(price_data["bear"][i], 4),
            }
            for i in range(6)
        ]
        return {
            "scenarioData": scenario_data,
            "scenarioProbabilities": self.probabilities,
            "scenarioNarratives": self.narratives,
            "scenarioDrivers": self.drivers,
            "scenarioWorstCasePct": self.worst_case_pct,
            "scenarioLevel": self.level,
            "scenarioGeneratedAt": self.generated_at,
            "scenarioKeyTrigger": self.key_trigger,
            "scenarioWorstCaseCatalyst": self.worst_case_catalyst,
        }


# ── Base class (abstract contract) ─────────────────────────────
class ScenarioGenerator:
    """Interface all generator levels must implement."""

    LEVEL = "base"

    async def generate(
        self,
        asset_id: str,
        asset_name: str,
        current_price: float,
        final_score: float,
        agent_scores: Dict[str, float],  # {macro, micro, sentiment, tech}
        regime: str,
        vix: float,
        news_headlines: List[str],
        supervisor_text: str = "",
    ) -> ScenarioResult:
        raise NotImplementedError


# ── Level 1: Gemini narratives + formula prices ─────────────────
class Level1Generator(ScenarioGenerator):
    """
    Level 1 — production-ready in 1 day.

    Probabilities: derived from final_score + VIX + regime.
    Price paths:   current_price × (1 ± annualised_vol × multiplier × √months).
    Narratives:    1 Gemini Flash call per asset.
    Worst case:    static historical max-drawdown lookup.
    """

    LEVEL = "1"

    # ── Public entry point ──────────────────────────────────────
    async def generate(
        self,
        asset_id: str,
        asset_name: str,
        current_price: float,
        final_score: float,
        agent_scores: Dict[str, float],
        regime: str,
        vix: float,
        news_headlines: List[str],
        supervisor_text: str = "",
        llm_narratives: bool = True,   # False = skip LLM, use rule-based text (cheaper)
    ) -> ScenarioResult:

        try:
            probs    = self._calculate_probabilities(final_score, vix, regime)
            paths    = self._calculate_price_paths(asset_id, current_price, final_score)
            wc       = self._calculate_worst_case(asset_id, current_price)
            if llm_narratives:
                narratives, drivers, key_trigger, worst_catalyst = await self._generate_narratives(
                    asset_id, asset_name, current_price, final_score,
                    agent_scores, regime, vix, probs, paths, news_headlines, supervisor_text
                )
            else:
                # Rule-based text — no LLM call, zero cost
                def fmt(p): return f"{p:,.2f}" if p > 100 else f"{p:.4f}"
                bt = fmt(paths["bull"][-1]); bst = fmt(paths["base"][-1]); brt = fmt(paths["bear"][-1])
                narratives = {
                    "bull": f"I ett positivt scenario kan {asset_name} nå {bt} om 6 månader.",
                    "base": f"Mest troligt rör sig {asset_name} mot {bst} med mixade signaler.",
                    "bear": f"I ett negativt scenario kan {asset_name} falla till {brt}.",
                }
                drivers = {
                    "bull": ["Positiv riskaptit", "Tekniska signaler"],
                    "base": ["Sidorörelse", "Blandade signaler"],
                    "bear": ["Risk-off", "Minskad riskaptit"],
                }
                key_trigger = None
                worst_catalyst = None
            return ScenarioResult(
                price_paths=paths,
                probabilities=probs,
                narratives=narratives,
                drivers=drivers,
                worst_case_pct=wc,
                level=self.LEVEL,
                key_trigger=key_trigger,
                worst_case_catalyst=worst_catalyst,
            )

        except Exception as e:
            logger.warning(f"ScenarioGenerator failed for {asset_id}: {e}")
            return self._fallback(asset_id, current_price, final_score)

    # ── Step 1: Probabilities ───────────────────────────────────
    def _calculate_probabilities(
        self, score: float, vix: float, regime: str
    ) -> Dict[str, int]:
        """
        Bull probability anchored to final_score, adjusted for VIX and regime.
        score  +10 → ~70% bull   score  0 → ~35% bull   score -10 → ~10% bull
        VIX > 25 cuts bull by 5-10 pp;  Risk-Off cuts by another 5 pp.
        """
        # Base from score (linear, clipped)
        base_bull = int(35 + score * 3.5)      # range: ~0–70 for score ±10
        base_bull = max(5, min(75, base_bull))

        # VIX penalty
        if vix >= 30:
            base_bull -= 12
        elif vix >= 25:
            base_bull -= 7
        elif vix >= 20:
            base_bull -= 3

        # Regime adjustment
        if regime in ("risk-off", "RISK_OFF", "crisis"):
            base_bull -= 8
        elif regime in ("risk-on", "RISK_ON"):
            base_bull += 5

        base_bull = max(5, min(75, base_bull))

        # Distribute remaining between base and bear
        remaining = 100 - base_bull
        bear = max(5, min(50, remaining // 3))   # bear is 1/3 of non-bull
        base = 100 - base_bull - bear

        return {"bull": base_bull, "base": base, "bear": bear}

    # ── Step 2: Price paths ─────────────────────────────────────
    def _calculate_price_paths(
        self, asset_id: str, price: float, score: float
    ) -> Dict[str, List[float]]:
        """
        Monthly price projections over 6 months.
        Uses annualised volatility scaled to monthly horizon:
            monthly_vol = annual_vol / sqrt(12)  × sqrt(month_number)
        Bull/Base/Bear use different multipliers on that vol.
        """
        if price <= 0:
            p = 1.0
        else:
            p = price

        annual_vol = _HIST_VOL.get(asset_id, 0.20)
        monthly_base_vol = annual_vol / (12 ** 0.5)  # one-month vol

        # Score modulates the base path direction (+/- 10%)
        base_drift = score * 0.008   # score=5 → +4% over 6 months

        bull_path, base_path, bear_path = [], [], []
        for i, month in enumerate(range(1, 7)):
            t_vol = monthly_base_vol * (month ** 0.5)
            bull_path.append(round(p * (1 + t_vol * BULL_MULT[i] + base_drift), 4))
            base_path.append(round(p * (1 + t_vol * BASE_MULT[i] + base_drift * 0.5), 4))
            # Floor: bear price can never go below 5% of current price
            bear_raw = p * (1 + t_vol * BEAR_MULT[i])
            bear_path.append(round(max(bear_raw, p * 0.05), 4))

        return {"bull": bull_path, "base": base_path, "bear": bear_path}

    # ── Step 3: Worst case ──────────────────────────────────────
    def _calculate_worst_case(self, asset_id: str, price: float) -> float:
        """Return historical max-drawdown as a percentage (e.g. -78.0)."""
        dd_fraction = _HIST_MAX_DD.get(asset_id, -0.35)
        return round(dd_fraction * 100, 1)

    # ── Step 4: Narratives via Gemini ───────────────────────────
    async def _generate_narratives(
        self,
        asset_id: str,
        asset_name: str,
        price: float,
        score: float,
        agent_scores: Dict[str, float],
        regime: str,
        vix: float,
        probs: Dict[str, int],
        paths: Dict[str, List[float]],
        headlines: List[str],
        supervisor_text: str,
    ):
        """Generate narrative text for all three scenarios in one LLM call."""

        # Format price targets
        def fmt(p): return f"{p:,.2f}" if p > 100 else f"{p:.4f}"

        bull_target = fmt(paths["bull"][-1])
        base_target = fmt(paths["base"][-1])
        bear_target = fmt(paths["bear"][-1])

        agent_summary = ", ".join(
            f"{k}: {v:+.1f}" for k, v in agent_scores.items() if v != 0
        )

        top_news = "\n".join(f"- {h}" for h in headlines[:5]) if headlines else "(inga nyheter)"

        prompt = f"""Du är en senior marknadsanalytiker som förklarar tre scenarier för {asset_name} 
till en vardagsinvesterare på enkel svenska.

NULÄGE:
- Pris: {fmt(price)}
- AI-score: {score:+.1f}/10 (agenter: {agent_summary})
- Marknadsregim: {regime}
- VIX (rädsloindex): {vix:.1f}
- Senaste nyheter:
{top_news}

BERÄKNADE PRISNIVÅER (6 månader):
- Bull-scenario ({probs['bull']}% sannolikhet): {bull_target}
- Bas-scenario ({probs['base']}% sannolikhet): {base_target}  
- Bear-scenario ({probs['bear']}% sannolikhet): {bear_target}

Svara med ENBART JSON:
{{
  "bull": {{
    "narrative": "En mening vad som händer och varför - enkel svenska",
    "drivers": ["Drivare 1", "Drivare 2", "Drivare 3"]
  }},
  "base": {{
    "narrative": "...",
    "drivers": ["...", "...", "..."]
  }},
  "bear": {{
    "narrative": "...",
    "drivers": ["...", "...", "..."]
  }},
  "key_trigger": "En mening: Vad som MÅSTE hända för att bull-scenariot ska utlösas",
  "worst_case_catalyst": "En mening: Vad som konkret utlöser det värsta scenariot"
}}

REGLER:
- Enkel svenska, inga finans-klichéer
- Narrativen ska referera till FAKTISKA drivare (VIX, regim, nyheter)
- key_trigger: konkret händelse/nivå (ex: 'Fed annonserar räntehöjning', 'BTC faller under 55k')
- worst_case_catalyst: konkret utlösare (ex: 'OPEC ökar produktion 2M fat/dag', 'recession bekräftas')
- Max 2 meningar per narrativ, var KONKRET"""

        narratives = {
            "bull": f"Om marknaden vänder uppåt kan {asset_name} nå {bull_target} om 6 månader.",
            "base": f"Mest troligt fortsätter {asset_name} runt nuvarande nivåer med viss rörlighet.",
            "bear": f"I ett negativt scenario kan {asset_name} falla mot {bear_target}.",
        }
        drivers = {
            "bull": ["Positiv riskaptit", "Starka signaler"],
            "base": ["Sidorörelse", "Blandade signaler"],
            "bear": ["Risk-off", "Negativa signaler"],
        }

        try:
            from llm_provider import call_llm_tiered, parse_llm_json
            resp, provider = await call_llm_tiered(
                tier=0,   # 2.0-flash sufficient — simple JSON narrative generation
                system_prompt="Du är en marknadsanalytiker. Svara ENBART med JSON.",
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=800,   # Slightly higher to accommodate new fields
            )
            parsed = parse_llm_json(resp)
            if parsed:
                for scenario in ("bull", "base", "bear"):
                    s = parsed.get(scenario, {})
                    if s.get("narrative"):
                        narratives[scenario] = s["narrative"]
                    if s.get("drivers"):
                        drivers[scenario] = s["drivers"][:3]
                # Extract new Level 1.5 fields
                key_trigger = parsed.get("key_trigger")
                worst_catalyst = parsed.get("worst_case_catalyst")
                logger.info(f"  📖 Scenarios for {asset_name} generated via {provider}")
                return narratives, drivers, key_trigger, worst_catalyst
        except Exception as e:
            logger.warning(f"  ⚠️ Scenario narrative failed for {asset_id}: {e}")

        return narratives, drivers, None, None

    # ── Fallback (no LLM / bad price) ──────────────────────────
    def _fallback(
        self, asset_id: str, price: float, score: float
    ) -> ScenarioResult:
        p = max(price, 1.0)
        paths = self._calculate_price_paths(asset_id, p, score)
        probs = self._calculate_probabilities(score, 20.0, "neutral")
        wc = self._calculate_worst_case(asset_id, p)
        return ScenarioResult(
            price_paths=paths,
            probabilities=probs,
            narratives={
                "bull": "Positiv marknad driver tillgången uppåt.",
                "base": "Marknaden rör sig sidledes i nuläget.",
                "bear": "Negativt marknadsklimat pressar ned tillgången.",
            },
            drivers={
                "bull": ["Positiv riskaptit"], "base": ["Sidorörelse"], "bear": ["Risk-off"],
            },
            worst_case_pct=wc,
            level=self.LEVEL,
        )


# ── Singleton ────────────────────────────────────────────────────
level1_generator = Level1Generator()
