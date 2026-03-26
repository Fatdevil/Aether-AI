"""
AI Analysis Engine - Orchestrates the multi-agent system.
Uses LLM agents when API keys are available, falls back to rule-based otherwise.
"""

import logging
import asyncio
from typing import Optional

from agents.macro_agent import MacroAgent
from agents.micro_agent import MicroAgent
from agents.sentiment_agent import SentimentAgent
from agents.technical_agent import TechnicalAgent
from agents.supervisor_agent import SupervisorAgent
from llm_provider import get_available_providers
from adaptive_prompts import get_performance_context, get_supervisor_context, get_dynamic_weights
from economic_calendar import calendar
from correlation_engine import correlation_engine
from regime_detector import regime_detector
from trade_signals import signal_generator
from onchain_data import fetch_onchain_data, format_onchain_for_prompt, get_cached_onchain
from meta_supervisor import should_get_second_opinion, aggregate_results, get_ensemble_status
from supervisor_context import SupervisorContextBuilder
from analysis_store import store as analysis_store

logger = logging.getLogger("aether.ai")

# Initialize agents (singleton instances)
macro_agent = MacroAgent()
micro_agent = MicroAgent()
sentiment_agent = SentimentAgent()
tech_agent = TechnicalAgent()
supervisor_agent = SupervisorAgent()

# Smart routing thresholds
SIGNAL_THRESHOLD = 3.0  # Minimum signal score to trigger LLM supervisor


def _quick_signal_score(price_data: dict) -> float:
    """Quick pre-screening: calculate signal strength from price data alone.
    Returns 0-10 score. High score = asset is worth deep analysis."""
    indicators = price_data.get("indicators", {})
    score = 0.0

    # Price momentum signal
    change_pct = abs(price_data.get("change_pct", 0))
    if change_pct > 3.0:
        score += 4.0  # Big move = very interesting
    elif change_pct > 1.5:
        score += 2.5
    elif change_pct > 0.5:
        score += 1.0

    # RSI extremes (oversold/overbought = interesting)
    rsi = indicators.get("rsi_14", 50)
    if rsi < 25 or rsi > 75:
        score += 3.0  # Extreme RSI
    elif rsi < 35 or rsi > 65:
        score += 1.5

    # MACD crossover signal
    macd = indicators.get("macd", 0)
    macd_signal = indicators.get("macd_signal", 0)
    if macd and macd_signal:
        macd_diff = abs(macd - macd_signal)
        if macd_diff > 0.5:
            score += 2.0

    # Bollinger band touch
    bb_pos = indicators.get("bb_position")
    if bb_pos is not None and (bb_pos < 0.05 or bb_pos > 0.95):
        score += 2.0

    return min(10.0, score)


