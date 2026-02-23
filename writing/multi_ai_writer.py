#!/usr/bin/env python3
"""
Multi-AI Writing Comparison via OpenRouter
==========================================
Calls two AI models in parallel via OpenRouter and returns both drafts
for comparison. Supports reasoning models (GPT-5.2, Gemini 3.1 Pro) with
automatic token budget management so reasoning doesn't starve content output.

Default model set depends on runtime:
- Claude Code: GPT-5.2 + Gemini 3.1 Pro
- Codex CLI: Claude Opus 4.6 + Gemini 3.1 Pro

Usage:
    python3 multi_ai_writer.py --prompt "Your writing prompt here"
    python3 multi_ai_writer.py --prompt "Platform: slack\\nDraft a quick update..."
    python3 multi_ai_writer.py --prompt "Write a blog post intro" --max-tokens 2500

Environment:
    OPENROUTER_API_KEY       - Required. API key from openrouter.ai
    OPENROUTER_OPUS_MODEL    - Optional. Override the Opus model id (Codex default)
"""

import asyncio
import argparse
import os
import json
import sys
from pathlib import Path
import re
from typing import Optional
import math

# Check for aiohttp availability
try:
    import aiohttp
except ImportError:
    print(json.dumps({
        "error": "aiohttp not installed. Run: pip install aiohttp",
        "model_a": {"error": "aiohttp not installed"},
        "model_b": {"error": "aiohttp not installed"}
    }))
    sys.exit(1)

# OpenRouter API endpoint
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FORCE_CODEX_RUNTIME = False


def _load_dotenv_var(*, repo_root: Path, key: str) -> Optional[str]:
    """
    Minimal .env loader for a single key.

    Supports simple KEY=VALUE pairs, optional surrounding quotes, and comments.
    Does not override existing environment variables.
    """
    existing = os.environ.get(key)
    if existing:
        return existing

    env_path = repo_root / ".env"
    if not env_path.exists():
        return None

    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() != key:
                continue
            value = v.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value or None
    except OSError:
        return None

    return None


def _is_codex_runtime() -> bool:
    if FORCE_CODEX_RUNTIME:
        return True
    # Heuristic: these env vars are set by Codex CLI.
    return bool(
        os.environ.get("CODEX_SANDBOX")
        or os.environ.get("CODEX_MANAGED_BY_NPM")
        or os.environ.get("CODEX")
    )


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

# Model IDs (verified on OpenRouter - Feb 2026)
# Note: Gemini -preview suffix may change when model graduates. Re-verify monthly.
DEFAULT_GPT_MODEL_ID = "openai/gpt-5.2"
DEFAULT_GEMINI_MODEL_ID = "google/gemini-3.1-pro-preview"
DEFAULT_OPUS_MODEL_ID = os.getenv("OPENROUTER_OPUS_MODEL") or "anthropic/claude-opus-4-6"


def _second_model_id() -> str:
    # In Codex, the base model is already GPT-5.2, so prefer non-GPT second opinions.
    return DEFAULT_OPUS_MODEL_ID if _is_codex_runtime() else DEFAULT_GPT_MODEL_ID


def _second_model_label() -> str:
    return "Claude Opus 4.6" if _is_codex_runtime() else "GPT-5.2"


def _base_model_label() -> str:
    return "GPT-5.2" if _is_codex_runtime() else "Claude"


def _models() -> dict[str, str]:
    # Back-compat key: in Codex mode "model_a" points to Opus, not GPT.
    return {
        "model_a": _second_model_id(),
        "model_b": DEFAULT_GEMINI_MODEL_ID,
    }


