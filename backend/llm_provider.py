"""
LLM Provider - Unified AI model routing via OpenRouter + Gemini.

Tier Architecture:
  Tier 0: Gemini 2.0 Flash (Google Free Tier) — news scanning, classification
  Tier 1: DeepSeek V3 via OpenRouter — chat, scenarios, tech/sentiment agents
  Tier 2: DeepSeek V3 via OpenRouter — macro/micro agents, sectors, regions
  Tier 3: Claude 3.5 Sonnet via OpenRouter — supervisor, portfolio (standard)
  Tier "3-opus": Claude 3 Opus via OpenRouter — supervisor (morning + escalation)

Escalation Policy:
  - Morning 07:00-09:00 CET: Tier 3 auto-upgrades to Opus
  - Regime shift detected: Escalates to Opus (max 1x/day)
  - Black swan (impact ≥ 9): Escalates to Opus (shares daily cap)
"""

import os
import json
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.llm")

# ============================================================
# TIER MODEL CONFIGURATION
# ============================================================

TIER_MODELS = {
    0: {"provider": "gemini",     "model": "gemini-2.0-flash"},
    1: {"provider": "openrouter", "model": "deepseek/deepseek-chat"},
    2: {"provider": "openrouter", "model": "deepseek/deepseek-chat"},
    3: {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.6"},
    "3-opus": {"provider": "openrouter", "model": "anthropic/claude-opus-4.6"},
}


def _init_tier_models():
    """Auto-configure tier models based on available API keys."""
    if os.getenv("OPENROUTER_API_KEY"):
        # Full OpenRouter setup — already configured in TIER_MODELS above
        logger.info("🌐 OpenRouter active: DeepSeek V3 (Tier 1-2), Sonnet (Tier 3), Opus (morning/escalation)")
    elif os.getenv("ANTHROPIC_API_KEY"):
        # Direct Anthropic fallback
        TIER_MODELS[2] = {"provider": "anthropic", "model": "claude-haiku-4-5-20251014"}
        TIER_MODELS[3] = {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}
        TIER_MODELS["3-opus"] = {"provider": "anthropic", "model": "claude-3-opus-20240229"}
        logger.info("🧠 Direct Anthropic: Haiku (Tier 2), Sonnet (Tier 3), Opus (escalation)")
    elif os.getenv("OPENAI_API_KEY"):
        TIER_MODELS[1] = {"provider": "openai", "model": "gpt-4o-mini"}
        TIER_MODELS[2] = {"provider": "openai", "model": "gpt-4o-mini"}
        TIER_MODELS[3] = {"provider": "openai", "model": "gpt-4o"}
        TIER_MODELS["3-opus"] = {"provider": "openai", "model": "gpt-4o"}
        logger.info("🧠 OpenAI: GPT-4o-mini (Tier 1-2), GPT-4o (Tier 3)")
    else:
        # All Gemini (free tier only)
        TIER_MODELS[1] = {"provider": "gemini", "model": "gemini-2.5-flash"}
        TIER_MODELS[2] = {"provider": "gemini", "model": "gemini-2.5-flash"}
        TIER_MODELS[3] = {"provider": "gemini", "model": "gemini-2.5-flash"}
        TIER_MODELS["3-opus"] = {"provider": "gemini", "model": "gemini-2.5-flash"}
        logger.info("🧠 All Gemini Flash (add OPENROUTER_API_KEY for hybrid Opus/Sonnet)")


_tier_models_initialized = False


def _ensure_tier_models():
    global _tier_models_initialized
    if not _tier_models_initialized:
        _init_tier_models()
        _tier_models_initialized = True


# ============================================================
# TIER ESCALATION GUARD
# ============================================================

CET = timezone(timedelta(hours=2))


class TierEscalationGuard:
    """Controls Opus escalation. Max N escalations per day beyond morning window."""

    def __init__(self):
        self._opus_escalations_today = 0
        self._opus_date: Optional[str] = None
        self._last_known_regime: Optional[str] = None
        self._opus_escalation_active = False  # Set when approved, cleared after consumed
        self.MAX_ESCALATIONS_PER_DAY = int(os.getenv("OPUS_MAX_ESCALATIONS", "1"))

    def _reset_if_new_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self._opus_date != today:
            self._opus_escalations_today = 0
            self._opus_escalation_active = False
            self._opus_date = today

    def is_morning_opus_window(self) -> bool:
        """True during morning scheduled Opus window (07:00-09:00 CET)."""
        hour = datetime.now(CET).hour
        return 7 <= hour < 9

    def should_escalate_to_opus(self, reason: str) -> bool:
        """Request Opus escalation. Returns True if allowed (daily cap not reached)."""
        self._reset_if_new_day()

        if self._opus_escalations_today >= self.MAX_ESCALATIONS_PER_DAY:
            logger.info(
                f"⛔ Opus eskalering NEKAD: {reason} "
                f"(redan {self._opus_escalations_today}/{self.MAX_ESCALATIONS_PER_DAY} idag)"
            )
            return False

        self._opus_escalations_today += 1
        self._opus_escalation_active = True  # Flag for supervisor to pick up
        logger.info(
            f"🧠 OPUS ESKALERING GODKÄND: {reason} "
            f"({self._opus_escalations_today}/{self.MAX_ESCALATIONS_PER_DAY} idag)"
        )
        return True

    def is_escalation_active(self) -> bool:
        """Check if an Opus escalation is waiting to be consumed."""
        self._reset_if_new_day()
        return self._opus_escalation_active

    def consume_escalation(self):
        """Mark the active escalation as consumed (called after Opus run completes)."""
        self._opus_escalation_active = False
        logger.info("✅ Opus eskalering konsumerad")

    def check_regime_shift(self, current_regime: str) -> bool:
        """Detect regime shift by comparing with last known regime.
        Returns True on first shift detected (does NOT auto-escalate — caller decides)."""
        if self._last_known_regime is None:
            self._last_known_regime = current_regime
            return False

        shifted = current_regime != self._last_known_regime
        old_regime = self._last_known_regime
        self._last_known_regime = current_regime

        if shifted:
            logger.info(f"🌊 REGIMSKIFTE detekterat: {old_regime} → {current_regime}")

        return shifted

    def get_status(self) -> dict:
        """Return current escalation status for API/debugging."""
        self._reset_if_new_day()
        return {
            "opus_escalations_today": self._opus_escalations_today,
            "max_per_day": self.MAX_ESCALATIONS_PER_DAY,
            "escalations_remaining": max(0, self.MAX_ESCALATIONS_PER_DAY - self._opus_escalations_today),
            "is_morning_window": self.is_morning_opus_window(),
            "last_known_regime": self._last_known_regime,
        }


# Singleton — importable by other modules
escalation_guard = TierEscalationGuard()


# ============================================================
# CLIENT CACHES
# ============================================================

_openai_client = None
_gemini_model = None
_anthropic_client = None
_openrouter_headers = None

# Rate limiter for Gemini free tier
_gemini_semaphore = asyncio.Semaphore(2)
_gemini_last_call = 0.0
_GEMINI_MIN_INTERVAL = 0.5

# Daily API call counter (safety limits)
_daily_call_count = 0
_daily_reset_date: Optional[str] = None
_DAILY_LIMIT = 1400  # Global max for all providers

# Per-tier daily call tracking (prevents runaway costs)
_tier_call_counts: dict = {}
_tier_reset_date: Optional[str] = None

# Hard caps per tier per day (safety net against loops)
TIER_DAILY_CAPS = {
    0: 500,     # Gemini Flash — free, generous cap
    1: 300,     # DeepSeek V3 — cheap, generous cap
    2: 300,     # DeepSeek V3 — cheap
    3: 50,      # Sonnet 4.6 — ~$3.25 max/day
    "3-opus": 20,  # Opus 4.6 — ~$1.40 max/day
}

# Estimated cost per call (input+output combined, conservative)
TIER_COST_ESTIMATE = {
    0: 0.0,        # Gemini free
    1: 0.00035,    # DeepSeek: ~1000in+500out
    2: 0.00035,    # DeepSeek
    3: 0.065,      # Sonnet: ~2000in+600out
    "3-opus": 0.07,  # Opus: ~2000in+600out ($5/$25)
}

# Daily budget cap in USD
_daily_cost_estimate = 0.0
_DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "5.0"))


