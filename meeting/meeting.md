---
description: Multi-phase meeting management — one persistent file per company/contact that accumulates all meetings over time
argument-hint: [Company or Person] [YYMMDD] [-- notes to append]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Task, mcp__exa__web_search_exa, mcp__firecrawl__firecrawl_scrape, mcp__firecrawl__firecrawl_search
---

# /meeting

One persistent file per contact that compounds over time. Pre-meeting research, live capture, post-meeting analysis — all in one place.

## OBSIDIAN VISUAL DEFAULTS

- **Scannable in ~10 seconds:** People (`[!quote]+` foldable, starts open) → Meeting Summary (collapsed `[!quote]-` with exec summary, infographic, next steps, meeting history) → (optional) Prep Brief → Latest Meeting (1-pager + agenda at top)
- **Infographic inside Meeting Summary callout** — visible when callout is expanded
- **Generate image first**, then embed (avoid broken links)
- **Checkboxes as state:** `[ ]` pending, `[?]` answered, `[x]` done, `[>]` deferred
- **Collapsible callouts** for transcripts: `> [!info]- Transcript`
- **Callout collapse rules:** Default `[!quote]` (consistent gray). Meeting Summary = collapsed (`[!quote]-`). People = foldable, starts open (`[!quote]+`). Latest Meeting: Overview, Notes, Questions, Should-Ask = all `[!quote]+` (open, foldable). Previous Meetings = each meeting in collapsed `[!quote]-`. Nested "Earlier meetings" inside Summary = `[!quote]-`. Transcript = `[!info]-` (blue — semantic: raw data).
- **Heading-as-link-target pattern:** Callout titles are NOT link targets in Obsidian. When a nav bar links to `[[#Summary]]`, there must be a real `## Summary` heading above the callout. Pattern: `## Summary` (H2 heading for linking) → `> [!quote]- Meeting Summary` (callout for collapsing). Apply to: Summary, Company Profile.
- **No empty sections** — omit if no real content

---

## PERSISTENCE

- **Folder:** `1_meetings/`
- **File path:** `1_meetings/{YYMMDD}-{company-or-person-slug}.md`
- **Assets:** `1_meetings/assets/` (infographics)
- **Dashboard:** `1_meetings/_dashboard.md`
- **Date in filename:** Latest meeting date (chronological sorting)

---

## ARGUMENT PARSING

<meeting_args>
$ARGUMENTS
</meeting_args>

1. **Entity name:** First part before any date or `--`
2. **Date (optional):** 6-digit `YYMMDD`. If absent, use today.
3. **Notes (optional):** Everything after `--`

**Examples:**
- `/meeting Acme Corp` → Entity: "Acme Corp", Date: today
- `/meeting Acme Corp 260130 -- Follow up on partnership` → All three parts

---

## MODE DETECTION

```
Glob: 1_meetings/*-{slug}.md
```

| Condition | Mode | Action |
|-----------|------|--------|
| No file exists | **New Contact** | Create file → Full research |
| File exists, no section for date | **New Meeting** | Rotate latest → history, fresh section, quick update |
| File exists, section for date exists | **Same Meeting** | Append to existing section (no research) |

---

## EXECUTION SEQUENCE

**Key principle:** Show user the file FIRST, then research in background.

```
1. Parse arguments → Detect mode
2. CREATE/UPDATE FILE IMMEDIATELY
3. SHOW USER the file path
4. RUN RESEARCH (if New Contact or New Meeting)
5. APPEND RESEARCH RESULTS
6. GENERATE INSIGHTS (AI) — if substantial meeting content
7. GENERATE INFOGRAPHIC — if substantial content
8. UPDATE DASHBOARD
```

---

## FILE STRUCTURE

### Top-Level Section Order

**First Meeting:**
```
# Company Name
🔗 [website] · [[#People|People]] · [[#Summary|Summary]] · [[#Latest Meeting|Latest]] · [[#Company Profile|Profile]]
📁 {Related files}

> [!quote]+ People      ← Foldable, starts expanded (same gray as Meeting Summary)
## Summary               ← H2 heading (link target) + `[!quote]-` callout below
## Latest Meeting
## Company Profile       ← H2 heading + `[!quote]+` callout below
## Key Sources
## Change Log
```

