# Agentic Skills

Open-source skill definitions for AI-assisted workflows. Each skill is a `.md` file that acts as a system prompt for Claude Code's `/command` feature, paired with Python scripts where needed. Designed to be tool-agnostic — the patterns work with any agentic coding tool (Claude Code, Codex, Cursor, etc.).

These are redacted versions of production skills — company names, personal paths, and brand-specific details have been replaced with placeholders. The patterns, prompt engineering, and architecture are the real thing.

---

## Available Skills

| Skill | Description | Scripts |
|-------|-------------|---------|
| **slides** | AI slide generation via Gemini 3 native image gen. Includes anti-AI aesthetic rules, consulting templates, typography enforcement, and iterative refinement loops. | `gemini_slides.py` |
| **web-search** | Evidence-first research analyst with adaptive depth. Parallel agent discovery, source scoring (0-10), triangulation, and community search. Bring your own search tools or use the included Exa/Firecrawl/Reddit scripts. | `exa_search.py`, `reddit_search.py`, `firecrawl_search.py`, `firecrawl_fetch.py` |

More skills coming soon.

---

## How to Use

### 1. Install as Claude Code commands

Copy any `.md` file into your project's `.claude/commands/` directory:

```bash
cp agentic-skills/slides/slides.md your-project/.claude/commands/slides.md
```

Then invoke with `/slides` in Claude Code.

### 2. Customize for your brand

Each skill has `[PLACEHOLDER]` markers where you should add your own:
- Company name and logo paths
- Brand colors and typography
- Output directory conventions
- API keys (in your `.env`, never in the skill file)

### 3. Run the scripts

Scripts are standalone Python files. Install dependencies and set env vars:

```bash
pip install requests img2pdf
export GEMINI_API_KEY=your-key-here

python3 agentic-skills/slides/gemini_slides.py --test
```

---

## Architecture

```
.claude/commands/skill.md    ← Claude reads this as system prompt
skills/scripts/script.py     ← Claude calls this via Bash tool
.env                         ← API keys (git-ignored)
```

The `.md` file tells Claude *what to do* and *how to think*. The Python script handles the API calls that Claude can't make directly (image generation, multi-model synthesis, etc.).

---

## Requirements

- **Claude Code** (claude.ai/code) — the CLI tool
- **Gemini API key** — for `/slides` image generation
- **Exa API key** — for `/web-search` semantic search (optional — can use built-in WebSearch instead)
- **Reddit API credentials** — for `/web-search` community search (optional)
- **Firecrawl API key** — for `/web-search` page scraping (optional — can use built-in WebFetch instead)
- **Python 3.10+** with `requests` and `img2pdf`

---

## License

MIT. Use however you want. Attribution appreciated but not required.
