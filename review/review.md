---
description: "Multi-agent review (5-agent + multi-AI pipeline × 2 cycles). All modes: code, visual, design, skill/file. Pipeline: triage → [correctness, completeness, research, GPT-5.2+Gemini] parallel → consolidate."
argument-hint: "[visual|full|design|the /skillname skill] [url|path]"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Task, WebSearch, WebFetch, mcp__exa__web_search_exa, mcp__firecrawl__firecrawl_scrape, mcp__playwright__browser_navigate, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_resize, mcp__playwright__browser_click, mcp__playwright__browser_press_key, mcp__playwright__browser_snapshot, mcp__playwright__browser_console_messages, mcp__playwright__browser_evaluate
---

# Multi-Agent Review

**Every review mode uses a 5-agent pipeline × 2 cycles.** Visual mode adds a browser agent (6 total).

**Mode detection from $ARGUMENTS:**
- No args → **Full Review** (Code + Visual if web project detected, Code-only otherwise)
- `code` → Code Review only (staged or unstaged changes)
- `visual <url>` → Visual Review (5 agents + browser agent)
- `full <url>` → Code + Visual Review
- `design [path]` → Design Review (slides/visual assets)
- `the /skillname skill` or `<filepath>` → Skill/File Review

**How to detect Skill/File Review mode:**
- Input references a skill name: "the /discover skill", "/meeting", "the discover command"
- Input is a file path: `.claude/commands/discover.md`, `./scripts/gemini_slides.py`
- Input references a skill concept: "the meeting skill", "review /slides"
- **Resolve skill name → file:** `/skillname` → `.claude/commands/skillname.md`

### Meta-Principle: Fix the System, Not Just the Symptom

When a review catches an issue that the skill *should have* caught but didn't, don't just fix the code — **update this skill** to catch that class of error next time. The goal is to make each review run smarter than the last.

After fixing any issue, ask: "What check, if it existed, would have caught this automatically?" If the answer is clear, add it to the relevant section of this skill file before closing the review.

---

## Core Architecture: 5-Agent Pipeline + Multi-AI Synthesis

All review modes use this pipeline. The main conversation acts as **orchestrator** (triage + synthesis). Agents 1-3 run in parallel, Agent 4 (Research) also runs in parallel, Agent 5 (Consolidator) runs after all others complete. **Multi-AI synthesis (GPT-5.2 + Gemini) runs in parallel with the Claude agents** to provide independent external perspective.

```
Main conversation: Triage
  ├── Read diff/files, determine mode, classify risk
  ├── Generate context brief + risk questions
  │
  │   Parallel fan-out:
  ├── Agent 1: Correctness & Security
  ├── Agent 2: Architecture & Consistency
  ├── Agent 3: Completeness & Flow
  ├── Agent 4: Research (selective)
  ├── Agent 6: Multi-AI Synthesis (GPT-5.2 + Gemini via OpenRouter)
  │
  │   Sequential:
  └── Agent 5: Consolidator (after 1-4 AND 6 complete)
```

For **visual mode**, add a **Browser Agent** in Phase B (after the parallel fan-out, before consolidation) since browser MCP tools require exclusive access.

### Triage (Main Conversation — before launching agents)

| Step | Details |
|------|---------|
| **Read the target** | `git diff --staged` (code), full file read (skill/file), page source (visual), slide images (design) |
| **Map what changed** | Files, functions, dependencies, consumers affected |
| **Identify requirements** | TODOs, acceptance criteria, linked issues, stated goals in the scope |
| **Classify risk** | 🟢 Green (trivial) / 🟡 Yellow (moderate) / 🔴 Red (auth, data, payments, breaking changes) |
| **Generate risk questions** | 3-7 Socratic questions for investigators: "What happens if the list is empty?", "Are all consumers updated?" |

Output: Structured context brief → passed to all agents.

### Agent 1: Correctness & Security (general-purpose — parallel)

Proves/disproves correctness and security risks. Focus varies by mode (see mode sections below).

**Contract:** Input = risk hypotheses from triage. Output = findings with **specific line/file evidence** + verdict per risk. No vague "this could be a problem."

### Agent 2: Architecture & Consistency (Explore — parallel)

Proves/disproves architecture, pattern, and consistency risks. Reads beyond the diff into the broader codebase.

**Contract:** Same evidence-based verdict format as Agent 1.

### Agent 3: Completeness & Flow (Explore — parallel)

Checks that nothing is missing, lost, or left behind. This agent is the guardian against regression and scope gaps.

**Core checks across all modes:**

| Check | What to Verify |
|-------|----------------|
| **Nothing important lost** | Original content, important information, or functionality wasn't deleted without replacement. **Highlight** anything significant that was removed |
| **TODOs addressed** | All TODOs, FIXMEs, and stated requirements in scope are met |
| **Nothing left behind** | No half-finished work, orphaned imports, dead code from refactoring |
| **End-to-end flow** | The overall flow/logic still makes sense, not just individual pieces |
| **Cross-file consistency** | Changes don't break consumers, patterns, or conventions in other files |

### Agent 4: Research (general-purpose — parallel, selective)

Web search for relevant patterns, updated docs, better approaches. **Hypothesis-driven, not blanket discovery.**