async def analyze_asset(asset_id: str, price_data: dict, news_items: list, category: str) -> dict:
    """
    Run multi-agent analysis on an asset.
    Each agent runs in parallel, then supervisor evaluates all results.
    Adaptive prompts inject historical performance feedback.
    Intelligence modules inject calendar, correlation, and regime context.
    """
    asset_name_map = {
        "btc": "Bitcoin", "global-equity": "Globala Aktier (ACWI)", "sp500": "S&P 500",
        "gold": "Guld (XAU)", "silver": "Silver (XAG)", "eurusd": "EUR/USD",
        "oil": "Råolja (Brent)", "us10y": "US 10Y Räntor",
    }
    asset_name = asset_name_map.get(asset_id, asset_id)

    # Get adaptive performance context for each agent
    try:
        perf_contexts = {
            "macro": get_performance_context("macro", asset_id),
            "micro": get_performance_context("micro", asset_id),
            "sentiment": get_performance_context("sentiment", asset_id),
            "tech": get_performance_context("tech", asset_id),
        }
        supervisor_ctx = get_supervisor_context()
    except Exception:
        perf_contexts = {k: "" for k in ["macro", "micro", "sentiment", "tech"]}
        supervisor_ctx = ""

    # === INTELLIGENCE CONTEXT ===
    try:
        # Economic calendar: upcoming events for this asset
        calendar_ctx = calendar.get_context_for_asset(asset_id)

        # Cross-asset correlations
        corr_ctx = correlation_engine.get_context_for_asset(asset_id)

        # Market regime: specific guidance per agent type
        regime = regime_detector.detect_regime()
        regime_contexts = {}
        for agent_name in ["macro", "micro", "sentiment", "tech"]:
            regime_contexts[agent_name] = regime_detector.get_context_for_agent(agent_name)

        # Check if confidence should be reduced due to imminent events
        should_reduce, conf_multiplier = calendar.should_reduce_confidence(asset_id)
    except Exception as e:
        logger.warning(f"Intelligence context failed: {e}")
        calendar_ctx = ""
        corr_ctx = ""
        regime_contexts = {k: "" for k in ["macro", "micro", "sentiment", "tech"]}
        should_reduce, conf_multiplier = False, 1.0

    # Fetch on-chain data for BTC
    onchain_ctx = ""
    if asset_id == "btc":
        try:
            onchain = await fetch_onchain_data()
            onchain_ctx = format_onchain_for_prompt(onchain)
        except Exception:
            onchain_ctx = ""

    # Build full context per agent (perf + calendar + correlation + regime + onchain + domain knowledge)
    try:
        from domain_knowledge import DomainKnowledgeManager
        # Use the global domain_mgr from main.py if available, otherwise create local
        import sys
        main_mod = sys.modules.get("main") or sys.modules.get("__main__")
        domain_ctx = ""
        if main_mod and hasattr(main_mod, "domain_mgr"):
            domain_ctx = main_mod.domain_mgr.build_agent_context()
    except Exception:
        domain_ctx = ""

    # FIX 2B: Build accuracy context per agent (inject historical performance)
    accuracy_ctx = ""
    try:
        acc_parts = ["HISTORISK PRICKSÄKERHET (de senaste 30 dagarna):"]
        for agent_name_key in ["macro", "micro", "sentiment", "tech"]:
            acc_data = analysis_store.get_agent_accuracy(agent_name_key, "30d")
            if acc_data:
                a = acc_data[0] if isinstance(acc_data, list) else acc_data
                total = a.get("total_predictions", 0)
                if total > 5:
                    acc_pct = round(a.get("accuracy_direction", 0) * 100)
                    acc_parts.append(f"  {agent_name_key}: {acc_pct}% korrekt ({total} prediktioner)")
        if len(acc_parts) > 1:
            accuracy_ctx = "\n".join(acc_parts)
    except Exception:
        pass

    # FIX 2C: Build lead-lag context for per-agent injection
    lead_lag_ctx = ""
    try:
        from predictive.lead_lag import LeadLagDetector
        ll = LeadLagDetector()
        # Get returns_df if available
        returns_df = None
        try:
            from data_service import data_service
            returns_df = data_service.get_historical_returns() if data_service else None
        except Exception:
            pass
        if returns_df is not None:
            signals = ll.get_actionable_signals(returns_df)
            relevant = [s for s in signals if s.get("follower", "").lower() == asset_id.lower() or
                        s.get("leader", "").lower() == asset_id.lower()]
            if relevant:
                ll_parts = ["LEAD-LAG SIGNALER (cross-asset prediktion):"]
                for sig in relevant[:3]:
                    ll_parts.append(
                        f"  {sig['leader']} → {sig['follower']}: "
                        f"{sig.get('action', '?')} (styrka: {sig.get('confidence', 0):.0%}, "
                        f"lag: {sig.get('lag_days', '?')} dagar)"
                    )
                lead_lag_ctx = "\n".join(ll_parts)
    except Exception:
        pass

    def build_context(agent_name: str) -> str:
        parts = [
            perf_contexts.get(agent_name, ""),
            calendar_ctx,
            corr_ctx,
            regime_contexts.get(agent_name, ""),
            accuracy_ctx,    # FIX 2B: Agent accuracy history
            lead_lag_ctx,    # FIX 2C: Lead-lag cross-asset signals
        ]
        # On-chain data only for micro/tech agents (most relevant)
        if onchain_ctx and agent_name in ("micro", "tech"):
            parts.append(onchain_ctx)
        # Domain knowledge from user
        if domain_ctx:
            parts.append(domain_ctx)
        return "\n".join(p for p in parts if p)

    # Run agents (sentiment first since it's rule-based/instant)
    sentiment_result = await sentiment_agent.analyze(asset_id, asset_name, category, price_data, news_items, build_context("sentiment"))
    macro_result = await macro_agent.analyze(asset_id, asset_name, category, price_data, news_items, build_context("macro"))
    micro_result = await micro_agent.analyze(asset_id, asset_name, category, price_data, news_items, build_context("micro"))
    tech_result = await tech_agent.analyze(asset_id, asset_name, category, price_data, news_items, build_context("tech"))

    # Handle any exceptions
    if isinstance(macro_result, Exception):
        logger.error(f"Macro agent failed for {asset_id}: {macro_result}")
        macro_result = {"score": 0, "confidence": 0, "reasoning": "Agent error", "key_factors": [], "provider_used": "error"}
    if isinstance(micro_result, Exception):
        logger.error(f"Micro agent failed for {asset_id}: {micro_result}")
        micro_result = {"score": 0, "confidence": 0, "reasoning": "Agent error", "key_factors": [], "provider_used": "error"}
    if isinstance(sentiment_result, Exception):
        logger.error(f"Sentiment agent failed for {asset_id}: {sentiment_result}")
        sentiment_result = {"score": 0, "confidence": 0, "reasoning": "Agent error", "key_factors": [], "provider_used": "error"}
    if isinstance(tech_result, Exception):
        logger.error(f"Tech agent failed for {asset_id}: {tech_result}")
        tech_result = {"score": 0, "confidence": 0, "reasoning": "Agent error", "key_factors": [], "provider_used": "error"}

    agent_results = {
        "macro": macro_result,
        "micro": micro_result,
        "sentiment": sentiment_result,
        "tech": tech_result,
    }

    # Build predict context for Supervisor V2
    try:
        context_builder = SupervisorContextBuilder(analysis_store=analysis_store)
        predict_ctx = context_builder.build_full_context(
            asset_id, asset_name, category, price_data, agent_results
        )
        predict_context_str = predict_ctx.get("formatted_prompt", "")
        logger.info(f"  📋 {asset_name}: Predict context built ({len(predict_context_str)} chars)")
    except Exception as e:
        logger.warning(f"Predict context failed for {asset_name}: {e}")
        predict_context_str = ""

    # Smart routing: check if asset warrants LLM supervisor
    signal_score = _quick_signal_score(price_data)
    use_llm_supervisor = signal_score >= SIGNAL_THRESHOLD

    if use_llm_supervisor:
        # Full LLM supervisor evaluation with predict context
        supervisor_result = await supervisor_agent.evaluate(
            asset_id, asset_name, category, price_data, agent_results,
            predict_context=predict_context_str,
        )
        logger.info(f"  🧠 {asset_name}: LLM supervisor V2 (signal: {signal_score:.1f})")
    else:
        # Rule-based supervisor with dynamic weights (saves API call)
        dyn_weights = get_dynamic_weights()
        supervisor_result = supervisor_agent._rule_based_evaluate(
            asset_id, asset_name, price_data, agent_results, weights_override=dyn_weights
        )
        logger.info(f"  ⚡ {asset_name}: Rule-based (signal: {signal_score:.1f}, below {SIGNAL_THRESHOLD})")

    final_score = supervisor_result["finalScore"]

    # Build primary result
    primary_result = {
        "finalScore": final_score,
        "supervisorText": supervisor_result["supervisorText"],
        "supervisorConfidence": supervisor_result.get("confidence", 0.5),
        "weights": supervisor_result.get("weights", {}),
        "recommendation": supervisor_result.get("recommendation", "Neutral"),
        "risk_flags": supervisor_result.get("risk_flags", []),
        "provider_used": supervisor_result.get("provider_used", "rule_based"),
    }

    # ===== ENSEMBLE: Check if second opinion needed =====
    news_impact = max((n.get("impact_score", 0) for n in news_items), default=0) if news_items else 0
    need_second, trigger_reason = should_get_second_opinion(
        asset_id, primary_result, agent_results, news_impact
    )

    second_result = None
    if need_second:
        try:
            # Run second supervisor with alternative provider
            from llm_provider import get_available_providers
            primary_provider = supervisor_result.get("provider_used", "gemini")
            available = get_available_providers()
            alt_providers = [p for p in available if p != primary_provider]

            if alt_providers:
                alt_provider = alt_providers[0]
                # Create temp supervisor with different provider
                alt_supervisor = SupervisorAgent()
                alt_supervisor.provider = alt_provider
                alt_result = await alt_supervisor.evaluate(
                    asset_id, asset_name, category, price_data, agent_results
                )
                second_result = {
                    "finalScore": alt_result["finalScore"],
                    "supervisorText": alt_result["supervisorText"],
                    "supervisorConfidence": alt_result.get("confidence", 0.5),
                    "provider_used": alt_provider,
                }
                logger.info(f"  🔀 {asset_name}: Second opinion from {alt_provider} ({trigger_reason})")
        except Exception as e:
            logger.warning(f"  ⚠️ Second opinion failed for {asset_name}: {e}")

    # Aggregate results (passthrough if no second opinion)
    primary_provider_name = supervisor_result.get("provider_used", "gemini")
    second_provider_name = second_result.get("provider_used", "anthropic") if second_result else None
    merged = aggregate_results(
        asset_id, primary_result, second_result,
        primary_provider_name, second_provider_name or "none"
    )

    final_score = merged.get("finalScore", final_score)
    risk_flags = merged.get("risk_flags", supervisor_result.get("risk_flags", []))
    supervisor_confidence = merged.get("supervisorConfidence", supervisor_result.get("confidence", 0.5))

    # ===== FIX 1D: Calendar confidence_multiplier =====
    # Reduce conviction before imminent high-impact events (FOMC, NFP, CPI)
    if should_reduce and conf_multiplier < 1.0:
        original_score = final_score
        final_score = final_score * conf_multiplier
        supervisor_confidence *= conf_multiplier
        risk_flags.append(f"⚠️ Score reducerat {original_score:+.1f}→{final_score:+.1f} pga kommande event (×{conf_multiplier:.2f})")
        logger.info(f"  📅 {asset_name}: Calendar reduction applied (×{conf_multiplier:.2f})")

    # ===== FIX 1B: Adversarial Agent (bias-kontroll) =====
    # Only challenge strong convictions (saves API calls on weak signals)
    adversarial_data = {}
    if abs(final_score) >= 5.0 and use_llm_supervisor:
        try:
            from predictive.adversarial_agent import AdversarialAgent
            from llm_provider import call_llm_tiered, parse_llm_json
            adversarial = AdversarialAgent()

            rec_for_challenge = {
                "asset": asset_name,
                "score": round(final_score, 1),
                "recommendation": merged.get("recommendation", supervisor_result.get("recommendation", "Neutral")),
                "confidence": round(supervisor_confidence, 2),
                "reasoning": supervisor_result.get("supervisorText", "")[:300],
                "agents": {k: round(v["score"], 1) for k, v in agent_results.items()},
            }

            challenge_prompt = adversarial.build_challenge_prompt(
                rec_for_challenge,
                market_context=predict_context_str[:500] if predict_context_str else "",
            )

            challenge_text, provider = await call_llm_tiered(
                tier=1,  # Use Flash for cost efficiency
                system_prompt="Du är en Devils Advocate-analytiker. Svara BARA med JSON.",
                user_prompt=challenge_prompt,
                temperature=0.4,
                max_tokens=800,
            )

            if challenge_text:
                challenge_json = parse_llm_json(challenge_text)
                if challenge_json:
                    challenge = adversarial.parse_challenge(challenge_json, rec_for_challenge)

                    # Apply conviction adjustment
                    conviction_ratio = challenge.adjusted_conviction / max(challenge.original_conviction, 0.01)
                    conviction_ratio = max(0.3, min(1.0, conviction_ratio))  # Clamp between 0.3x and 1.0x
                    original_score = final_score
                    final_score = final_score * conviction_ratio

                    # Add red flags to result
                    risk_flags.extend(challenge.red_flags)

                    adversarial_data = {
                        "active": True,
                        "conviction_ratio": round(conviction_ratio, 2),
                        "original_score": round(original_score, 1),
                        "adjusted_score": round(final_score, 1),
                        "should_proceed": challenge.should_proceed,
                        "weakest_assumption": challenge.weakest_assumption,
                        "counter_narrative": challenge.counter_narrative,
                        "challenges_count": len(challenge.challenges),
                        "red_flags": challenge.red_flags,
                        "provider": provider,
                    }
                    logger.info(f"  😈 {asset_name}: Adversarial {original_score:+.1f}→{final_score:+.1f} "
                                f"(×{conviction_ratio:.2f}, {'PROCEED' if challenge.should_proceed else 'BLOCKED'})")
        except Exception as e:
            logger.warning(f"  ⚠️ Adversarial failed for {asset_name}: {e}")

    # Determine trend
    if final_score >= 3:
        trend = "up"
    elif final_score <= -3:
        trend = "down"
    else:
        trend = "neutral"

    # Generate scenario projections
    scenarios = _generate_scenarios(asset_id, price_data.get("price", 0), final_score)

    return {
        "scores": {
            "macro": macro_result["score"],
            "micro": micro_result["score"],
            "sentiment": sentiment_result["score"],
            "tech": tech_result["score"],
        },
        "agentDetails": {
            "macro": {
                "reasoning": macro_result.get("reasoning", ""),
                "key_factors": macro_result.get("key_factors", []),
                "confidence": macro_result.get("confidence", 0),
                "provider": macro_result.get("provider_used", ""),
            },
            "micro": {
                "reasoning": micro_result.get("reasoning", ""),
                "key_factors": micro_result.get("key_factors", []),
                "confidence": micro_result.get("confidence", 0),
                "provider": micro_result.get("provider_used", ""),
            },
            "sentiment": {
                "reasoning": sentiment_result.get("reasoning", ""),
                "key_factors": sentiment_result.get("key_factors", []),
                "confidence": sentiment_result.get("confidence", 0),
                "provider": sentiment_result.get("provider_used", ""),
            },
            "tech": {
                "reasoning": tech_result.get("reasoning", ""),
                "key_factors": tech_result.get("key_factors", []),
                "confidence": tech_result.get("confidence", 0),
                "provider": tech_result.get("provider_used", ""),
            },
        },
        "finalScore": final_score,
        "trend": trend,
        "supervisorText": merged.get("supervisorText", supervisor_result["supervisorText"]),
        "supervisorConfidence": round(supervisor_confidence, 3),
        "supervisorWeights": supervisor_result.get("weights", {}),
        "riskFlags": risk_flags,
        "recommendation": merged.get("recommendation", supervisor_result.get("recommendation", "Neutral")),
        "scenarioData": scenarios["data"],
        "scenarioProbabilities": scenarios["probabilities"],
        "providersUsed": list(set(
            r.get("provider_used", "rule_based") for r in agent_results.values()
        )) + [supervisor_result.get("provider_used", "rule_based")],
        "ensemble": merged.get("ensemble", {"active": False, "reason": trigger_reason}),
        "adversarial": adversarial_data,
    }