def _check_daily_limit() -> bool:
    """Check and update daily API call counter."""
    global _daily_call_count, _daily_reset_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_reset_date != today:
        _daily_call_count = 0
        _daily_reset_date = today
    if _daily_call_count >= _DAILY_LIMIT:
        logger.warning(f"⛔ Daily API limit reached ({_daily_call_count}/{_DAILY_LIMIT})")
        return False
    _daily_call_count += 1
    return True


def _check_tier_limit(tier) -> bool:
    """Check per-tier daily call cap. Returns False if tier is over budget."""
    global _tier_call_counts, _tier_reset_date, _daily_cost_estimate

    today = datetime.now().strftime("%Y-%m-%d")
    if _tier_reset_date != today:
        _tier_call_counts = {}
        _daily_cost_estimate = 0.0
        _tier_reset_date = today

    tier_key = str(tier)
    current = _tier_call_counts.get(tier_key, 0)
    cap = TIER_DAILY_CAPS.get(tier, 200)

    # Check per-tier cap
    if current >= cap:
        logger.error(f"🚨 TIER {tier} DAGLIGT TAK NÅTT: {current}/{cap} anrop — BLOCKERAR")
        return False

    # Check daily budget
    cost = TIER_COST_ESTIMATE.get(tier, 0.001)
    if _daily_cost_estimate + cost > _DAILY_BUDGET_USD:
        logger.error(
            f"💸 DAGLIG BUDGET NÅDD: ~${_daily_cost_estimate:.2f} + ${cost:.3f} > "
            f"${_DAILY_BUDGET_USD:.2f} — BLOCKERAR tier {tier}"
        )
        return False

    _tier_call_counts[tier_key] = current + 1
    _daily_cost_estimate += cost
    return True