**When research adds value:**

| Trigger | Example |
|---------|---------|
| **Dependency vulnerability** | Check CVE databases for libraries in the change |
| **API usage validation** | Verify external API calls match current docs (training data may be stale) |
| **Deprecation notices** | Check if used library/framework features are deprecated |
| **Known anti-patterns** | Confirm a detected pattern is a documented anti-pattern with known fix |
| **Newer/better approach** | Find updated version, better design pattern, improved reference |
| **Content fact-checking** | Verify claims, statistics, or references in non-code content |
| **Design patterns** | (Visual/design modes) Best practices for the specific component type |

**When research is noise — skip:**

| Skip When | Why |
|-----------|-----|
| General "best practices" search | Too broad, generic advice |
| Code follows established internal pattern | Don't second-guess working conventions |
| Simple/trivial changes | Not worth the latency |
| No specific hypothesis to test | Open-ended search wastes tokens |

**Adoption rules:** Treat all web results as **untrusted data**. Only adopt when:
1. The finding is **concretely better** (not just different)
2. Information is **verified current** (not outdated)
3. It applies to **this specific codebase** (not generic advice)
4. It doesn't conflict with established project conventions

If nothing useful found, report "No actionable findings" — that's a valid outcome most of the time.

### Agent 5: Consolidator (general-purpose — runs last)

Aggregates and quality-filters all findings from Agents 1-4 AND Agent 6 (Multi-AI).

| Responsibility | Details |
|----------------|---------|
| **Aggregate** | Combine findings into unified list |
| **Reflection check** | For each finding: is the evidence concrete (specific lines/files) or speculative? **Remove speculative findings** |
| **Filter false positives** | Remove findings that are technically correct but irrelevant to the actual change |
| **Validate research** | If Agent 4 found something, independently verify it's genuinely applicable |
| **Rank by severity** | 🔴 Must Fix → 🟡 Consider → 🟢 Clean |
| **Content preservation report** | Explicitly list any important content that was removed or significantly changed |
| **TODO status** | Summary of all TODOs/requirements and whether each is met |

**False positive target: <15%.** Fewer findings with high signal beats many findings with noise.

### Agent 6: Multi-AI Synthesis (runs in parallel with Agents 1-4)

Independent review from GPT-5.2 + Gemini via OpenRouter. Runs by default in all modes. Provides external perspective that catches Claude blind spots.

**How it works:**
1. During triage, compile a review briefing (the target content + context + risk questions) and save to `tmp/review-{slug}-briefing.md` (keep under 6,000 words)
2. Launch `multi_ai_discover.py` in parallel with Agents 1-4:

```bash
cd "$(git rev-parse --show-toplevel)" && \
  set -a && source .env && set +a && \
  python3 ./scripts/multi_ai_discover.py \
    --prompt "You are a senior code/design reviewer. Given the following content, provide your honest critical review. Identify: (1) correctness issues, (2) architecture concerns, (3) missing pieces, (4) what you'd do differently. Be specific — cite line numbers or sections. Do NOT just agree with the existing content — bring genuinely new perspective." \
    --sources-file tmp/review-{slug}-briefing.md \
    --max-tokens 4096 \
    --timeout 300 \
    --out-dir tmp/review-{slug}-models/
```

3. Pass GPT-5.2 + Gemini outputs to Agent 5 (Consolidator) alongside Agents 1-4 findings
4. Consolidator synthesizes: note **convergence** (all models agree = high confidence) and **divergence** (models disagree = important trade-off to surface)

**When to skip multi-AI:**
- User says "lite", "quick", "no multi-AI"
- Pure code style review (tiny diff, no architectural decisions)
- `OPENROUTER_API_KEY` missing (graceful degradation — note "Multi-AI: skipped" in output)

**Graceful degradation:** If script fails or times out, proceed with Claude-only review. Note "Multi-AI: skipped ([reason])" in the final verdict.

---

## Two-Cycle Methodology

Every `/review` runs **two full cycles**. The second catches regressions, missed items, and verifies fixes.

### Cycle 1: Identify + Fix

1. Run triage (main conversation)
2. Launch Agents 1-4 in parallel
3. (Visual mode: run Browser Agent after parallel phase)
4. Run Agent 5 (Consolidator)
5. Catalog all issues (🔴 must fix, 🟡 consider)
6. **Implement fixes immediately** — don't just report
7. Commit-ready state after Cycle 1

### Cycle 2: Verify + Flow + Polish

1. Re-run Agents 1-3 on the **fixed** code/content
2. Agent 4 (Research): skip unless Cycle 1 introduced new patterns worth validating
3. Agent 5: fresh consolidation

**Cycle 2 adds these checks:**

| Check | What to Verify |
|-------|----------------|
| **Cycle 1 fixes verified** | Every fix is correct, no regressions introduced |
| **End-to-end flow** | The entire flow still makes sense after individual fixes |
| **Content preservation** | Important information wasn't lost during fixes — highlight anything removed beyond scope |
| **TODO re-check** | All requirements still met after changes |
| **Polish** | (Visual/design) Refactoring UI checks applied more carefully |

**Final verdict:** 🟢 Ship it or 🔴 Fix remaining issues.