def _generate_scenarios(asset_id: str, current_price: float, final_score: float) -> dict:
    """Generate 6-month scenario projections based on analysis."""
    if current_price <= 0:
        current_price = 1

    monthly_drift_base = final_score * 0.8
    monthly_drift_bull = monthly_drift_base + 4.0
    monthly_drift_bear = monthly_drift_base - 4.0

    data = []
    bull_price = current_price
    base_price = current_price
    bear_price = current_price

    for month in range(1, 7):
        bull_price *= (1 + monthly_drift_bull / 100)
        base_price *= (1 + monthly_drift_base / 100)
        bear_price *= (1 + monthly_drift_bear / 100)
        data.append({
            "name": f"Mån {month}",
            "bull": round(bull_price, 2),
            "base": round(base_price, 2),
            "bear": round(bear_price, 2),
        })

    if final_score >= 5:
        probs = {"bull": 35, "base": 45, "bear": 20}
    elif final_score >= 2:
        probs = {"bull": 30, "base": 50, "bear": 20}
    elif final_score >= -2:
        probs = {"bull": 25, "base": 50, "bear": 25}
    elif final_score >= -5:
        probs = {"bull": 20, "base": 45, "bear": 35}
    else:
        probs = {"bull": 10, "base": 35, "bear": 55}

    return {"data": data, "probabilities": probs}