**Follow-Up Meeting:**
```
🔗 [website] · [[#People|People]] · [[#Summary|Summary]] · [[#Prep Brief|Prep]] · [[#Latest Meeting|Latest]] · [[#Previous Meetings|Previous]] · [[#Company Profile|Profile]]
📁 {Related files — partner, project, deliverables, LOA}

> [!quote]+ People      ← Foldable, starts expanded (same gray as Meeting Summary)
## Summary               ← H2 heading (link target) + `[!quote]-` callout below (exec summary + infographic + next steps)
## Prep Brief            ← Context to remember + platform intel + key decisions
## Latest Meeting
## Previous Meetings     ← Each meeting in its own `[!quote]-` callout (summary + full notes + transcript inside)
## Company Profile       ← H2 heading + `[!quote]+` callout below
## Key Sources
## Change Log
```

### Latest Meeting Subsection Order

Ordered for **live capture** → **pre-meeting prep** → **post-meeting review**:

**Most elements use `[!quote]+` callouts** — consistent gray, foldable, starts expanded. **Exception: Notes uses plain bullets** (no callout) for frictionless live note-taking without exiting reader mode.

| # | Element | Format | Purpose |
|---|---------|--------|---------|
| 0 | **1-Pager** | `![[image]]` | Pre-meeting visual summary; replaced with outcomes post-meeting |
| 1 | **Overview** | `[!quote]+` | Description + agenda + logistics (one box) |
| 2 | **Notes** | `####` + plain bullets | Live note-taking — NO callout (callouts require exiting reader mode to edit) |
| 3 | **Questions & Talking Points** | `[!quote]+` | Must-ask + surface-through-walkthrough + talking points |
| 4 | **Should-Ask (if time)** | `[!quote]+` | Lower-priority questions |
| 5 | **Actions** | `####` | Next steps (user then AI) — `####` for easy editing |
| 6 | **Discussed** | `####` | What was covered, questions answered |
| 7 | **Insights (AI)** | `####` | Post-meeting analysis (generated after transcript/notes) |
| 8 | **Reflection** | `####` | Pre-meeting: template. Post-meeting: auto-populated, moves up to after Notes |
| 9 | **Transcript** | `[!info]-` | Full record (collapsed) |

**Post-meeting reorder:** After transcript/substantial notes, Reflection moves up to position 3 (after Notes, before Questions). The 1-pager is also regenerated with outcomes. This surfaces the most important post-meeting content at the top.

### Conditional Section Rules

| Section | First Meeting | Follow-Up |
|---------|:---:|:---:|
| People | ✅ (`[!quote]+` — open, foldable) | ✅ (`[!quote]+` — open, foldable, update if new attendee) |
| Summary | `## Summary` heading + `[!quote]-` callout (exec summary + infographic) | Full (+ Next Steps + Open Questions + Meeting History) |
| Prep Brief | ❌ | ✅ |
| Latest Meeting | ✅ | ✅ (fresh template) |
| Previous Meetings | ❌ | ✅ — each meeting in its own `[!quote]-` callout (summary + full notes + transcript all inside one box) |
| Company Profile | ✅ (`## Company Profile` heading + `[!quote]+` callout) | ✅ (update if needed) |

**Critical:** Never show placeholder sections. If no real content, omit entirely.

---

## CONTENT CONVENTIONS

### User vs AI Content

Separate sections, user first. Pattern: `{Section name}` for user, `{Section name} (AI)` for AI.

```markdown
> [!quote]+ Questions & Talking Points
> **Must-ask:**
> 1. Your question
>
> **Must-ask (AI):**
> 1. AI suggested question
>
> **Talking points:**
> - Your talking point
>
> **Talking points (AI):**
> - AI suggested point
```

### Source Hyperlinks in AI Items

For `(AI)` sections, **add inline hyperlinks to non-obvious claims** so the user can verify.