**Why two cycles:** Single-pass reviews anchor on finding problems. Second-pass anchors on verifying solutions — different cognitive frame catches different things.

---

## Mode: Code Review

Review code changes. Check staged first (`git diff --staged`); if nothing staged, review unstaged (`git diff`). If neither has changes, inform user "No changes to review."

### Agent 1 Focus: Code Correctness & Security

| Check | What to Look For |
|-------|------------------|
| **Correctness** | Does it do what it claims? Edge cases handled? |
| **Security** | No secrets, no injection risks, auth verified? |
| **Authorization gaps** | Endpoints verify permissions, not just authentication (IDOR prevention) |
| **Input validation** | Parameterized queries, no string interpolation in DB queries |
| **Error handling** | Errors not swallowed with console.log, no stack traces in responses |
| **Performance** | N+1 queries? Unbounded loops? Blocking I/O in async? Memory leaks? |
| **Types** | TypeScript strict? No `any` escapes? |
| **Test quality** | Tests exist? Assertions meaningful (not just `toBeDefined()`)? Error paths tested? |

### Agent 2 Focus: Architecture & Code Consistency

| Check | What to Look For |
|-------|------------------|
| **Pattern drift** | New code diverges from established conventions |
| **Duplicate logic** | Same function/pattern reimplemented (check if utility already exists) |
| **Cross-file impact** | Changes break consumers in other files (API contracts, shared types) |
| **Unnecessary complexity** | Over-engineering: abstract base classes, factory patterns where a function suffices |
| **Domain boundary violations** | Direct DB access across service boundaries, circular dependencies |

### Agent 3 Focus: Code Completeness & Cleanup

| Check | JS/TS | Python | Skill files (.md) |
|-------|-------|--------|-------------------|
| **Debug statements** | `console.log`, `debugger` | `print(`, `breakpoint()` | N/A |
| **Commented code** | `/* ... */`, `// old code` | `# old code` blocks | Commented-out sections |
| **Unused imports** | Imports not referenced | Imports not referenced | N/A |
| **Unresolved TODOs** | `TODO`, `FIXME`, `HACK` | Same | `TODO`, `FIXME`, placeholders |
| **Hardcoded values** | API keys, secrets, magic numbers | Same | Hardcoded paths, stale URLs |

Plus the core Agent 3 checks: nothing important lost, TODOs met, nothing left behind, flow makes sense.

### Commands to Run

```bash
# Check for debug statements (language-aware)
git diff --staged | grep -E "console\.(log|debug)|debugger|print\(|breakpoint\(\)"

# Run tests (auto-detect)
# JS/TS: npm test / npx jest / npx vitest
# Python: pytest / python -m pytest
# Go: go test ./...

# Lint (if available)
# JS/TS: npm run lint / npx eslint
# Python: ruff check / flake8
```

### Code Review Output

```markdown
### Review Summary

**Files changed:** [N files] | **Risk tier:** 🟢/🟡/🔴

### Issues Found

🔴 **Must Fix:**
- [file:line] [issue description] — [evidence]

🟡 **Consider:**
- [file:line] [suggestion] — [rationale]

### Research Findings (Agent 4)
- [finding] — [source] — Adopt? ✅/❌ [reason]
(or: "No actionable findings")

### Completeness
- [ ] No debug statements (or: found N)
- [ ] No commented-out code (or: found in [file])
- [ ] No unused imports (or: found N)
- [ ] No unresolved TODOs (or: found N)
- [ ] Original content/functionality preserved
- [ ] All stated requirements met

### Tests
- [ ] All tests pass: [X/Y passed]
- [ ] New code has test coverage

### Verdict
🟢 **Ready to commit**
— or —
🔴 **Fix issues above first**
```

---

## Mode: Skill/File Review

Review a specific skill command file (`.claude/commands/*.md`) or any individual file for internal consistency, correctness, and completeness.

### Agent 1 Focus: Cross-Reference & Correctness

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **Agent/phase counts** | Numbers in one section match definitions elsewhere | "6 agents" but 7 defined |
| **Section references** | "See Phase 3b" targets exist | Phase 3b renamed |
| **Variable placeholders** | `{company}`, `{slug}` used consistently | Mixed `{company_name}` and `{company}` |
| **File path references** | Referenced files actually exist | Path typo or file moved |
| **Script references** | Scripts match actual bash commands in phases | Script renamed but table not updated |
| **Threshold consistency** | Same metric has matching thresholds everywhere | CP3 says "≥3" but Key Requirements says "≥5" |
| **Model reference freshness** | Model names/IDs match current versions | "Claude Opus 4.5" when current is 4.6 |

### Agent 2 Focus: Conditional & Structural Integrity

**Conditional Branch Completeness:**

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **If/else paths** | Every conditional has both branches documented | "If team provided, do X" but no else |
| **Fallback chains** | Every agent/tool has a fallback for failure | Agent 4 has no fallback if API fails |
| **Optional features** | Optional features handled in ALL downstream phases | Agent 7 added to Phase 1 but Phase 4 doesn't include its output |
| **Mode variants** | Lite/Full/PE modes correctly include/exclude steps | Lite says "skip agents 4-6" but doesn't mention new Agent 7 |

