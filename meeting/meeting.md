---
description: Multi-phase meeting management — one persistent file per company/contact that accumulates all meetings over time
argument-hint: [Company or Person] [YYMMDD] [-- notes to append]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Task
---

# /meeting

Multi-phase meeting management with persistent per-contact files. Like a CRM contact record — one file per relationship that grows over time.

## OBSIDIAN VISUAL DEFAULTS (read this first)

**Goal:** When you open the note in Obsidian, the top should be scannable in ~10 seconds, while the full detail is still preserved further down.

- **Keep "Action Center" near the top:** `## People` → `## Meeting Summary` → (optional) `## Prep Brief` → `## Latest Meeting`.
- **Visual summary should be visible fast:** embed the image **at the top of `## Meeting Summary`**, expanded by default (no collapsed callout).
- **Avoid broken embeds:** generate the image first; only insert the embed once the asset exists.
- **Use checkboxes as state:** `- [ ]` for open items/questions, `- [?]` for answered questions (readable), `- [x]` for done, `- [>]` for intentionally deferred.
- **Put long text behind collapsible callouts:** transcripts always go in `> [!info]- Transcript`.
- **No empty sections:** if a section has no real content in this mode, omit it entirely.

## VALUE PROPOSITION

**The problem I was solving:**
Before every meeting, I'd open 10+ tabs — LinkedIn profiles, company website, CrunchBase, recent news — copy-pasting snippets into notes. By meeting #2 with the same person, I'd forgotten half of what we discussed.

**What actually changed:**
- **One persistent file per contact** (the note compounds over time)
- **Prep Brief** surfaces unfinished business before the next meeting
- **Fast append** means I actually keep the file up to date (before/after meetings)

**The specific tools:**
- **Exa semantic search** — finds company context that keyword search misses
- **Firecrawl** — scrapes company pages for deep reading
- **Gemini 3.0** — generates visual meeting summaries for quick reference

<!-- CUSTOMIZE: Add your own discovery tools (LinkedIn API, CrunchBase, etc.) -->

## PERSISTENCE (required)

- **Folder:** `1_meetings/`
- **File path:** `1_meetings/{YYMMDD}-{company-or-person-slug}.md`
- **Assets:** `1_meetings/assets/` (infographics)
- **Dashboard:** `1_meetings/_dashboard.md` (aggregated view)
- **Date in filename:** Latest meeting date (enables chronological sorting)

<!-- CUSTOMIZE: Change folder paths to match your project structure -->

## ARGUMENT PARSING

<meeting_args>
$ARGUMENTS
</meeting_args>

**Parse the arguments:**
1. **Entity name:** First part before any date or `--` (e.g., "Acme Corp", "Jane Doe")
2. **Date (optional):** 6-digit `YYMMDD` format (e.g., `260130`). If absent, use today's date.
3. **Notes (optional):** Everything after `--` is content to append

**Examples:**
- `/meeting Acme Corp` → Entity: "Acme Corp", Date: today, Notes: none
- `/meeting Acme Corp 260130` → Entity: "Acme Corp", Date: 2026-01-30, Notes: none
- `/meeting Acme Corp -- Ask about Q2 roadmap` → Entity: "Acme Corp", Date: today, Notes: "Ask about Q2 roadmap"
- `/meeting Acme Corp 260130 -- Follow up on partnership` → All three parts

---

## MODE DETECTION (Auto-Detected)

Check for existing file:
```
Glob: 1_meetings/*-{slug}.md
```

| Condition | Mode | Action |
|-----------|------|--------|
| No file for this entity | **New Contact** | Create file → Full research appends |
| File exists, no section for specified date | **New Meeting** | Add meeting section → Quick update appends |
| File exists, section for specified date exists | **Same Meeting** | Append to existing section (no research) |

---

## EXECUTION SEQUENCE

**Key principle:** Show user the file FIRST, then research in background.

```
1. Parse arguments → Detect mode
2. CREATE/UPDATE FILE IMMEDIATELY
   - New Contact: Create file with template
   - New Meeting: Rotate latest → history, create fresh section
   - Same Meeting: Append content to appropriate subsection
3. SHOW USER the file path (they can start using it)
4. RUN RESEARCH (if needed)
   - New Contact: Full company/person research
   - New Meeting: Quick news update + generate Prep Brief
   - Same Meeting: No research
5. APPEND RESEARCH RESULTS to file
6. GENERATE INFOGRAPHIC (if substantial content)
7. UPDATE DASHBOARD (scan all meeting files, rebuild tables)
```