**Add links for:** specific facts/stats, events/announcements, background claims, named entities.
**Skip links for:** obvious questions, info already in the file, no reliable URL.

```markdown
- Your [LinkedIn post](https://...) mentioned 0.5x AI usage — what's driving that?
- [ ] [Digital Garden Summit](https://...) coming up — what are you speaking about?
- What does "moving beyond PoC purgatory" look like? ([ref: founding post](https://...))
```

### Checkbox Conventions

| Syntax | Use | Appearance |
|--------|-----|------------|
| `- [ ]` | Pending / unanswered | Empty |
| `- [?]` | Answered (readable) | Checked, **no strikethrough** |
| `- [x]` | Completed | Checked, subtle fade |
| `- [>]` | Deferred | Arrow, de-emphasized |

### Questions Formatting

- **4+ questions:** Group by topic with bold headers
- **<4 questions:** Flat bullet list

### People Formatting

People section uses `[!quote]+` — foldable, starts expanded, same gray as Meeting Summary.

```markdown
> [!quote]+ People
>
> ### Person Name
> **Title** · [LinkedIn](url)
>
> > Background line 1
> > Background line 2

📅 First meeting: YYYY-MM-DD
```

---

## TEMPLATES

### First Meeting (New Contact)

```markdown
---
title: Meetings — {Company/Person} ({YYMMDD})
entity: {Company or Person name}
entity_type: company | person
created: YYYY-MM-DD
latest_meeting: YYYY-MM-DD
meeting_count: 1
relationship: prospect | partner | client | vendor | other
next_meeting: YYYY-MM-DD  # optional
cssclass: meeting-note
tags: [meetings, {industry}]
---

# {Company/Person}

🔗 [{domain}]({url}) · [[#People|People]] · [[#Summary|Summary]] · [[#Latest Meeting|Latest]] · [[#Company Profile|Profile]]
📁 {Related files — [[partner meeting file\|Partner]], [[project files\|Project]], [[deliverables\|Deliverable]] as applicable}

---

> [!quote]+ People
>
> ### {Person Name}
> **{Title}** · [LinkedIn]({url})
>
> > {Background}
>
> 📅 First meeting: {YYYY-MM-DD}

---

## Summary

> [!quote]- Meeting Summary
>
> ![[1_meetings/assets/{YYMMDD}-{slug}-summary.png]]
>
> #### Executive Summary
>
> **Engagement:** {What we're doing, fee, timeline, status}
>
> **What we've built:** {Deliverables with [[wikilinks]], research done, new intel — link to key files}
>
> **What's next:** {Next meeting/milestone, key questions to resolve}
>
> **Our edge:** {Sharpest positioning angle with specific numbers}
>
> ---
>
> #### Meeting History
> *(reverse chronological — last 3 visible, older entries folded)*
>
> - **{Date} — [[#Latest Meeting\|Next meeting]]:** {Purpose, who's attending.} ← Next
> - **{Date} — [[#section\|Meeting label]]:** {2-3 sentence summary.}
> - **{Date} — [[other-file#section\|Partner: label]]:** {Same detail level.}
>
> > [!quote]- Earlier meetings ({N} more)
> > - **{Date} — [[link\|Label]]:** {Summary.}
> > - **{Date} — [[link\|Label]]:** {Summary.}
>
> ---
>
> #### Next Steps
> <!-- Chronological — soonest first -->
> - [ ] {Action item} (~{M/DD})
>
> #### Open Questions
> - [ ] {Question}

---

## Latest Meeting

### {YYYY-MM-DD} — {Brief Topic}

![[1_meetings/assets/{YYMMDD}-{slug}-meeting.png]]

> [!quote]+ Overview
> **{Mon DD}** · {Platform} · {Attendees}
> *{Purpose}*
>
> **Agenda**
> - **{Item 1}** — {Description}
> - **{Item 2}** — {Description}
> - **{Item 3}** — {Description}
>
> **Logistics:** {1-line abbreviated: key status items separated by · }

#### Notes
-

> [!quote]+ Questions & Talking Points
> **Must-ask:**
> 1. {Question}
>
> **Must-ask (AI):**
> 1. {AI question}
>
> **Talking points:**
> - {Point}
>
> **Talking points (AI):**
> - {AI point}

> [!quote]+ Should-Ask (if time)
> {Lower-priority questions}

#### Actions
**Mine**
- [ ]

**Mine (AI)**
- [ ] {AI task}

**Theirs (AI)**
- [ ] {AI task}

#### Discussed
**Questions answered:**
- [?] {Question} → *{Answer}*

**Key topics:**
- {Topic}

#### Insights (AI)
{Post-meeting analysis — generated after notes/transcript appended}

#### Reflection
**How it went:** 🟢 / 🟡 / 🔴
**What worked:**
**To improve:**

> [!info]- Transcript
> {Paste here}

---

## Company Profile

> [!quote]+ Company Profile
>
> ![[1_meetings/assets/{YYMMDD}-{slug}-profile.png]]
>
> | | |
> |---|---|
> | **What** | {Description} |
> | **Size** | {Employees/size} |
> | **HQ** | {Location} |
> | **Founded** | {Year} |
>
> **Recent News**
>
> | Date | Development |
> |------|-------------|
> | {Mon YYYY} | {Event} — [source]({url}) |

---

## Key Sources

**Note:** Escape `|` in wikilinks inside tables: `[[path\|Display]]` (backslash before pipe).

| Source | Link |
|--------|------|
| Website | [{domain}]({url}) |
| LinkedIn | [Company]({url}) |

---

## Change Log

- {YYYY-MM-DD}: Created for {purpose}
```