def generate_portfolio(assets_analysis: dict) -> dict:
    """Generate portfolio allocation based on all asset analyses."""
    allocations = []

    colors = {
        "btc": "#f7931a", "global-equity": "#4facfe", "sp500": "#6c5ce7",
        "gold": "#ffd700", "silver": "#c0c0c0", "eurusd": "#00f2fe",
        "oil": "#636e72", "us10y": "#9d4edd",
    }

    for asset_id, analysis in assets_analysis.items():
        score = analysis["finalScore"]

        if score >= 5:
            weight = 20
            action = "buy"
        elif score >= 2:
            weight = 12
            action = "buy"
        elif score >= -2:
            weight = 0
            action = "hold"
        elif score >= -5:
            weight = 2
            action = "sell"
        else:
            if asset_id == "us10y" and score <= -5:
                weight = 18
                action = "buy"
            else:
                weight = 0
                action = "sell"

        allocations.append({
            "assetId": asset_id,
            "name": analysis.get("name", asset_id),
            "weight": weight,
            "action": action,
            "color": colors.get(asset_id, "#888"),
            "score": score,
        })

    total_weight = sum(a["weight"] for a in allocations)
    if total_weight > 0:
        scale = 95 / total_weight
        for a in allocations:
            a["weight"] = max(0, round(a["weight"] * scale))

    buy_assets = [a["name"] for a in allocations if a["action"] == "buy"]
    sell_assets = [a["name"] for a in allocations if a["action"] == "sell"]
    cash_pct = 100 - sum(a["weight"] for a in allocations)

    # List providers used across all agents
    all_providers = set()
    for analysis in assets_analysis.values():
        for p in analysis.get("providersUsed", ["rule_based"]):
            all_providers.add(p)

    motivation = (
        f"Portföljallokering baserad på AI-analys (via {', '.join(all_providers)}). "
        f"Köppositioner i: {', '.join(buy_assets) if buy_assets else 'Inga'}. "
        f"{'Reducerade positioner i: ' + ', '.join(sell_assets) + '. ' if sell_assets else ''}"
        f"Cash-buffert {max(0, cash_pct)}% för opportunistisk rebalansering."
    )

    return {
        "allocations": allocations,
        "cash": max(0, cash_pct),
        "motivation": motivation,
    }