---

## FILE STRUCTURE TEMPLATE

### Section Order (Action-Oriented)

When you return to a meeting file, the most useful info should be visible first:

**First Meeting (New Contact):**
```
# Company Name
[links] · [[#People|People]] · [[#Meeting Summary|Summary]] · [[#Latest Meeting|Latest Meeting]]

## People                    ← Who you're meeting (at top)
## Meeting Summary           ← Executive brief + infographic
## Latest Meeting            ← Current meeting details
## Profile                   ← Company background
## Key Sources
## Change Log
```

**Follow-Up Meeting (Existing Contact):**
```
# Company Name
[links] · [[#People|People]] · [[#Meeting Summary|Summary]] · [[#Prep Brief|Prep Brief]] · [[#Latest Meeting|Latest Meeting]]

## People
## Meeting Summary           ← Updated executive brief
## Prep Brief               ← Follow-ups + what to remember before this meeting
## Latest Meeting            ← Current meeting details
## Previous Summary          ← Quick reference to last meeting
## Profile
## Meeting History           ← Full archive
## Key Sources
## Change Log
```

### Latest Meeting Subsection Order

Within Latest Meeting, ordered for **live capture** → **pre-meeting prep** → **post-meeting review**:

| Position | Section | Purpose |
|----------|---------|---------|
| 1 | **Notes** | Live note-taking — first thing you see for easy capture |
| 2 | **My Prep** | What you planned to cover (pre-meeting) |
| 3 | **Actions** | Next steps — most actionable info |
| 4 | **Reflection** | Self-feedback (post-meeting) |
| 5 | **Discussed** | What was covered (reference) |
| 6 | **Pre-Meeting Context** | Background captured before meeting (travel, logistics) |
| 7 | **Transcript** | Full record (collapsed callout) |

### User vs AI Content

Use separate sections (not individual markers) to distinguish user-added vs AI-generated. **Group all user content first, then all AI content** — so the user can scan their own prep at a glance before seeing AI suggestions:

```markdown
#### My Prep
**Questions I want to ask**
- Your question here
- Another question

**Talking points**
- [ ] Your talking point

**Questions I want to ask (AI)**
- AI suggested question
- Another AI suggestion

**Talking points (AI)**
- [ ] AI suggested point
```

**Pattern:** `{Section name}` for user content, `{Section name} (AI)` for AI suggestions. Same for Talking points, Actions, etc. **Order: all user sections first, then all AI sections.** User sections can be empty if user provided nothing — still show them for easy adding later.

### First Meeting Template (New Contact)

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