### Follow-Up Meeting (Additional Sections)

```markdown
## Summary

> [!quote]- Meeting Summary
>
> ![[1_meetings/assets/{YYMMDD}-{slug}-summary.png]]
>
> #### Executive Summary
>
> **Engagement:** {What we're doing, fee, timeline, status}
>
> **What we've built:** {Deliverables with [[wikilinks]], research done, new intel — link to key files}
>
> **What's next:** {Next meeting/milestone, key questions to resolve}
>
> **Our edge:** {Sharpest positioning angle with specific numbers}
>
> ---
>
> #### Meeting History
> *(reverse chronological — last 3 visible, older entries folded)*
>
> - **{Date} — [[#Latest Meeting\|Next meeting]]:** {Purpose, who's attending.} ← Next
> - **{Date} — [[#section\|Meeting label]]:** {2-3 sentence summary.}
> - **{Date} — [[other-file#section\|Partner: label]]:** {Same detail level.}
>
> > [!quote]- Earlier meetings ({N} more)
> > - **{Date} — [[link\|Label]]:** {Summary.}
> > - **{Date} — [[link\|Label]]:** {Summary.}
>
> ---
>
> #### Next Steps
> <!-- Chronological — soonest first -->
> - [ ] {Action item} (~{M/DD})
>
> #### Open Questions
> - [ ] {Question}

---

## Prep Brief

### Follow-Up Items
- {Open action from previous meeting}

### Context to Remember
- {Key point from last meeting}

---

## Previous Meetings

Reverse chronological — each meeting in its own `[!quote]-` callout. Summary at top, full notes below separator, transcript nested at bottom.

> [!quote]- {Mon DD} — {Topic} ({emoji})
>
> ![[1_meetings/assets/{YYMMDD}-{slug}-meeting.png]]
>
> **{Mon DD}** · {Platform} · {Attendees}
> *{Purpose}*
>
> **Key outcomes:** {2-3 sentences}
> **What we learned:** {3-5 bullets}
> **Open items carried forward:** {comma-separated list}
>
> ---
>
> **Full Notes:**
> {Detailed notes, actions, questions answered}
>
> **Insights (AI):**
> {Post-meeting analysis}
>
> > [!info]- Transcript
> > {link or content}

> [!quote]- {Earlier Date} — {Topic} ({emoji})
>
> {Same structure — summary + full notes + transcript all in one callout}
```

---

## AI MEETING INSIGHTS

### Executive Summary (in Meeting Summary)

Every meeting file gets an **Executive Summary** inside the `[!quote]- Meeting Summary` callout (under `## Summary`), above the infographic.