# ---------------------------------------------------------------------------
# Reasoning model token budgets
# ---------------------------------------------------------------------------
# Reasoning models (GPT-5.2, Gemini 3.1 Pro) share max_tokens between
# reasoning and visible content. These overheads are ADDED to the desired
# content length so reasoning doesn't starve the actual output.
#
# GPT-5.2: 400K context = 272K input + 128K output (128K reserved for output).
#   Using reasoning.max_tokens=2048 for predictable allocation.
#   With effort-based control, "high" (0.8 ratio) would consume 80% of
#   max_tokens for reasoning, leaving only 20% for content. For a 2000-token
#   request, that's only ~810 tokens of actual content.
#
# Gemini 3.1 Pro: Uses Google's thinkingLevel internally (not precise token
#   control), but reasoning.max_tokens is still passed through as a hint.
#   Max output: 65,536 tokens (default 8,192 -- must be set explicitly for
#   longer output).
MODEL_REASONING_OVERHEAD: dict[str, int] = {
    "openai/gpt-5.2": 2048,
    "google/gemini-3.1-pro-preview": 2048,
}

# Model-specific extra parameters using nested "reasoning" object (current
# OpenRouter format). OpenRouter rejects requests with BOTH effort and
# max_tokens set -- pick one per model. We use reasoning.max_tokens for
# both models for predictable token allocation.
# Note: Gemini 3.1 Pro's reasoning is mandatory - cannot be disabled.
MODEL_EXTRA_PARAMS: dict[str, dict] = {
    "openai/gpt-5.2": {
        "reasoning": {"max_tokens": 2048},
    },
    "google/gemini-3.1-pro-preview": {
        "reasoning": {"max_tokens": 2048},
    },
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Tuned for article-length content while keeping short-form fast.
# Platform auto-detection (slack/linkedin/email) overrides with lower caps.
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TEMPERATURE = 0.4

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
# Customize this for your own voice, name, and style preferences.
# The default below is a generic professional writing assistant prompt.
SYSTEM_PROMPT = """You are a professional writing assistant.
Write a send-ready draft based on the user's input.

## Voice & Style
- Crisp, direct, warm-professional tone
- Short sentences, active voice
- Be concise: clarity beats cleverness

## Anti-patterns (avoid these)
- Minimize em-dashes. One per piece max. Use commas, periods, or semicolons instead.
- Banned words: leverage, unlock, synergy, transformational, stakeholders, 10x, disrupt, cutting-edge, thought leader, robust, seamless.
- No forced metaphors in long-form writing.
- No marketing-speak disguised as insight.
- Vary sentence rhythm. Mix sentence lengths.

## Platform Rules
**Slack:** 2-6 lines, lead with purpose, clear CTA. No signature.
**Email:** Subject (if new thread) -> greeting -> purpose -> 1-2 paragraphs -> CTA -> signature.
**LinkedIn:** 2-6 lines, personable, one low-friction CTA. No signature.

## Output Rules
1. Output ONLY the draft - no preamble, no "Here's a draft...", no meta commentary
2. Preserve facts - never invent names, dates, numbers, or commitments
3. Flag gaps with [brackets]: [Confirm date], [Insert recipient name]
4. Be concise - clarity beats cleverness
5. If platform is Email, include a short "Subject: ..." line at the top (unless replying to existing thread)
6. If reference examples are provided, use them for tone/style only - do NOT copy facts from examples
"""


async def call_openrouter(
    session: aiohttp.ClientSession,
    model_id: str,
    prompt: str,
    api_key: str,
    *,
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
) -> dict:
    """
    Call OpenRouter API for a single model.

    Returns:
        dict with either {"content": "..."} or {"error": "..."}
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _coerce_content_to_text(content) -> str:
        """Handle varied content formats from different models."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return ""

    async def _post(*, effective_max_tokens: int, extra_params: Optional[dict] = None) -> dict:
        # Reasoning models: add overhead on top of desired content tokens.
        # max_tokens is the COMBINED budget (reasoning + content), so without
        # this adjustment, reasoning consumes most/all of the budget and
        # content truncates.
        overhead = MODEL_REASONING_OVERHEAD.get(model_id, 0)
        api_max_tokens = effective_max_tokens + overhead

        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": api_max_tokens,
            "temperature": temperature,
            **MODEL_EXTRA_PARAMS.get(model_id, {}),
            **(extra_params or {}),
        }

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with session.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                return {
                    "error": f"HTTP {resp.status}: {error_text[:300]}",
                    "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
                }
            data = await resp.json()
            if "error" in data:
                return {
                    "error": data["error"].get("message", str(data["error"])),
                    "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
                }
            choices = data.get("choices") or []
            if not choices:
                return {
                    "error": f"Unexpected response structure: {str(data)[:200]}",
                    "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
                }
            choice0 = choices[0] or {}
            message = choice0.get("message") or {}
            finish_reason = choice0.get("finish_reason")
            content = _coerce_content_to_text(message.get("content"))
            reasoning = message.get("reasoning")
            if content:
                if finish_reason == "length":
                    print(
                        f"[WARN] {model_id}: response truncated "
                        f"(finish_reason=length, max_tokens={api_max_tokens})",
                        file=sys.stderr,
                    )
                return {
                    "content": content,
                    "finish_reason": finish_reason,
                    "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
                }
            return {
                "error": "Empty response from model",
                "finish_reason": finish_reason,
                "has_reasoning": bool(reasoning),
                "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
            }

    started = asyncio.get_running_loop().time()
    try:
        result = await _post(effective_max_tokens=max_tokens)

        # Gemini 3.1 Pro sometimes returns empty `content` when it hits the
        # token limit while still generating reasoning. Retry once with a
        # larger token budget and reduced reasoning effort.
        if (
            model_id == "google/gemini-3.1-pro-preview"
            and isinstance(result, dict)
            and result.get("error") == "Empty response from model"
            and result.get("finish_reason") == "length"
        ):
            retry_max_tokens = min(max(max_tokens * 3, 2000), 8000)
            result = await _post(
                effective_max_tokens=retry_max_tokens,
                extra_params={"reasoning": {"max_tokens": 512}},
            )
            if isinstance(result, dict):
                result["retried_with_max_tokens"] = retry_max_tokens

        return result

    except asyncio.TimeoutError:
        return {
            "error": f"Timeout after {timeout_seconds}s",
            "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
        }
    except aiohttp.ClientError as e:
        return {
            "error": f"Network error: {str(e)}",
            "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "elapsed_seconds": round(asyncio.get_running_loop().time() - started, 3),
        }