def generate_risk_portfolios(assets_analysis: dict, market_state: dict) -> dict:
    """Generate 3 risk-profiled portfolios using Markowitz MPT optimization.

    Uses scipy.optimize to find mathematically optimal weights along the
    efficient frontier, with AI signals adjusting expected returns.

    Falls back to heuristic approach if optimization fails.
    """
    from portfolio_optimizer import optimize_portfolios

    overall_score = market_state.get("overallScore", 0)

    # Try MPT optimization first
    try:
        profiles = optimize_portfolios(assets_analysis)
        if profiles:
            logger.info("✅ MPT optimization successful")
            advice = get_regime_advice(overall_score, assets_analysis)
            return {"profiles": profiles, "regime": advice}
    except Exception as e:
        logger.warning(f"⚠️ MPT optimization failed, using fallback: {e}")

    # === Fallback: heuristic weights (used if MPT fails) ===
    logger.info("Using heuristic fallback for portfolio generation")
    colors = {
        "btc": "#f7931a", "global-equity": "#4facfe", "sp500": "#6c5ce7",
        "gold": "#ffd700", "silver": "#c0c0c0", "eurusd": "#00f2fe",
        "oil": "#636e72", "us10y": "#9d4edd",
    }
    safe_assets = {"us10y", "gold", "silver"}
    risky_assets = {"btc"}

    profiles_config = {
        "conservative": {
            "name": "Försiktig", "emoji": "🛡️",
            "description": "Heuristisk fallback — MPT-optimering ej tillgänglig.",
            "safe_mult": 3.0, "medium_mult": 0.6, "risky_mult": 0.1, "min_safe_pct": 55,
        },
        "balanced": {
            "name": "Balanserad", "emoji": "⚖️",
            "description": "Heuristisk fallback — MPT-optimering ej tillgänglig.",
            "safe_mult": 1.0, "medium_mult": 1.5, "risky_mult": 0.3, "min_safe_pct": 25,
        },
        "aggressive": {
            "name": "Aggressiv", "emoji": "🚀",
            "description": "Heuristisk fallback — MPT-optimering ej tillgänglig.",
            "safe_mult": 0.3, "medium_mult": 2.0, "risky_mult": 1.5, "min_safe_pct": 10,
        },
    }

    result_portfolios = {}
    for profile_id, profile in profiles_config.items():
        allocations = []
        for asset_id, analysis in assets_analysis.items():
            score = analysis["finalScore"]
            base_weight = _score_to_weight(score)
            if asset_id in safe_assets:
                weight = base_weight * profile["safe_mult"]
            elif asset_id in risky_assets:
                weight = base_weight * profile["risky_mult"]
            else:
                weight = base_weight * profile["medium_mult"]
            if overall_score < -3 and asset_id in safe_assets:
                weight = max(weight, 8)
            action = "buy" if weight > 0 else ("hold" if score >= -2 else "sell")
            allocations.append({
                "assetId": asset_id, "name": analysis.get("name", asset_id),
                "weight": max(0, round(weight)), "action": action,
                "color": colors.get(asset_id, "#888"), "score": score,
            })
        total = sum(a["weight"] for a in allocations)
        if total > 0:
            scale = 95 / total
            for a in allocations:
                a["weight"] = max(0, round(a["weight"] * scale))
        safe_total = sum(a["weight"] for a in allocations if a["assetId"] in safe_assets)
        if safe_total < profile["min_safe_pct"]:
            deficit = profile["min_safe_pct"] - safe_total
            safe_allocs = [a for a in allocations if a["assetId"] in safe_assets]
            if safe_allocs:
                best_safe = max(safe_allocs, key=lambda a: a["score"])
                best_safe["weight"] += deficit
        cash_pct = 100 - sum(a["weight"] for a in allocations)
        result_portfolios[profile_id] = {
            "id": profile_id, "name": profile["name"], "emoji": profile["emoji"],
            "description": profile["description"], "allocations": allocations,
            "cash": max(0, cash_pct), "total_weight": sum(a["weight"] for a in allocations),
        }

    advice = get_regime_advice(overall_score, assets_analysis)
    return {"profiles": result_portfolios, "regime": advice}