**Structure:** `## Summary` heading (link target) → `> [!quote]- Meeting Summary` collapsed callout containing 4 bold-labeled fields + meeting timeline:
1. **Engagement:** Who, what, fee, timeline, status
2. **What we've built:** Deliverables with `[[wikilinks]]` to key files, research, new intel
3. **What's next:** Next meeting/milestone, pending questions
4. **Our edge:** Sharpest positioning with specific numbers
Plus `#### Meeting History` (reverse chronological, last 3 visible, older in nested `> [!quote]- Earlier meetings (N more)` callout), `#### Next Steps`, `#### Open Questions`.

**Omit sections that don't apply** (e.g., first meeting has no "What we've built"). Keep each section to 1-3 sentences. Use `[[wikilinks]]` for deliverables and `[[#heading]]` links for meeting history so everything is clickable in Obsidian.

**When to write/update:**
- **New Contact:** Write initial summary from research + meeting purpose
- **New Meeting:** Update with latest outcomes + upcoming context
- **Post-transcript:** Rewrite to reflect actual meeting outcomes (not just prep assumptions)

**Style:** Bold-labeled sections with 1-3 sentences each (not flowing prose). A reader who opens this file cold should understand the full situation in 30 seconds. Concrete numbers and dates over vague status updates. Use `[[wikilinks]]` for deliverables and `[[#heading]]` links for meeting history.

---

Generate `#### Insights (AI)` after substantial meeting content is appended.

### When to Generate

| Trigger | Action |
|---------|--------|
| Substantial meeting notes appended | Generate Insights + populate Reflection prompts |
| Transcript pasted | Generate/regenerate Insights + populate Reflection prompts |
| Manual request (`-- regenerate insights`) | Generate |
| Light append (single line) | Skip |

**"Substantial":** ≥3 discussion topics, OR structured outcomes/actions, OR transcript.

### Content: 3-5 sentences covering ≥2 of 4 dimensions

1. **Meeting Performance** — How the presenter came across. Positioning, credibility, question quality, power dynamics, rapport. Be specific, not generic praise.

2. **Strategic Observations** — What wasn't said, what was implied. Gaps between stated and real priorities. Timing/urgency signals. Competitive dynamics.

3. **Missed Opportunities** — Prep questions not covered. Follow-up threads not pulled. Information asymmetries not leveraged.

4. **Next Interaction Suggestions** — What to lead with. Concrete value to provide before next meeting. Relationship dynamic to nurture.

### Format

Flowing prose, no headers or bullets. Reads like a trusted advisor's candid debrief.

```markdown
#### Insights (AI)

The collaboration framing landed well — positioning bilingual prototyping as complementary to their scaling capacity avoids competition. Their internal tools (AI recruiting, VC due diligence) could be a low-stakes first project to build trust. The "12 directions simultaneously" signals pre-PMF — they won't prioritize a partnership without a concrete deal on the table. Lead with a specific project opportunity next time.
```

### Reflection (Auto-Populated After Transcript)

When a transcript or substantial notes are appended, **auto-populate the Reflection section** with AI-generated prompts based on the actual meeting content. Don't leave the generic template — replace it with specific, actionable reflection questions.

**Template (before transcript):**
```markdown
#### Reflection
**How it went:** 🟢 / 🟡 / 🔴
**What worked:**
**To improve:**
```

**After transcript/notes appended, replace with:**
```markdown
#### Reflection
**How it went:** 🟢 / 🟡 / 🔴

**What worked:**
- {AI-generated: specific moment from the meeting that landed well}
- {AI-generated: positioning or framing that was effective}

**To improve:**
- {AI-generated: specific question or topic that could have been pushed further}
- {AI-generated: prep gap or missed opportunity from the transcript}

**For next time:**
- {AI-generated: 1-2 concrete things to do differently or follow up on}
```

The user fills in `🟢 / 🟡 / 🔴` and edits/adds to the AI-generated bullets. The AI prompts give them something to react to instead of a blank page.

---

## RESEARCH WORKFLOW

### New Contact (Full Research)

**Parallel agents recommended:**