**Structural Integrity:**

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **Frontmatter accuracy** | `description`, `argument-hint`, `allowed-tools` match behavior | Skill edits files but `allowed-tools` lacks Edit |
| **Phase ordering** | Sequence diagram matches descriptions | Diagram ≠ text |
| **Duplicate/conflicting instructions** | Two sections giving different guidance | Conflicting agent counts |
| **Dead instructions** | References to removed features/old patterns | "Update Research Ledger" but it was removed |
| **Step numbering** | No duplicates, no gaps | Two step 4s |

### Agent 3 Focus: Completeness & Quality Coverage

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **Feature ↔ checklist parity** | Every feature has a corresponding checklist item | New feature added but no checklist item |
| **Checklist actionability** | Each item is verifiable (yes/no), not vague | "Use cases are good" vs "Each has Before→After" |
| **Nothing important lost** | (If reviewing changes) Original key content preserved | Critical instruction deleted in refactor |
| **TODOs met** | Stated requirements and goals are addressed | |

### Obsidian Visual Quality (for `.md` files)

When reviewing `.md` files that live in the Obsidian vault, check for **Reader View / Live Preview quality**. These files are read daily in Obsidian, so visual presentation matters as much as content accuracy.

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **Tables over prose** | Structured data (comparisons, options, specs) should be in tables, not bullet lists or paragraphs | 6 CLI flags described in prose when a table would be scannable |
| **Collapsible callouts** | Verbose/reference content (transcripts, raw data, long examples) should use `[!info]- Title` collapsible callouts | 50-line code example inline instead of collapsed |
| **Section hierarchy** | H2 for major sections, H3 for subsections, no H4+ nesting. 4-6 substantial sections preferred over 10+ thin ones | 12 sections with 2-3 lines each |
| **Whitespace & horizontal rules** | `---` between major zones, blank lines between sections | Wall of content with no visual breaks |
| **Bold for scanability** | Key terms, names, statuses bolded so eyes can skim | Important terms buried in regular-weight text |
| **Blockquotes for meta** | Background notes, attributions, secondary context in `>` blocks | Meta-information mixed into primary content |
| **No deep nesting** | Bullets max 2 levels deep | 4-level nested bullet lists |
| **Cross-link navigation** | Related files linked with `[[wikilinks]]` or `file://` links near top | No way to navigate to related files |
| **Checkbox conventions** | `[ ]` pending, `[x]` done, `[?]` answered, `[-]` skipped | All checkboxes use only `[x]` (loses nuance) |
| **No bare URLs** | Use `[Label](url)` or reference-style links, never bare `https://...` | Long URLs breaking across lines |
| **YAML frontmatter** | Appropriate metadata (title, created, updated, tags) | No frontmatter or stale dates |

**Anti-patterns to flag:**
- Wall of text without visual breaks
- Tables with >7 columns (split into multiple tables)
- Mixing multiple formatting styles in the same section
- Emoji headers (one `🔗` for nav bar is the only acceptable emoji)
- Redundant section headers that add no information

### Content Flow & Organization (for `.md` prose files)

When reviewing `.md` files with substantial prose (project logs, design briefs, meeting notes, articles), check for **logical flow and content organization** — not just visual formatting.

| Check | What to Look For | Example Failure |
|-------|------------------|-----------------|
| **Redundant ideas** | Same concept repeated in multiple sections with different wording | "Security is a priority" in section 2, "We prioritize security" in section 5, "Security-first approach" in section 8 |
| **Scattered related content** | Related points spread across distant sections instead of grouped | Timeline details in intro, in section 3, and in appendix — should be one place |
| **Section purpose clarity** | Each section has a clear, distinct purpose; no "catch-all" sections | "Additional Notes" section that's actually 5 unrelated topics |
| **Logical progression** | Sections flow in a natural order (context → problem → solution → next steps) | Solution described before the problem is explained |
| **Orphaned paragraphs** | Paragraphs that don't connect to their surrounding content | A paragraph about pricing dropped between two paragraphs about timeline |
| **Repetitive phrasing** | Same sentence structures or phrases used across sections | Every section starts with "It's important to note that..." |
| **Dead weight** | Paragraphs that add no new information beyond what's already stated | Filler paragraphs restating the intro |
| **Missing transitions** | Abrupt topic shifts between sections with no connecting logic | Section about team jumps straight to section about pricing with no bridge |

**How to report flow issues:**
- Group related redundancies together: "These 3 sections all discuss security → consolidate into one"
- Suggest reorganization with a proposed outline, not just "this is scattered"
- For each suggested move, note: "Move paragraph X from section A to section B (better fit because...)"

### Content Preservation Protocol

**CRITICAL: When fixing flow or organization issues in any `.md` file, follow this protocol to prevent content loss.**

**Before making edits:**
1. **Catalog key facts** — List every important data point, decision, name, date, metric, and unique insight in the file
2. **Tag each item** — Mark as: `[KEEP]` (essential), `[CONSOLIDATE]` (merge with duplicate), `[TRIM]` (verbose but info preserved elsewhere)
3. **Show the catalog to the user** before implementing changes