def _score_to_weight(score: float) -> float:
    """Convert AI score to base weight."""
    if score >= 6:
        return 22
    elif score >= 3:
        return 15
    elif score >= 0:
        return 8
    elif score >= -3:
        return 3
    elif score >= -6:
        return 1
    else:
        return 0


def get_regime_advice(overall_score: float, assets_analysis: dict) -> dict:
    """Determine market regime and recommend portfolio profile."""
    # Count bearish/bullish signals
    bearish = sum(1 for a in assets_analysis.values() if a.get("finalScore", 0) < -3)
    bullish = sum(1 for a in assets_analysis.values() if a.get("finalScore", 0) > 3)
    total = len(assets_analysis)

    # Determine regime
    if overall_score <= -4 or bearish >= total * 0.6:
        regime = "risk_off"
        regime_label = "Risk Off"
        regime_color = "#ef4444"
        recommended = "conservative"
        urgency = "high" if overall_score <= -6 else "medium"
        advice = (
            f"⚠️ Marknaden visar starka risk-off-signaler (AI-poäng: {overall_score:+.1f}). "
            f"{bearish} av {total} tillgångar har negativa utsikter. "
            f"Rekommenderar Försiktig profil för att skydda kapital."
        )
    elif overall_score <= -1 or bearish > bullish:
        regime = "cautious"
        regime_label = "Avvaktande"
        regime_color = "#f59e0b"
        recommended = "balanced"
        urgency = "medium" if overall_score <= -2.5 else "low"
        advice = (
            f"📊 Marknaden är avvaktande (AI-poäng: {overall_score:+.1f}). "
            f"En balanserad profil ger rimlig exponering med skydd nedåt."
        )
    elif overall_score >= 4 and bullish >= total * 0.5:
        regime = "risk_on"
        regime_label = "Risk On"
        regime_color = "#10b981"
        recommended = "aggressive"
        urgency = "low"
        advice = (
            f"🚀 Marknaden visar risk-on-signaler (AI-poäng: {overall_score:+.1f}). "
            f"{bullish} av {total} tillgångar har positiva utsikter. "
            f"Aggressiv profil kan ge hög avkastning."
        )
    else:
        regime = "neutral"
        regime_label = "Neutral"
        regime_color = "#6366f1"
        recommended = "balanced"
        urgency = "low"
        advice = (
            f"📈 Marknaden är neutral till lätt positiv (AI-poäng: {overall_score:+.1f}). "
            f"Balanserad profil rekommenderas."
        )

    return {
        "regime": regime,
        "regime_label": regime_label,
        "regime_color": regime_color,
        "recommended_profile": recommended,
        "switch_urgency": urgency,
        "advice": advice,
        "overall_score": round(overall_score, 1),
        "bearish_count": bearish,
        "bullish_count": bullish,
        "total_assets": total,
    }


def get_system_info() -> dict:
    """Return info about which providers are active."""
    available = get_available_providers()
    return {
        "available_providers": available,
        "agent_config": {
            "macro": {"provider": macro_agent.provider, "active": macro_agent.provider in available or macro_agent.provider == "rule_based"},
            "micro": {"provider": micro_agent.provider, "active": micro_agent.provider in available or micro_agent.provider == "rule_based"},
            "sentiment": {"provider": sentiment_agent.provider, "active": True},  # Always active (rule-based)
            "tech": {"provider": tech_agent.provider, "active": tech_agent.provider in available or tech_agent.provider == "rule_based"},
            "supervisor": {"provider": supervisor_agent.provider, "active": supervisor_agent.provider in available or supervisor_agent.provider == "rule_based"},
        },
        "llm_powered": len(available) > 0,
    }