def get_daily_cost_status() -> dict:
    """Return current daily cost tracking for monitoring."""
    global _tier_call_counts, _daily_cost_estimate
    today = datetime.now().strftime("%Y-%m-%d")
    if _tier_reset_date != today:
        return {"date": today, "calls": {}, "estimated_cost_usd": 0.0, "budget_usd": _DAILY_BUDGET_USD}

    return {
        "date": today,
        "calls_per_tier": dict(_tier_call_counts),
        "tier_caps": {str(k): v for k, v in TIER_DAILY_CAPS.items()},
        "estimated_cost_usd": round(_daily_cost_estimate, 4),
        "budget_usd": _DAILY_BUDGET_USD,
        "budget_remaining_usd": round(max(0, _DAILY_BUDGET_USD - _daily_cost_estimate), 4),
        "budget_used_pct": round((_daily_cost_estimate / _DAILY_BUDGET_USD) * 100, 1) if _DAILY_BUDGET_USD > 0 else 0,
    }


# ============================================================
# PROVIDER CLIENTS
# ============================================================

def _get_openai():
    global _openai_client
    if _openai_client is None:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            return None
        from openai import OpenAI
        _openai_client = OpenAI(api_key=key)
    return _openai_client


def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            return None
        from google import genai
        client = genai.Client(api_key=key)
        _gemini_model = client
    return _gemini_model


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            return None
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=key)
    return _anthropic_client


def _get_openrouter_headers() -> Optional[dict]:
    global _openrouter_headers
    if _openrouter_headers is None:
        key = os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            return None
        _openrouter_headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://aether-ai.app"),
            "X-Title": "Aether AI",
            "Content-Type": "application/json",
        }
    return _openrouter_headers


def get_available_providers() -> list[str]:
    """Return list of providers with valid API keys."""
    available = []
    if os.getenv("OPENROUTER_API_KEY"):
        available.append("openrouter")
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("GOOGLE_API_KEY"):
        available.append("gemini")
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    return available