🔗 [{domain}]({url}) · [[#People|People]] · [[#Meeting Summary|Summary]] · [[#Latest Meeting|Latest Meeting]]

---

## People

### {Person Name}
**{Title}** · [LinkedIn]({url})

> {Background line 1 — credentials, prev companies}
> {Background line 2 — location, personal notes}

📅 First meeting: {YYYY-MM-DD}

---

## Meeting Summary

### At a Glance
| | |
|---|---|
| Meetings | 1 ({Mon DD}) |
| Relationship | {Status} |

<!-- For first meetings: Only show At a Glance. Add Next Steps/Open Questions after meeting when there's real content. -->

---

## Latest Meeting

### {YYYY-MM-DD} — {Brief Topic/Purpose}
> **{Mon DD}** · {Platform} · {Attendees}
> *{Purpose — 1 sentence}*

#### Notes
-

#### My Prep
**Questions I want to ask**
-

**Talking points**
- [ ]

**Questions I want to ask (AI)**
- {AI suggested question}

**Talking points (AI)**
- [ ] {AI suggested point}

#### Actions
**Mine**
- [ ]

**Mine (AI)**
- [ ] {AI suggested task}

**Theirs (AI)**
- [ ] {AI suggested task}

#### Discussed
**Questions answered:**
- [?] {Question} → *{Answer}*

**Key topics:**
- {Topic}

#### Reflection
**How it went:** 🟢 / 🟡 / 🔴
**What worked:** {Brief}
**To improve:** {Brief}

#### Pre-Meeting Context
{Travel, logistics, background notes}

> [!info]- Transcript
> {Paste here}

---

## Profile

| | |
|---|---|
| **What** | {Description} |
| **Size** | {Employees/size} |
| **HQ** | {Location} |
| **Founded** | {Year} |

### Recent News

| Date | Development |
|------|-------------|
| {Mon YYYY} | {Event} — [source]({url}) |

---

## Key Sources

| Source | Link |
|--------|------|
| Website | [{domain}]({url}) |
| LinkedIn | [Company]({url}) |

---

## Change Log

- {YYYY-MM-DD}: Created for {purpose}
```

### Follow-Up Meeting Template (Existing Contact)

Additional sections to include when file already exists:

```markdown
## Meeting Summary

<!-- After generating the infographic, insert the embed here (expanded). -->
![[1_meetings/assets/{YYMMDD}-{slug}-summary.png]]

### At a Glance

| | |
|---|---|
| Meetings | {N} ({dates}) |
| Relationship | {Status} |
| Last discussed | {Key topics} |

<!-- Next Steps and Open Questions: Only add when there's real content from previous meetings -->
### Next Steps
- [ ] {Real action item from meeting}

### Open Questions
- [ ] {Real question to ask them}

---

## Prep Brief

### Follow-Up Items
- {Open action item from previous meeting}
- {Unresolved topic}

### Context to Remember
- {Key point from last meeting}
- {Personal detail they shared}

---

## Previous Summary

**{YYYY-MM-DD}** — {Topic}

**Key outcomes:**
- {Main decision/discussion}

**Open items:**
- {Unchecked action items}

---

## Meeting History

> [!note]- {YYYY-MM-DD} — {Topic}
> > **{Mon DD}** · {Platform} · {Attendees}
> > *{Purpose — 1 sentence}*
>
> **Key outcomes:**
> - {Outcome 1}
> - {Outcome 2}
>
> **Actions:**
> - [ ] {Open item}
>
> **Notes:**
> {Detailed notes here}
```

### Conditional Section Rules

| Section | First Meeting | Follow-Up Meeting |
|---------|---------------|-------------------|
| People | Show | Show (update if new attendee) |
| Meeting Summary | At a Glance only | Full (with Next Steps/Open Questions) |
| Prep Brief | Omit | Show with real content |
| Latest Meeting | Show | Show (fresh template) |
| Previous Summary | Omit | Show with real content |
| Profile | Show | Show (update if needed) |
| Meeting History | Omit | Show with archived meetings |
| Key Sources | Show | Show |
| Change Log | Show | Show |

**Critical rules:**
- Never show placeholder sections. If no real content, omit entirely.
- **First meetings:** Meeting Summary only has "At a Glance" table. Add Next Steps/Open Questions after meeting when there's real content.
- **AI markers:** Add `(AI)` suffix to AI-generated items in My Prep, Actions, etc. User-added content has no marker.

### Checkbox Conventions

| Syntax | Meaning | Visual Appearance |
|--------|---------|-------------------|
| `- [ ]` | Pending task / unanswered question | Empty checkbox |
| `- [?]` | Answered question (readable) | Filled checkbox, **no strikethrough** |
| `- [x]` | Completed action item | Filled checkbox, subtle fade |
| `- [>]` | Deferred / moved | Arrow indicator, de-emphasized |

**Critical:** Use `[?]` for answered questions so the answer remains readable. Use `[>]` when you intentionally move/defer an item but want it to remain visible without looking "done".

Example:
```markdown
#### Discussed

**Questions answered:**
- [?] What's the pricing model? → *Mid-market $25-80k, enterprise low-mid 6 figures*
- [?] How does deal sourcing work? → *Consultative: identify top 3 ROI opportunities*
- [ ] What happens to the IP? *(not covered)*
```

### Questions Formatting

**4+ questions:** Group by topic with bold headers, use bullets
```markdown
#### My Prep

**Questions I want to ask:**

**Business Model**
- How does deal sourcing work?
- What's the pricing model?

**Operations**
- What's the team structure?
- How long are projects typically?
```

**<4 questions:** Keep flat bullet list (no grouping needed)
```markdown
#### My Prep

**Questions I want to ask:**
- How does deal sourcing work?
- What's the team structure?
```

### People Section Formatting

**Inline format (not tables):**
```markdown
### {Person Name}
**{Title}** · [LinkedIn]({url})

> {Background — credentials, previous companies}
> {Location, personal notes}

📅 Met: {YYYY-MM-DD} (intro call)
```

### Quick Ref Formatting

**Compact blockquote (not table):**
```markdown
> **{Mon DD}** · {Platform} · {Attendees}
> *{Purpose — 1 sentence}*
```

---

## RESEARCH WORKFLOW

### New Contact (Full Research)

**Trigger:** No `1_meetings/*-{slug}.md` file exists

**Research scope (parallel agents recommended):**

| Agent | Tool | Query |
|-------|------|-------|
| Company Overview | Semantic search (Exa or similar) | "{company} overview what they do" |
| Key People | Semantic search | "{person name} {company}" |
| Recent News | Web search (Firecrawl or similar) | "{company} news {year}" with recency filter |
| Deep Read | Page scraper (Firecrawl or similar) | Company website, about page |

<!-- CUSTOMIZE: Add people-research tools here (CrunchBase, Proxycurl, etc.) -->

**Minimum research targets:**
- Company profile (what they do, size, HQ, funding)
- Key person profiles (title, background)
- Recent news (past 6 months)
- 5+ sources cited in Key Sources

### New Meeting (Quick Update + Prep Brief)

**Trigger:** File exists, but no meeting section for specified date

**Actions:**
1. Move current "Latest Meeting" content to "Meeting History" (at top, newest first)
2. Update "Previous Summary" with key outcomes from moved meeting
3. **Generate "Prep Brief"** based on:
   - Open action items from previous meeting
   - Topics that were left unresolved
   - Personal notes about attendees
   - Recent company news (quick search)
4. Create fresh "Latest Meeting" section with template
5. Rename file with new date: `{YYMMDD}-{slug}.md`
6. Update frontmatter: `latest_meeting`, `meeting_count`, title

**Quick news search:**
```
Semantic search: "{company} news after:{latest_meeting_date}"
```

### Same Meeting (Append Only)

**Trigger:** File exists AND section for specified date exists

**Action:** Append content to appropriate subsection based on pattern matching (see below)

---

## APPEND LOGIC

When `-- <text>` is provided, route to appropriate section:

| Text Pattern | Target Section |
|--------------|----------------|
| "ask about", "discuss", "mention", "point:", "talk about" | Latest Meeting > My Prep > Talking points |
| "question:", "?" at end, "ask:" | Latest Meeting > My Prep > Questions I want to ask |
| "action:", "todo:", "follow-up:", "send", "schedule", "prepare" | Latest Meeting > Actions > Mine |
| "they will", "they committed", "they agreed", "they promised" | Latest Meeting > Actions > Theirs |
| "reflection:", "how it went", "what worked", "to improve" | Latest Meeting > Reflection |
| "transcript:", "[paste]" | Latest Meeting > Transcript (collapsed callout) |
| Default (no pattern match) | Latest Meeting > Notes |

**Format when appending:**
- Talking points: `- [ ] {text}`
- Questions: `- {text}`
- Actions: `- [ ] {text} — Due: {date if mentioned}`
- Notes: `- {text}` or paragraph

---

## DASHBOARD UPDATE

After a **New Contact** or **New Meeting** (not Same Meeting appends), update `1_meetings/_dashboard.md`:

1. **Scan all files** in `1_meetings/` (except `_dashboard.md`)
2. **Extract from frontmatter:**
   - `entity`, `latest_meeting`, `next_meeting`, `relationship`, `meeting_count`
3. **Extract from content:**
   - Action items from "Latest Meeting > Actions" sections
   - Key outcomes from "Previous Summary"
4. **Rebuild tables:**
   - Upcoming: Sort by `next_meeting` ascending
   - Recent: Sort by `latest_meeting` descending, limit 7 days
   - Actions: All unchecked `- [ ]` items from action sections
   - All Contacts: Sort by `latest_meeting` descending

---

## FILE RENAME ON NEW MEETING

When adding a new meeting to existing contact:

**Before:** `1_meetings/260126-acme-corp.md`
**After:** `1_meetings/260130-acme-corp.md` (if new meeting is Jan 30)

**Steps:**
1. Read existing file
2. Update content (rotate meeting, add new section)
3. Write to new filename with new date
4. Delete old file
5. Update all dashboard links

---

## TRANSCRIPT INTEGRATION

When user pastes transcript content:
```markdown
> [!info]- Transcript
> {Pasted content here}
```

The collapsible callout keeps the file scannable while preserving full transcript.

<!-- CUSTOMIZE: If you use a transcription tool, add tool-specific formatting here -->

---

## INFOGRAPHIC GENERATION

Generate visual meeting summaries using image generation (e.g., Gemini 3 native image gen).

### When to Generate (vs Skip)

| Scenario | Action |
|----------|--------|
| **First meeting, light notes** | Skip — don't generate |
| **First meeting, substantial** (3+ topics OR 2+ outcomes) | Generate company overview + meeting highlights |
| **Follow-up meeting** | Generate cumulative relationship view |
| **Transcript added** | Regenerate with discussion content |
| **Manual request** | `/meeting Company -- regenerate infographic` |

**"Substantial" means:**
- 3+ key discussion topics, OR
- 2+ concrete outcomes/decisions, OR
- Transcript added with real content

### Storage

- **Location:** `1_meetings/assets/`
- **Naming:** `{YYMMDD}-{slug}-summary.png`
- **Example:** `1_meetings/assets/260127-acme-corp-summary.png`

### Content by Type

**First Meeting (Substantial):**
- Company overview (what they do, key facts)
- Meeting highlights (key topics discussed)
- Next steps

**Follow-Up Meeting (Cumulative):**
- Relationship context (first met, meeting count, status)
- This meeting highlights (key topics, outcomes)
- Open actions (mine and theirs)
- Status indicator

### Prompt Template (Follow-Up Meeting)

```
Create a professional meeting summary infographic:

LAYOUT: Single-panel summary card
- Aspect ratio: 16:9 (landscape)
- Background: Warm white (#FAFAF9)
- Title: "{COMPANY} — Meeting #{N}" in dark slate (#1E293B), 32pt
- Subtitle: "{Date} · {Topic}" in warm slate (#64748B), 20pt

CONTENT SECTIONS (top to bottom):

1. RELATIONSHIP CONTEXT (small text, gray)
   - First met: {date}
   - Status: {relationship status}

2. THIS MEETING (main content, warm slate boxes or bullet list)
   - {Key topic 1} → {Outcome}
   - {Key topic 2} → {Outcome}

3. OPEN ACTIONS (checklist style with empty boxes)
   □ {My action}
   □ {Their action}

4. STATUS: {emoji} {status text} (bottom right)

STYLE:
- Minimal modern, clean lines, no illustrations
- Sans-serif fonts, generous whitespace
- Warm slate (#64748B) for accents, dark slate (#1E293B) for text
```

### Embedding in Meeting File

```markdown
## Meeting Summary

![[1_meetings/assets/260127-acme-corp-summary.png]]
```

Place the embed at the top of `## Meeting Summary` so it's visible immediately when you open the note.

---

## SEARCH TOOLS — Bring Your Own

This skill works with **any combination of search and scraping tools**. The examples use Exa and Firecrawl, but you can swap in whatever you prefer.

### Tool Hierarchy Pattern

**Discovery:**
```
[Primary semantic search]        → Best quality results (Exa, Tavily, etc.)
        ↓ fallback
[Secondary web search]           → Site-specific, recency filter (Firecrawl, Brave, etc.)
        ↓ fallback
[Built-in WebSearch]             → Always available, good for breaking news
```

**Deep Reading:**
```
[Primary page scraper]           → JS-rendered content (Firecrawl, Jina Reader, etc.)
        ↓ fallback
[Built-in WebFetch]              → Simple static pages
```

<!-- CUSTOMIZE: Add your MCP tools to allowed-tools in frontmatter -->
<!-- Example with Exa + Firecrawl MCPs: -->
<!-- allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Task, mcp__exa__web_search_exa, mcp__firecrawl__firecrawl_scrape, mcp__firecrawl__firecrawl_search -->

### Optimal Parameters (If Using Exa + Firecrawl)

**Exa:**
```json
{
  "numResults": 10,
  "type": "auto",
  "livecrawl": "preferred",
  "contextMaxCharacters": 12000
}
```

**Firecrawl Scrape:**
```json
{
  "maxAge": 86400000,
  "onlyMainContent": true,
  "formats": ["markdown"],
  "proxy": "auto"
}
```

---

## SLUG GENERATION

Convert entity name to filename slug:
- Lowercase
- Replace spaces with hyphens
- Remove special characters (keep `a-z0-9-`)
- Collapse multiple hyphens
- Trim hyphens from ends

**Examples:**
- "Acme Corp" → `acme-corp`
- "Jane Doe" → `jane-doe`
- "Tokyo Design Lab (Japan)" → `tokyo-design-lab-japan`

---

## PRE-OUTPUT VALIDATION

Before finalizing:
- [ ] File created/updated in `1_meetings/`
- [ ] Frontmatter complete (entity, latest_meeting, meeting_count)
- [ ] Appropriate section updated based on mode
- [ ] Dashboard updated with current state
- [ ] Research appended (if New Contact or New Meeting mode)
- [ ] Key Sources section has actual URLs (not placeholders)
- [ ] Infographic generated (if substantial content)