| Agent | Tool | Query |
|-------|------|-------|
| Company Overview | `mcp__exa__web_search_exa` | "{company} overview what they do" |
| Key People | `mcp__exa__web_search_exa` | "{person} {company} LinkedIn" |
| LinkedIn Profiles | Bright Data (Bash) | Full profile data |
| Recent News | `mcp__firecrawl__firecrawl_search` | "{company} news 2026" with `tbs: "qdr:m"` |
| Deep Read | `mcp__firecrawl__firecrawl_scrape` | Company website |

**LinkedIn via Bright Data:**

```bash
cd "$(git rev-parse --show-toplevel)" && \
  set -a && source .env && set +a && \
  python3 ./scripts/brightdata_linkedin.py \
    --url "https://www.linkedin.com/in/{username}"
```

Other variants: `--urls urls.txt` (batch), `--type company` (company profile).

**Bright Data vs Exa:** Exa gets name/headline. Bright Data gets full work history, education, languages, awards, projects, network signals. **Always try Bright Data first for meeting prep.**

**Fallback:** If Bright Data returns an error or empty payload, fall back to Exa search: `mcp__exa__web_search_exa` with query `"{person} {company} site:linkedin.com"` (numResults: 5). This recovers name, title, and headline from LinkedIn's indexed metadata.

**Minimum research targets:** Company profile, key person profiles (Bright Data), recent news (6 months), 5+ sources.

### New Meeting (Quick Update)

1. **Backfill infographic** — if previous meeting lacks an infographic, generate one via `/slides` before rotating
2. Move "Latest Meeting" → "Previous Meetings" (own `[!quote]-` callout with summary + full notes + transcript) + add entry to Meeting History timeline inside Summary callout
3. Generate "Prep Brief" from open items + recent news
4. Create fresh "Latest Meeting" section
5. Update Executive Summary callout with latest context + new meeting history entry
6. Rename file: `mv` old → `{new-YYMMDD}-{slug}.md` (preserves content, updates date for sorting)
7. Update frontmatter: `latest_meeting`, `meeting_count`, title
8. Update cross-references in other files that link to the old filename

### Same Meeting (Append Only)

Append content to appropriate subsection via pattern matching:

| Pattern | Target |
|---------|--------|
| "ask about", "discuss", "point:", "talk about" | Questions & Talking Points > Talking points |
| "question:", "?", "ask:" | Questions & Talking Points > Must-ask |
| "action:", "todo:", "send", "schedule" | Actions > Mine |
| "they will", "they committed", "they agreed" | Actions > Theirs |
| "reflection:", "how it went" | Reflection |
| "transcript:", "granola" | Transcript (collapsed `> [!info]- Transcript`) |
| Default | Notes |

---

## INFOGRAPHIC GENERATION

Uses `/slides` (Gemini 3 native image gen). If Gemini API fails, skip infographic generation and note "Infographic skipped: Gemini API unavailable" in the Change Log.

### Three Types of Infographic

| Type | Filename | Location | Purpose |
|------|----------|----------|---------|
| **Meeting Summary** | `{YYMMDD}-{slug}-summary.png` | Inside `[!quote]- Meeting Summary` callout | Cumulative engagement overview |
| **Per-Meeting 1-Pager** | `{YYMMDD}-{slug}-meeting.png` | Top of Latest Meeting (after heading, before Overview) | Visual snapshot of this specific meeting |
| **Company Profile** | `{YYMMDD}-{slug}-profile.png` | Inside `[!quote]+ Company Profile` callout | Company snapshot — generate when Profile section is substantial (≥20 lines) |

**Per-Meeting 1-Pager lifecycle:**
1. **Pre-meeting (at setup):** Generated with agenda, key questions, attendees, context. Shows what's about to happen.
2. **Post-meeting (after transcript/notes):** Regenerated with actual outcomes, decisions, action items. Shows what happened.
3. **When rotated to Previous Meetings:** Stays as-is — the post-meeting version becomes the permanent record.

### When to Generate