# ============================================================
# MAIN LLM CALL FUNCTIONS
# ============================================================

async def call_llm(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
    model: Optional[str] = None,
    plain_text: bool = False,
) -> Optional[str]:
    """
    Call an LLM and return the text response.
    Returns None if the provider is unavailable or call fails.
    """
    try:
        if not _check_daily_limit():
            return None
        if provider == "openrouter":
            return await _call_openrouter(system_prompt, user_prompt, temperature, max_tokens, model, plain_text)
        elif provider == "openai":
            return await _call_openai(system_prompt, user_prompt, temperature, max_tokens, model, plain_text)
        elif provider == "gemini":
            return await _call_gemini(system_prompt, user_prompt, temperature, max_tokens, model, plain_text)
        elif provider == "anthropic":
            return await _call_anthropic(system_prompt, user_prompt, temperature, max_tokens, model)
        else:
            logger.warning(f"Unknown provider: {provider}")
            return None
    except Exception as e:
        logger.error(f"LLM call failed ({provider}): {e}")
        return None


async def call_llm_tiered(
    tier: Union[int, str],
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
    plain_text: bool = False,
) -> tuple[Optional[str], str]:
    """
    Call LLM using tiered model routing.
    Returns (response_text, provider_used).
    Falls through tiers on failure.
    
    Tier values:
      0 = Gemini Flash (free)
      1 = DeepSeek V3 (cheap)
      2 = DeepSeek V3 (medium)
      3 = Claude Sonnet (standard premium)
      "3-opus" = Claude Opus (scheduled/escalation premium)
    """
    _ensure_tier_models()

    config = TIER_MODELS.get(tier, TIER_MODELS[1])
    provider = config["provider"]
    model = config["model"]

    # Safety: check per-tier budget before calling
    if not _check_tier_limit(tier):
        # Budget exceeded for this tier — fall back to cheaper tier
        if tier == "3-opus":
            logger.warning(f"🔽 Opus budget nått — nedgraderar till Sonnet")
            return await call_llm_tiered(3, system_prompt, user_prompt, temperature, max_tokens, plain_text)
        elif tier == 3:
            logger.warning(f"🔽 Sonnet budget nått — nedgraderar till DeepSeek")
            return await call_llm_tiered(1, system_prompt, user_prompt, temperature, max_tokens, plain_text)
        else:
            return None, "budget_exceeded"

    result = await call_llm(provider, system_prompt, user_prompt, temperature, max_tokens, model, plain_text)
    if result:
        return result, f"{provider}/{model}"

    # Fallback: try tier 1 if higher tier failed
    if tier not in (0, 1):
        t1 = TIER_MODELS[1]
        result = await call_llm(t1["provider"], system_prompt, user_prompt, temperature, max_tokens, t1["model"], plain_text)
        if result:
            return result, f"{t1['provider']}/{t1['model']}(fallback)"

    # Last resort: try Gemini Flash (always free)
    if tier != 0:
        t0 = TIER_MODELS[0]
        result = await call_llm(t0["provider"], system_prompt, user_prompt, temperature, max_tokens, t0["model"], plain_text)
        if result:
            return result, f"{t0['provider']}/{t0['model']}(emergency-fallback)"

    return None, "rule_based"


# ============================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================