**After making edits:**
4. **Verify catalog** — Check every `[KEEP]` item is still present in the edited file
5. **Report changes** — Show a summary:
   - **Kept:** N items (all essential content preserved)
   - **Consolidated:** N items (merged duplicates, original info retained)
   - **Trimmed:** N items (verbose phrasing shortened, no info lost)
   - **Removed:** N items (with reason for each — user must approve removals)

**Rules:**
- Never silently delete paragraphs — always flag what was removed and why
- When consolidating duplicates, keep the **strongest version** (most specific, most evidence-backed)
- If unsure whether something is redundant or adds nuance, **keep it** and flag for user decision
- Show before/after for any substantial reorganization

### Python/Script File Checks

If reviewing a Python script (e.g., `./scripts/*.py`):

| Check | What to Look For |
|-------|------------------|
| **Argument parsing** | `argparse` args match what the skill command passes |
| **Error handling** | API calls have try/except, timeouts, and fallbacks |
| **Output format** | Script output matches what the calling skill expects to parse |
| **Secrets** | API keys read from env vars, not hardcoded |
| **Dependencies** | All imports available (or documented in fallback section) |

### Skill/File Review Output

```markdown
### Review: [file path or skill name]

**Lines:** [N] | **Type:** Skill command / Python script / Config
**Risk tier:** 🟢/🟡/🔴

### Issues Found

🔴 **Must Fix:**
- [line:N] [issue description]

🟡 **Consider:**
- [line:N] [suggestion]

### Research Findings (Agent 4)
- [finding] — [source] — Adopt? ✅/❌
(or: "No actionable findings")

### Cross-Reference Consistency
- [ ] Agent/phase counts match
- [ ] Section references resolve
- [ ] Variable placeholders consistent
- [ ] File path references exist
- [ ] Script references match

### Conditional & Structural Completeness
- [ ] All if/else paths documented
- [ ] Fallbacks defined for every agent/tool
- [ ] Optional features handled in all downstream phases
- [ ] Mode variants complete
- [ ] No dead instructions

### Quality Coverage
- [ ] Every feature has a checklist item
- [ ] Checklist items are verifiable (yes/no)
- [ ] Original important content preserved
- [ ] All requirements met

### Verdict
🟢 **Clean**
— or —
🔴 **Fix [N] issues first**
```

---

## Mode: Visual Review (5 Agents + Browser Agent)

Visual review uses the 5-agent pipeline plus a **Browser Agent** that runs in Phase B (since browser MCP tools require exclusive access).

### Inputs

- **url** (required): The URL to review
- **qa-script-path** (optional): Path to a QA checklist to test against

### Execution Phases

**Phase A — Agents 1-4 in parallel (no browser needed):**

| Agent | Type | Focus |
|-------|------|-------|
| Agent 1: Correctness | Explore | Source Analysis — CSS/templates, typography, spacing, brand compliance, dynamic content |
| Agent 2: Architecture | Explore | Cross-Component Consistency — Nav/Footer parity, i18n, placeholder content, credential ordering |
| Agent 3: Completeness | Explore | Content preservation, flow coherence, TODO/requirements check |
| Agent 4: Research | general-purpose | Design patterns for the specific page type (selective — see core architecture) |

**Phase B — Browser Agent (sequential, after Phase A):**

| Agent | Type | Focus |
|-------|------|-------|
| Browser Agent | general-purpose | Screenshots, DOM/a11y inspection, interaction checks, modal content, mobile viewport, console errors |

**Phase C — Agent 5: Consolidator (after all above)**

**Browser tool preference:**

```
Chrome DevTools MCP          ← PREFERRED (lighter, more token-efficient)
        ↓ fallback
Playwright MCP               ← FALLBACK (heavier a11y tree, works for cross-browser)
```

- **Chrome DevTools MCP** — snapshot-on-demand, more token-economical. Better for: debugging, performance, network inspection.
- **Playwright MCP** — comprehensive a11y tree. Use for: cross-browser testing, E2E, CI pipelines. Also when Chrome DevTools MCP is not configured.

**Why browser runs separately:** Browser MCP controls a single instance. Always close the browser in the main conversation before launching the Browser Agent.

---

### Agent 1: Source Analysis Checks

Read stylesheets, layout components, and page templates. Reason about computed rendering behavior that screenshots can't catch.

#### Typography & Locale

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **CJK letter-spacing** | `letter-spacing` on headings applied to `html[lang="ja"]` content | Negative tracking compresses CJK characters |
| **CJK word-break** | `word-break: keep-all` set for JA locale | Default breaks split katakana mid-word |
| **CJK text-transform** | `text-transform: uppercase` on elements with Japanese text | `letter-spacing: 0.1em` adds unnatural gaps |
| **Heading hierarchy** | H1 → H2 → H3 sizes form clear visual scale | H2 larger than parent section's heading |
| **Font stack mixing** | Display headings using serif + CJK sans-serif fallback | "AI" in Fraunces, surrounding Japanese in Hiragino Sans |

#### Bilingual Text Balance (if site has EN + JA)