| Scenario | Summary Infographic | Per-Meeting 1-Pager |
|----------|:---:|:---:|
| First meeting, light notes | Skip | Generate (pre-meeting) |
| First meeting, substantial (≥3 topics OR ≥2 outcomes) | Generate | Generate (pre-meeting) |
| Follow-up meeting | Update (cumulative) | Generate (pre-meeting) |
| Transcript/notes added | Regenerate | Regenerate (post-meeting outcomes) |
| New Meeting mode (rotating latest → history) | Update | Backfill previous if missing |

**Every meeting gets a 1-pager.** Even light first meetings — the pre-meeting version with agenda/questions is still useful. When transcript or substantial notes come in, regenerate with actual outcomes.

### Storage & Embedding

- **Summary path:** `1_meetings/assets/{YYMMDD}-{slug}-summary.png`
- **Summary embed:** `![[1_meetings/assets/{YYMMDD}-{slug}-summary.png]]` inside the `[!quote]- Meeting Summary` callout
- **Per-meeting path:** `1_meetings/assets/{YYMMDD}-{slug}-meeting.png`
- **Per-meeting embed:** `![[1_meetings/assets/{YYMMDD}-{slug}-meeting.png]]` at top of Latest Meeting section (after heading, before Overview callout)

### Generation Command

```bash
cd "$(git rev-parse --show-toplevel)" && \
  set -a && source .env && set +a && \
  python3 ./scripts/gemini_slides.py \
    --prompts '[{"filename": "{YYMMDD}-{slug}-summary.png", "prompt": "..."}]' \
    --output 1_meetings/assets/ \
    --direct
```

### Prompt Style

16:9 landscape, warm white (#FAFAF9) background, dark slate (#1E293B) text, warm slate (#64748B) accents. Minimal, text-forward, no illustrations. Content: company snapshot, meeting highlights, open actions, status.

---

## DASHBOARD UPDATE

After **New Contact** or **New Meeting** (not Same Meeting appends):

1. Scan all `1_meetings/*.md` (except `_dashboard.md`)
2. Extract frontmatter: `entity`, `latest_meeting`, `next_meeting`, `relationship`, `meeting_count`
3. Extract content: action items, key outcomes
4. Rebuild tables: Upcoming, Recent (7 days), Actions (mine + theirs), All Contacts

---

## TOOL PARAMS (meeting-specific)

Tool hierarchy follows CLAUDE.md. Meeting-specific optimal params:

**Exa:** `numResults: 10`, `type: "auto"`, `livecrawl: "preferred"`, `contextMaxCharacters: 12000`
**Firecrawl scrape:** `maxAge: 86400000`, `onlyMainContent: true`, `formats: ["markdown"]`, `proxy: "auto"`

---

## SLUG GENERATION

Lowercase → replace spaces with hyphens → remove special chars (keep `a-z0-9-`) → collapse multiple hyphens → trim ends.

Examples: "Acme Corp" → `acme-corp` · "Digital Vorn (Japan)" → `digital-vorn-japan`

---

## PRE-OUTPUT VALIDATION

- [ ] File created/updated in `1_meetings/`
- [ ] Frontmatter complete (entity, latest_meeting, meeting_count)
- [ ] Appropriate section updated based on mode
- [ ] Dashboard updated
- [ ] Research appended (if New Contact or New Meeting)
- [ ] Key Sources has actual URLs
- [ ] Insights (AI) generated (if substantial content)
- [ ] Per-meeting 1-pager generated (always — pre-meeting with agenda/questions)
- [ ] Summary infographic generated/updated (if substantial content)
- [ ] Company Profile infographic generated (if Profile section ≥20 lines)
- [ ] Executive Summary callout updated with current context
- [ ] Reflection auto-populated (if transcript/notes appended)
- [ ] Previous meeting infographic backfilled (if missing, New Meeting mode)
- [ ] File renamed with correct date (New Meeting mode)
- [ ] Cross-references updated in other files pointing to old filename
- [ ] Nav bar present at top (`🔗` in-file links + `📁` related files)
- [ ] Change Log updated with today's action

---

## SYNC NOTE

`skills/meeting/references/meeting.md` is a synced copy of this spec.