async def _call_openrouter(
    system: str, user: str, temp: float, max_tokens: int,
    model: Optional[str] = None, plain_text: bool = False,
) -> Optional[str]:
    """Call OpenRouter API (OpenAI-compatible endpoint)."""
    import httpx

    headers = _get_openrouter_headers()
    if not headers:
        logger.warning("OpenRouter API key not configured")
        return None

    model_name = model or "deepseek/deepseek-chat"

    body: dict = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }

    # JSON mode for structured output (not all models support response_format)
    if not plain_text and "deepseek" not in model_name:
        # Claude and GPT models support response_format
        body["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Log cost if available
            usage = data.get("usage", {})
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                logger.info(
                    f"  ✨ {model_name}: {prompt_tokens}+{completion_tokens} tokens"
                )

            return content if content else None

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning(f"  ⏳ OpenRouter rate limited for {model_name}")
        elif e.response.status_code == 402:
            logger.error(f"  💳 OpenRouter insufficient credits for {model_name}")
        else:
            error_body = e.response.text[:200] if e.response else ""
            logger.error(f"  ❌ OpenRouter HTTP {e.response.status_code}: {error_body}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"  ⏳ OpenRouter timeout for {model_name} (60s)")
        return None
    except Exception as e:
        logger.error(f"  ❌ OpenRouter error: {str(e)[:150]}")
        return None


async def _call_openai(
    system: str, user: str, temp: float, max_tokens: int,
    model: Optional[str] = None, plain_text: bool = False,
) -> Optional[str]:
    client = _get_openai()
    if not client:
        return None
    kwargs = {
        "model": model or "gpt-4o",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    if not plain_text:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def _call_gemini(
    system: str, user: str, temp: float, max_tokens: int,
    model: Optional[str] = None, plain_text: bool = False,
) -> Optional[str]:
    """Call Gemini with rate limiting for free tier."""
    global _gemini_last_call

    client = _get_gemini()
    if not client:
        return None

    model_name = model or "gemini-2.5-flash"

    async with _gemini_semaphore:
        now = time.monotonic()
        wait_time = _GEMINI_MIN_INTERVAL - (now - _gemini_last_call)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        _gemini_last_call = time.monotonic()

        if plain_text:
            full_prompt = f"{system}\n\n---\n\n{user}"
        else:
            full_prompt = f"{system}\n\n---\n\n{user}\n\nRespond ONLY with valid JSON."

        try:
            from google.genai import types
            config_kwargs = {
                "temperature": temp,
                "max_output_tokens": max_tokens,
            }
            if not plain_text:
                config_kwargs["response_mime_type"] = "application/json"

            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            if response and response.candidates:
                try:
                    content = response.candidates[0].content
                    parts = content.parts if content and content.parts else []
                    text_parts = []
                    for p in parts:
                        if hasattr(p, 'thought') and p.thought:
                            continue
                        if p.text:
                            text_parts.append(p.text)
                    result_text = "\n".join(text_parts) if text_parts else None
                except Exception:
                    result_text = None

                if not result_text:
                    try:
                        result_text = response.text
                    except Exception:
                        pass

                if result_text:
                    logger.info(f"  ✨ {model_name} responded successfully")
                    return result_text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "RESOURCE_EXHAUSTED" in error_str:
                logger.warning(f"  ⏳ {model_name} rate limited – falling back")
                return None
            elif "not found" in error_str.lower() or "NOT_FOUND" in error_str:
                logger.warning(f"  ⚠️ Model {model_name} not found – falling back")
                return None
            else:
                logger.error(f"  ❌ Gemini error: {error_str[:150]}")
                return None

    return None


async def _call_anthropic(
    system: str, user: str, temp: float, max_tokens: int,
    model: Optional[str] = None,
) -> Optional[str]:
    client = _get_anthropic()
    if not client:
        return None
    model_name = model or "claude-haiku-4-5-20251014"
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temp,
            timeout=30.0,
        )
        logger.info(f"  ✨ {model_name} responded successfully")
        return response.content[0].text
    except Exception as e:
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            logger.warning(f"  ⏳ {model_name} timed out after 30s")
        else:
            raise


# ============================================================
# JSON PARSER (unchanged)
# ============================================================

def parse_llm_json(text: Optional[str]) -> Optional[dict]:
    """Safely parse JSON from LLM response."""
    if not text:
        return None
    
    import re
    
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    
    cleaned = re.sub(r'.*?```(?:json)?\s*', '', text, count=1, flags=re.DOTALL)
    cleaned = re.sub(r'\s*```.*', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if cleaned:
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            s = cleaned.find('{')
            e = cleaned.rfind('}')
            if s != -1 and e > s:
                try:
                    return json.loads(cleaned[s:e + 1])
                except (json.JSONDecodeError, ValueError):
                    pass
    
    logger.warning(f"Failed to parse LLM JSON: {text[:200]}")
    return None