CJK characters are denser and wider than Latin at the same font size. Check both languages.

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Hero heading line count** | EN vs JA hero `<h1>` should wrap to similar line counts | JA wraps to 3 lines, EN is 2, dangling 。 |
| **Dangling CJK punctuation** | 。、） sitting alone on the last line of large headings | `max-w-reading` + large font = overflow |
| **Card title height parity** | JA titles cause significantly taller cards than EN? | Long katakana wraps to 2+ lines |
| **Button/pill text overflow** | JA text fits without wrapping or clipping? | Long JA CTA text overflows |
| **Nav label crowding** | JA nav items overlap before mobile breakpoint? | "私たちについて" vs "About" |

**Fixes (in preference order):**
1. Shorten the JA copy (dictionary form over polite form)
2. Add `<br class="hidden md:block">` at natural phrase break
3. Widen the container for that specific element
4. Accept it — minor dangling punctuation is common in Japanese web design

#### Mobile Overlap & Scroll

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Fixed/sticky vs content** | Fixed bottom bars — matching bottom padding? | Sticky CTA hides footer content |
| **Modal scroll** | Modals have `max-height` + `overflow-y: auto` | Virtual keyboard pushes fields off-screen |
| **Overlay z-index stacking** | Modal > sticky CTA > nav z-index ordering | Nav dropdown behind modal overlay |

#### Dynamic Content & Rendered Markup

Modals, drawers, CMS/markdown-rendered content are the #1 place hierarchy dies. **Open every modal/drawer during review.**

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Modal content hierarchy** | At least 2 visual levels inside modals? | All content renders as uniform `text-sm text-gray-500` |
| **Prose-rendered sections** | Semantically distinct sections look different? | All `<p>` tags identical |
| **Metric/stat presentation** | Quantitative results visually prominent? | Metrics in `text-xs` — smallest element |
| **Context badges/tags** | Category/type context present? | Can't tell Build vs Workshop without reading body |
| **Information density** | Enough spacing, color variation, grouping? | Wall of same-size text |

**Fix patterns:**
1. Bold + navy for section labels
2. Card-style metrics — background tint, larger value text
3. Category badges — pill-shaped tags
4. Generous paragraph spacing in modals

#### Visual Noise & Emphasis Calibration

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Bold strobe effect** | >50% of list items use `<strong>` → bold loses signal | Every bullet leads with bold phrase |
| **Emphasis competing** | Bold + color + size + border stacked on same element | Too many signals on one card |
| **Section weight balance** | Adjacent sections have balanced visual weight | One section all bold, neighbor all gray |
| **Squint test** | Primary vs secondary visible when blurred? | Everything same weight |
| **CJK heading punctuation** | Large JA headings omit terminal 。, avoid 、 at line-break | Dangling punctuation at display sizes |

**Fix patterns:**
1. Remove bold from lists — plain text with teal dots
2. One emphasis per element
3. Match sibling patterns

#### Brand Guide Compliance

Read `your-brand-guide.md` and cross-reference:

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Terminology checks** | Verify branded terms match official style — NOT possessive/shortened forms | Possessive/shortened forms reverse branding |
| **Punctuation anti-patterns** | Em dashes where commas/periods preferred | "Breathless" voice |
| **Voice patterns** | No filler words, no "leverage/utilize/cutting-edge" | Marketing language survives |

#### Visual Sizing & Contrast

| Check | What to Look For | Common Failures |
|-------|------------------|-----------------|
| **Photo aspect ratios** | Responsive sizing (`aspect-*`) not fixed height | Fixed height crops heads |
| **Dark-on-dark contrast** | Sufficient contrast on dark sections | Just barely passing WCAG AA |
| **Pill/badge contrast** | Small text on colored backgrounds readable | |
| **CTA card sizing** | Cards don't shrink with shorter text (especially CJK) | JA card 30% narrower than EN |

---

### Agent 2: Cross-Component Consistency Checks

Read actual source files (Nav, Footer, all page files) — don't rely solely on screenshots.

| Check | What to Verify | Common Failures |
|-------|----------------|-----------------|
| **Nav ↔ Footer link order** | Same order? | Footer built at different time |
| **Page structure pattern** | Every page: Kicker → H1 → lead at top; CTA at bottom | Missing CTA or different intro |
| **CTA context values** | `data-contact-context` matches page topic | Copy-pasted with wrong context |
| **i18n parity** | EN/JA pages: same structure, sections, CTA placement | JA drifts from EN |
| **Credential/bio ordering** | Consistent ordering convention | Mixed chronological and prestige-first |
| **Credential visual treatment** | Visually distinct from body text | Plain faded text at bottom |
| **List/bullet pattern consistency** | Same visual pattern across pages | Teal dots here, numbered badges there |
| **Placeholder content** | No dummy URLs, lorem, TODO markers | Placeholders survive to production |
| **Asset freshness** | Logo/favicon match latest version | Old asset in `src/assets/` |

**How to run:**
1. Read Nav + Footer — extract link lists, compare order
2. Per page: confirm kicker, H1, lead, CTA exist
3. Grep for: `example\.com`, `lorem`, `TODO`, `FIXME`, `placeholder`
4. Compare EN/JA pairs for structural symmetry

---

### Browser Agent Checks

**Keep it tight — minimize round-trips:**

