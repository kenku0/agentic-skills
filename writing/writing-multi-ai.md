# Multi-AI Writer

Parallel multi-model writing assistant via [OpenRouter](https://openrouter.ai/). Sends the same prompt to two AI models simultaneously and returns both drafts as JSON for comparison or synthesis.

## What it does

1. Detects the writing platform from the prompt (slack, email, linkedin, substack, article)
2. Adjusts token budgets and timeouts per platform (e.g., Slack drafts cap at 250 tokens / 35s)
3. Calls two models in parallel through OpenRouter
4. Applies post-processing: strips code fences, preamble, enforces line limits for short-form platforms
5. Returns structured JSON with both drafts, timing, and metadata

## Models

The script picks a model pair based on whether it detects a Codex CLI or Claude Code runtime:

| Runtime | Model A | Model B |
|---------|---------|---------|
| Claude Code | GPT-5.2 | Gemini 3.1 Pro |
| Codex CLI | Claude Opus 4.6 | Gemini 3.1 Pro |

The logic avoids using the same model family as the host agent (e.g., Claude Code already runs Claude, so Model A is GPT instead).

You can override the Opus model ID with the `OPENROUTER_OPUS_MODEL` env var.

## Reasoning model support

Both GPT-5.2 and Gemini 3.1 Pro are reasoning models that share their `max_tokens` budget between internal reasoning and visible content. Without adjustment, reasoning can consume most of the token budget, leaving truncated output.

The script handles this by:
- Adding a configurable overhead (default: 2048 tokens) on top of the requested content length
- Passing `reasoning.max_tokens` to cap reasoning allocation explicitly
- Auto-retrying Gemini with a larger budget and reduced reasoning effort when it returns empty content due to token exhaustion

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key from [openrouter.ai](https://openrouter.ai/) |
| `OPENROUTER_OPUS_MODEL` | No | Override Claude Opus model ID for Codex runtime |

The script checks `OPENROUTER_API_KEY` in the environment first, then falls back to a `.env` file in the repo root.

## Installation

```bash
pip install aiohttp
```

No other dependencies required. Python 3.10+.

## Usage

### Basic

```bash
python3 multi_ai_writer.py --prompt "Write a professional email declining a meeting invite"
```

### With platform detection

Include a `Platform:` line in your prompt and the script auto-adjusts token budgets:

```bash
python3 multi_ai_writer.py --prompt "Platform: slack
Quick update to the team that the deploy is delayed by 2 hours"
```

### Override defaults

```bash
python3 multi_ai_writer.py \
  --prompt "Write a long-form article intro about AI in healthcare" \
  --max-tokens 3000 \
  --temperature 0.6 \
  --timeout 120
```

### Force Codex runtime (use Opus instead of GPT)

```bash
python3 multi_ai_writer.py \
  --prompt "Draft a thank-you note" \
  --force-codex-runtime
```

## Output format

JSON to stdout. Example:

```json
{
  "model_a": {
    "content": "Subject: Quick Update...\n\nHi team,...",
    "finish_reason": "stop",
    "elapsed_seconds": 4.217
  },
  "model_b": {
    "content": "Subject: Deployment Status...\n\nHi all,...",
    "finish_reason": "stop",
    "elapsed_seconds": 3.891
  },
  "models_used": {
    "model_a": "openai/gpt-5.2",
    "model_b": "google/gemini-3.1-pro-preview"
  },
  "model_a_label": "GPT-5.2",
  "model_b_label": "Gemini 3.1 Pro",
  "runtime": "claude-code",
  "request": {
    "max_tokens": 250,
    "temperature": 0.4,
    "timeout_seconds": 35,
    "platform": "slack"
  }
}
```

## Platform-specific token budgets

When a `Platform:` line is detected in the prompt and `--max-tokens` is not explicitly set:

| Platform | Max tokens | Timeout |
|----------|-----------|---------|
| slack | 250 | 35s |
| linkedin | 300 | 35s |
| email | 800 | 90s |
| substack/article | 2500 | 90s |
| (default) | 2000 | 90s |

## CLI reference

```
usage: multi_ai_writer.py [-h] --prompt PROMPT [--repo-root REPO_ROOT]
                           [--force-codex-runtime] [--max-tokens MAX_TOKENS]
                           [--temperature TEMPERATURE] [--timeout TIMEOUT]

Multi-AI writing comparison via OpenRouter

options:
  --prompt PROMPT       The full formatted prompt to send to both AIs
  --repo-root REPO_ROOT Repo root used to locate .env file (default: .)
  --force-codex-runtime Force Codex runtime (use Opus as second-opinion model)
  --max-tokens N        Max tokens per model response (default: 2000)
  --temperature F       Sampling temperature (default: 0.4)
  --timeout N           Request timeout in seconds (default: 90)
```

## Customization

### System prompt

Edit the `SYSTEM_PROMPT` constant at the top of the script to match your own writing voice, name, style preferences, and anti-patterns. The default is a generic professional writing assistant.

### Models

Update the `DEFAULT_*_MODEL_ID` constants to use different OpenRouter models. Any model available on OpenRouter works. If the model is a reasoning model, add its ID to `MODEL_REASONING_OVERHEAD` and `MODEL_EXTRA_PARAMS` to get proper token budget management.

### Adding more models

To call 3+ models in parallel, extend `_models()` to return additional entries and add corresponding tasks in `run_parallel_calls()`. The `asyncio.gather` pattern scales to any number of concurrent calls.
