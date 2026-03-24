"""
LLM Provider - Abstraction layer for multiple AI model providers.
Supports OpenAI, Google Gemini, and Anthropic Claude.
Includes rate limiting and retry logic for free-tier API usage.
"""

import os
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("aether.llm")

# Tier → Model mapping (LLM Router - NVIDIA AI Blueprint inspired)
# Tier 0: Ultra-cheap (sentinel news scanning, classification)
# Tier 1: Cheap (sentiment, tech analysis)
# Tier 2: Medium (macro, micro, sectors, regions)
# Tier 3: Premium (supervisor, portfolio)
TIER_MODELS = {
    0: {"provider": "gemini", "model": "gemini-2.0-flash-lite"},   # ~50% cheaper than Flash
    1: {"provider": "gemini", "model": "gemini-2.5-flash"},
    2: {"provider": "gemini", "model": "gemini-2.5-flash"},       # Upgrade to anthropic/haiku when key available
    3: {"provider": "gemini", "model": "gemini-2.5-flash"},       # Upgrade to anthropic/opus when key available
}

# If Anthropic key is available, use tiered models
def _init_tier_models():
    """Auto-configure tier models based on available API keys."""
    if os.getenv("ANTHROPIC_API_KEY"):
        TIER_MODELS[2] = {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"}
        TIER_MODELS[3] = {"provider": "anthropic", "model": "claude-opus-4-20250514"}
        logger.info("🧠 Tier models: Flash-Lite → Flash → Haiku → Opus")
    elif os.getenv("OPENAI_API_KEY"):
        TIER_MODELS[2] = {"provider": "openai", "model": "gpt-4o-mini"}
        TIER_MODELS[3] = {"provider": "openai", "model": "gpt-4o"}
        logger.info("🧠 Tier models: Gemini Flash → 4o-mini → GPT-4o")
    else:
        logger.info("🧠 Tier models: All Gemini Flash (add ANTHROPIC_API_KEY for Opus)")

# Cache clients
_openai_client = None
_gemini_model = None
_anthropic_client = None

# Rate limiter for Gemini free tier (15 RPM = 1 request per 4 seconds)
_gemini_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent
_gemini_last_call = 0.0
_GEMINI_MIN_INTERVAL = 0.5  # seconds between calls (paid tier = fast)

# Daily API call counter (safety limit)
_daily_call_count = 0
_daily_reset_date: Optional[str] = None
_DAILY_LIMIT = 1400  # Safety margin under Gemini's 1500/day


def _check_daily_limit() -> bool:
    """Check and update daily API call counter. Returns True if under limit."""
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


def get_available_providers() -> list[str]:
    """Return list of providers with valid API keys."""
    available = []
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("GOOGLE_API_KEY"):
        available.append("gemini")
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    return available


async def call_llm(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Call an LLM and return the text response.
    Returns None if the provider is unavailable or call fails.
    """
    try:
        if not _check_daily_limit():
            return None
        if provider == "openai":
            return await _call_openai(system_prompt, user_prompt, temperature, max_tokens, model)
        elif provider == "gemini":
            return await _call_gemini(system_prompt, user_prompt, temperature, max_tokens, model)
        elif provider == "anthropic":
            return await _call_anthropic(system_prompt, user_prompt, temperature, max_tokens, model)
        else:
            logger.warning(f"Unknown provider: {provider}")
            return None
    except Exception as e:
        logger.error(f"LLM call failed ({provider}): {e}")
        return None


async def call_llm_tiered(
    tier: int,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> tuple[Optional[str], str]:
    """
    Call LLM using tiered model routing.
    Returns (response_text, provider_used).
    Falls through tiers on failure.
    """
    _init_tier_models()
    config = TIER_MODELS.get(tier, TIER_MODELS[1])
    provider = config["provider"]
    model = config["model"]

    result = await call_llm(provider, system_prompt, user_prompt, temperature, max_tokens, model)
    if result:
        return result, f"{provider}/{model}"

    # Fallback: try tier 1 if higher tier failed
    if tier > 1:
        t1 = TIER_MODELS[1]
        result = await call_llm(t1["provider"], system_prompt, user_prompt, temperature, max_tokens, t1["model"])
        if result:
            return result, f"{t1['provider']}/{t1['model']}(fallback)"

    return None, "rule_based"


async def _call_openai(system: str, user: str, temp: float, max_tokens: int, model: Optional[str] = None) -> Optional[str]:
    client = _get_openai()
    if not client:
        return None
    response = client.chat.completions.create(
        model=model or "gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temp,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


async def _call_gemini(system: str, user: str, temp: float, max_tokens: int, model: Optional[str] = None) -> Optional[str]:
    """Call Gemini with rate limiting for free tier."""
    global _gemini_last_call

    client = _get_gemini()
    if not client:
        return None

    model_name = model or "gemini-2.5-flash"

    # Rate limiting: wait for semaphore + minimum interval
    async with _gemini_semaphore:
        now = time.monotonic()
        wait_time = _GEMINI_MIN_INTERVAL - (now - _gemini_last_call)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        _gemini_last_call = time.monotonic()

        full_prompt = f"{system}\n\n---\n\n{user}\n\nRespond ONLY with valid JSON."

        try:
            from google.genai import types
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=temp,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if response and response.candidates:
                # Gemini 2.5 may include "thinking" parts – extract only non-thought text
                try:
                    content = response.candidates[0].content
                    parts = content.parts if content and content.parts else []
                    text_parts = []
                    for p in parts:
                        if hasattr(p, 'thought') and p.thought:
                            continue  # Skip thinking parts
                        if p.text:
                            text_parts.append(p.text)
                    result_text = "\n".join(text_parts) if text_parts else None
                except Exception:
                    result_text = None
                
                # Fallback to response.text if parts extraction failed
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
                logger.warning(f"  ⏳ {model_name} rate limited – falling back to rule_based")
                return None
            elif "not found" in error_str.lower() or "NOT_FOUND" in error_str:
                logger.warning(f"  ⚠️ Model {model_name} not found – falling back")
                return None
            else:
                logger.error(f"  ❌ Gemini error: {error_str[:150]}")
                return None

    return None


async def _call_anthropic(system: str, user: str, temp: float, max_tokens: int, model: Optional[str] = None) -> Optional[str]:
    client = _get_anthropic()
    if not client:
        return None
    model_name = model or "claude-sonnet-4-20250514"
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temp,
            timeout=30.0,  # 30s timeout
        )
        logger.info(f"  ✨ {model_name} responded successfully")
        return response.content[0].text
    except Exception as e:
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            logger.warning(f"  ⏳ {model_name} timed out after 30s")
        else:
            raise


def parse_llm_json(text: Optional[str]) -> Optional[dict]:
    """Safely parse JSON from LLM response."""
    if not text:
        return None
    
    import re
    
    # Step 1: Try direct parse (fastest path)
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Step 2: Strip everything outside { ... } and parse
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Step 3: Strip markdown code blocks then extract JSON
    cleaned = re.sub(r'.*?```(?:json)?\s*', '', text, count=1, flags=re.DOTALL)
    cleaned = re.sub(r'\s*```.*', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    if cleaned:
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            # Try extracting {} from cleaned
            s = cleaned.find('{')
            e = cleaned.rfind('}')
            if s != -1 and e > s:
                try:
                    return json.loads(cleaned[s:e + 1])
                except (json.JSONDecodeError, ValueError):
                    pass
    
    logger.warning(f"Failed to parse LLM JSON: {text[:200]}")
    return None