def infer_platform(prompt: str) -> Optional[str]:
    """
    Best-effort platform inference from the user's prompt.
    Supports either a "Platform: ..." line or a "<platform> ..." block.
    Returns: slack, email, linkedin, substack, article, or None.
    """
    match = re.search(
        r"(?im)^\s*platform\s*:\s*(slack|email|linkedin|substack|article|other)\b",
        prompt,
    )
    if match:
        platform = match.group(1).lower()
        return None if platform == "other" else platform

    match = re.search(
        r"(?im)^\s*<platform>\s*(slack|email|linkedin|substack|article|other)\b",
        prompt,
    )
    if match:
        platform = match.group(1).lower()
        return None if platform == "other" else platform

    return None


def normalize_draft(text: str, *, platform: Optional[str]) -> str:
    """
    Local cleanup to improve "send-ready" quality without extra model calls.

    - Strips code fences, preamble, markdown headers
    - Normalizes whitespace
    - Enforces platform-specific line limits (slack/linkedin: max 6 lines)
    """
    cleaned = text.strip()

    # Remove wrapping code fences
    cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Remove common preamble patterns
    cleaned = re.sub(r"(?im)^\s*(here(?:'|')s|here is)\b.*?\n+", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(draft|email draft|message)\s*:\s*\n+", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*#{1,6}\s+.*\n+", "", cleaned)

    # Normalize line endings
    cleaned = re.sub(r"\r\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # Enforce line limits for short-form platforms
    if platform in {"slack", "linkedin"}:
        lines = [line.rstrip() for line in cleaned.split("\n")]
        non_empty = [line for line in lines if line.strip()]
        if len(non_empty) > 6:
            cleaned = "\n".join(non_empty[:6]).strip()

    return cleaned


async def run_parallel_calls(
    prompt: str,
    api_key: str,
    *,
    max_tokens: int,
    temperature: float,
    timeout_seconds: int,
    platform: Optional[str],
) -> dict:
    """
    Call two models in parallel via OpenRouter.

    - Claude Code runtime: GPT-5.2 + Gemini 3.1 Pro
    - Codex CLI runtime:   Claude Opus 4.6 + Gemini 3.1 Pro

    Returns:
        dict with results from both models, model metadata, and request params.
    """
    models = _models()
    connector = aiohttp.TCPConnector(limit_per_host=10, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Launch both API calls simultaneously
        model_a_task = call_openrouter(
            session,
            models["model_a"],
            prompt,
            api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        model_b_task = call_openrouter(
            session,
            models["model_b"],
            prompt,
            api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

        # Wait for both to complete
        results = await asyncio.gather(model_a_task, model_b_task, return_exceptions=True)

        # Handle any exceptions that weren't caught
        model_a_result = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
        model_b_result = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}

        if isinstance(model_a_result, dict) and model_a_result.get("content"):
            model_a_result["content"] = normalize_draft(model_a_result["content"], platform=platform)
        if isinstance(model_b_result, dict) and model_b_result.get("content"):
            model_b_result["content"] = normalize_draft(model_b_result["content"], platform=platform)

        return {
            "model_a": model_a_result,
            "model_b": model_b_result,
            "models_used": models,
            "model_a_label": _second_model_label(),
            "model_b_label": "Gemini 3.1 Pro",
            "runtime": ("codex" if _is_codex_runtime() else "claude-code"),
            "request": {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timeout_seconds": timeout_seconds,
                "platform": platform,
            },
        }


def main():
    parser = argparse.ArgumentParser(
        description="Multi-AI writing comparison via OpenRouter"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="The full formatted prompt to send to both AIs",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root used to locate .env file (default: current directory).",
    )
    parser.add_argument(
        "--force-codex-runtime",
        action="store_true",
        help="Force Codex runtime behavior (use Opus as the second-opinion model).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens per model response (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args()

    global FORCE_CODEX_RUNTIME
    FORCE_CODEX_RUNTIME = bool(args.force_codex_runtime)

    platform = infer_platform(args.prompt)
    user_set_max_tokens = "--max-tokens" in sys.argv
    user_set_timeout = "--timeout" in sys.argv

    effective_max_tokens = args.max_tokens
    effective_timeout = args.timeout

    # Platform-specific token budget overrides (unless user set explicitly)
    if platform and not user_set_max_tokens:
        if platform == "slack":
            effective_max_tokens = min(effective_max_tokens, 250)
        elif platform == "linkedin":
            effective_max_tokens = min(effective_max_tokens, 300)
        elif platform == "email":
            effective_max_tokens = min(effective_max_tokens, 800)
        elif platform in {"substack", "article"}:
            effective_max_tokens = max(effective_max_tokens, 2500)

    if platform in {"slack", "linkedin"} and not user_set_timeout:
        effective_timeout = min(effective_timeout, 35)

    # Get API key from environment or .env file
    repo_root = Path(args.repo_root).resolve()
    api_key = os.environ.get("OPENROUTER_API_KEY") or _load_dotenv_var(
        repo_root=repo_root, key="OPENROUTER_API_KEY"
    )
    if not api_key:
        print(json.dumps({
            "error": "OPENROUTER_API_KEY not set in environment or .env file",
            "model_a": {"error": "No API key"},
            "model_b": {"error": "No API key"},
        }))
        sys.exit(1)

    # Run the async calls
    results = asyncio.run(
        run_parallel_calls(
            args.prompt,
            api_key,
            max_tokens=effective_max_tokens,
            temperature=args.temperature,
            timeout_seconds=effective_timeout,
            platform=platform,
        )
    )

    # Output as JSON (ensure_ascii=False for international character support)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