1. **Desktop pass (1280×800):** Navigate each route → screenshot → note issues
2. **Mobile pass (375×667):** Resize → re-check key pages → screenshot
3. **Interaction check:** Click primary CTA → verify modal/nav → ESC to close
4. **Modal content check:** Open every modal → screenshot content → verify hierarchy
5. **Console check:** Review errors (ignore dev-only noise)
6. **If QA script provided:** Map findings to QA check IDs

**Tool-specific notes:**
- **Chrome DevTools MCP:** `getDocument` for structure, `getConsoleMessages` for errors, `evaluateScript` for overflow checks.
- **Playwright MCP:** `browser_navigate` already returns a11y tree — never call `browser_snapshot` right after. Use `browser_console_messages` for errors.

**Token discipline:** Navigate → screenshot → move on. Prioritize: homepage, key conversion pages, one i18n page.

**Structural Checks (from accessibility tree):**

| Check | What to Verify |
|-------|----------------|
| **Nav consistency** | Same items on every page |
| **Footer completeness** | All pages, contact, social links |
| **Heading hierarchy** | H1 → H2 → H3, no skipped levels |
| **Link targets** | No dead links |
| **Image alt text** | All `img` have alt |
| **Language toggle** | Maps to correct route |
| **Semantic HTML** | `banner`, `main`, `contentinfo`, `navigation` landmarks |

**Visual Checks (from screenshots):**

| Check | What to Verify |
|-------|----------------|
| **Layout integrity** | No overlapping elements, consistent spacing |
| **Color system** | Consistent tokens, no rogue colors |
| **Typography** | Heading scale intentional, body readable |
| **Responsive** | Content reflows at mobile |
| **Dark/light sections** | Contrast patterns maintained |
| **No AI anti-patterns** | No glassmorphism, no stock imagery |
| **Bilingual balance** | EN vs JA side-by-side comparison |

---

### Visual Polish (Refactoring UI — Cycle 2 focus)

A focused subset of *Refactoring UI* checks. Run after structural checks pass — catches the "correct but not polished" issues.

**Hierarchy & Emphasis:**

| Check | What to Verify |
|-------|----------------|
| **3-level text color** | Primary, secondary, tertiary — not one shade for all |
| **Weight over size** | Hierarchy via font weight + color, not just bigger |
| **De-emphasis over emphasis** | Quiet the competitors, don't shout louder |
| **Button hierarchy** | Primary (solid), secondary (outline), tertiary (link) |
| **Labels de-emphasized** | Data values primary; labels smaller/lighter |
| **Dynamic content hierarchy** | Modals/drawers have visual hierarchy, not uniform text |

**Spacing & Layout:**

| Check | What to Verify |
|-------|----------------|
| **Constrained spacing scale** | 4/8/12/16/24/32/48/64 — no arbitrary values |
| **Enough white space** | If it feels tight, it is tight |
| **Unambiguous grouping** | More space between groups than within |
| **Content width constrained** | Paragraphs 45-75 chars |
| **Not everything full-width** | Sized to content, not stretched |

**Typography:**

| Check | What to Verify |
|-------|----------------|
| **Line-height inversely proportional** | Small text: 1.5-1.75, large headings: 1.0-1.25 |
| **Letter-spacing on all-caps** | Uppercase text has 0.05-0.1em spacing |
| **Headline tracking tightened** | Large headings have tighter tracking |
| **No center-aligned long text** | Center only for ≤2-3 lines |
| **Numbers right-aligned** | Decimal columns right-aligned |

**Color & Contrast:**

| Check | What to Verify |
|-------|----------------|
| **No grey on colored backgrounds** | Use hue-matched lighter color |
| **Saturated greys** | Subtle warm/cool tint |
| **WCAG contrast** | Normal ≥4.5:1, large ≥3:1 |
| **Color not the only signal** | Icon or text too |

**Depth & Borders:**

| Check | What to Verify |
|-------|----------------|
| **Fewer borders** | Prefer shadows, bg differences, or spacing |
| **Shadow system** | Sizes match elevation intent |
| **Consistent border-radius** | One personality per component type |

**Interaction States:**

| Check | What to Verify |
|-------|----------------|
| **Hover states** | Every clickable has visible hover |
| **Focus rings** | Visible keyboard focus |
| **Active/pressed feedback** | Buttons show pressed state |
| **Transition consistency** | Same duration and easing |

---

## Mode: Design Review

Review visual assets (slides, infographics, logos) for design quality, brand consistency, and content accuracy.

**Trigger:** `design`, `design /slides`, `design <path-to-slides-folder>`

**Input:** Path to slides folder. If no path given, review most recently generated slides.

### Agent 1 Focus: Content Accuracy

Read all slide images AND the source content document. Cross-reference:

| Check | What to Look For |
|-------|------------------|
| **Metrics match** | Numbers on slides match source doc exactly |
| **Text accuracy** | Slide text matches spec (no hallucinated content) |
| **Outdated content** | Stale terminology, wrong locations, old pricing |
| **Brand voice** | No corporate-speak, no cliches, practitioner tone |
| **Action titles** | Titles state conclusions, not topic labels |
| **One message per slide** | Each slide communicates exactly one point |
| **Duplicate content** | Same point on multiple slides |
| **Slide redundancy** | Same story in different words — merge or kill one |
| **Narrative flow** | Natural question chain: why us → what → how → let's start |

### Agent 2 Focus: Visual Consistency

Read all slide images. Check for:

| Check | What to Look For |
|-------|------------------|
| **Background consistency** | Same bg color across all slides |
| **Typography hierarchy** | Title/body sizes consistent |
| **Card heights** | Grid cards same height |
| **Color palette adherence** | Only brand colors |
| **Anti-AI aesthetic** | No gradients, glows, decorative elements |
| **Spec text leak** | Font specs or hex codes rendered as visible text |
| **Spacing** | Consistent margins, bottom 80px empty |
| **Text legibility** | No garbled characters |

### Agent 4 Focus: Design Research

Search for design inspiration relevant to the content type:

| Content Type | Search Queries |
|---|---|
| **Consulting slides** | "MBB consulting slide design 2026", "McKinsey presentation best practices" |
| **Technical architecture** | "modern architecture diagram design" |
| **Product/UI** | "SaaS dashboard design trends 2026" |
| **Case studies** | "consulting case study slide layout" |

Return 5-8 actionable improvements with sources. Don't suggest wholesale redesign.

**Skip for:** quick internal drafts, user says "no research" or "quick."

### Design Review Output

```markdown
### Design Review: [folder path]

**Slides reviewed:** [N] | **Source doc:** [path if found]
**Risk tier:** 🟢/🟡/🔴

### Issues Found

🔴 **Must Fix:**
- [slide-XX] [issue description]

🟡 **Consider:**
- [slide-XX] [suggestion]

### Research Findings (Agent 4)
| # | Improvement | Source | Applicable To |
|---|------------|--------|---------------|
| 1 | [specific pattern] | [source] | Slides XX-XX |
(or: "No actionable findings")

### Visual Consistency
| Slide | Background | Typography | Cards/Layout | Text Render | Status |
|-------|-----------|-----------|-------------|------------|--------|
| 01 | ✅ | ✅ | N/A | ✅ | 🟢 |

### Content Accuracy
| Slide | Metrics | Text | Voice | Action Title | Status |
|-------|---------|------|-------|-------------|--------|
| 01 | N/A | ✅ | ✅ | ✅ | 🟢 |

### Verdict
🟢 **Ship it**
— or —
🔴 **Fix [N] issues first**
```

---

## Two-Cycle Output Format

```markdown
## Cycle 1: Issues Found + Fixed

| # | Issue | Severity | Fix Applied | File |
|---|-------|----------|-------------|------|
| 1 | [description] | 🔴/🟡 | [what changed] | file:line |

### Research Findings
- [finding] — [source] — Adopted? ✅/❌ [reason]
(or: "No actionable findings")

### Content Preservation
- [list any important content removed or significantly changed]
(or: "All original content preserved")

### TODO/Requirements Status
- [ ] [requirement 1] — met/not met
- [ ] [requirement 2] — met/not met

---

## Cycle 2: Verification

| # | Original Issue | Verified | New Issues |
|---|---------------|----------|------------|
| 1 | [description] | ✅/🔴 | [any new problems] |

### Flow Check
- [ ] End-to-end flow coherent after fixes
- [ ] No regressions introduced
- [ ] Content preservation verified

### Polish Checks (Cycle 2 only)
[Refactoring UI / mode-specific polish applied]

### Final Verdict
🟢 **Ship it** — [N] issues fixed, [N] verified, [N] polish items
— or —
🔴 **Fix [N] remaining issues**
```

---

## Cleanup

After visual or full review, remove temp artifacts:

```bash
rm -f review-*.png
rm -rf .playwright-mcp/
```

Run silently at end of every visual/full review.

## Rules

- Be specific — quote line numbers for code, screenshot names for visual
- Every finding must have **concrete evidence** (specific lines/files), not speculation
- Suggest fixes, not just problems
- Don't nitpick style if it matches project conventions
- Security and correctness are blockers; style issues are suggestions
- For visual: focus on structural/measurable checks, not subjective aesthetics
- Agent 4 (Research): only adopt findings that are concretely better, verified current, and applicable

---

## Review Log (Research Caching)

Agent 4 (Research) findings are logged to avoid re-running the same searches on subsequent reviews.

**Log location:** Check `your-journal.md` (operational journal) for recent `/review` entries.

**Before launching Agent 4, check the log:** If `your-journal.md` has a recent `/review` entry for the same target (within 7 days), pass those findings to Agent 4 as context. Agent 4 should:
1. Skip searches that were already done and had no actionable findings
2. Only re-search if the previous finding was "adopt" (verify it's still current)
3. Search for NEW hypotheses not covered in the previous run

This prevents redundant web searches when reviewing the same skill/file iteratively.

---

## Scope: /review vs /writing

| Concern | Tool |
|---------|------|
| **Structure & flow** (redundancy, organization, scattered ideas, section ordering) | `/review` — Content Flow checks |
| **Visual formatting** (tables, callouts, hierarchy, whitespace) | `/review` — Obsidian Visual Quality checks |
| **Voice & style polish** (tone, brand voice, tightening prose, em-dashes) | `/writing polish` |
| **Multi-AI creative drafting** (GPT + Gemini + Claude synthesis) | `/writing` |

Both skills use the **Content Preservation Protocol** when editing — catalog before, verify after, never silently delete.
