# Code Council - UI implementation plan (M4)

Source designs: Google Stitch project `3954592498826862557` ("Code Council Legal
Portal"), five desktop screens downloaded to `docs/stitch/<n>-<slug>/` as
`code.html` + `screen.png`. The HTML is Stitch export: Tailwind **CDN**, inline
`tailwind.config`, Material Symbols icons, Plus Jakarta Sans. It is reference
material, not code to paste - see "How to port" below.

Downloaded 2026-09-05, all five HTTP 200:

| # | Folder | Stitch screen ID | Height |
|---|---|---|---|
| 1 | `01-tasks` | `0b1317e1e8df4af4b48624f6fc9c833a` | 2048 |
| 2 | `02-task-affected-documents` | `6108f8c88d47402bbb8f76caae5aa394` | 2670 |
| 3 | `03-task-detail-subletting` | `56859c803bc449978e78c4cfec98f976` | 2300 |
| 4 | `04-inbox` | `7058731180f24f509108bf8fe963b616` | 2162 |
| 5 | `05-documents` | `8566cbb9e0fe4c17a1220d82ed461618` | 3482 |

The project contains 8 further screens - earlier iterations and a logo. Ignore
them; the five above are the approved set.

---

## 1. The structural change: tasks are three levels, not two

Screen 2 was added during design and it changes the shape of the app. The
breadcrumbs in the exports confirm the chain - screen 2 says "Back to Morning
Briefing", screen 3 says "Back to Affected Documents":

```
Tasks (morning briefing)
  └─ Task  ->  Affected Documents Overview      one parliament item, N documents
       └─ Document  ->  Clause redline review    one document, M clauses
```

**This does not match the current data model.** `models.py` describes
`proposals` as `(parliament_item x clause)`, a flat pair. The UI needs an
intermediate grouping and task-level state that a flat pair cannot carry.

Required model change, to settle **before** M4 and ideally while freezing
`models.py` in M1:

- A **task** is one parliament item, with its own id (`TASK-SG-2026-0884` in the
  design), status, assignee and severity.
- A task fans out to **affected documents** (2 in the design), each with its own
  exposure level and flagged-clause count.
- Each affected document holds **clause-level proposals** - the existing
  `(parliament_item x clause)` rows, which stay as they are.

Severity appears at two levels in the design: "High impact" on the task, "High
Exposure" / "Medium Exposure" per document. Simplest correct rule: store
severity per clause proposal (the judge already returns it), then roll up to
document and task as the maximum. Do not have the LLM emit three severities.

---

## 2. Status model - PROPOSED, needs your confirmation

The five screens use eight different status-ish labels: `New`, `In progress`,
`Approved`, `Applied by...`, `Dismissed`, `Action Required`, `Pending Review`,
`Pending`, plus `Mark Task Reviewed`. That is design drift across separately
generated screens, not eight real states. Normalise to this before writing any
component:

**Task status - exclusive, one at a time:**

| Status | Meaning | Set by |
|---|---|---|
| `new` | Nobody has opened it | pipeline, on creation |
| `in_progress` | Claimed by a named lawyer - shows avatar + name | opening / claiming a task |
| `approved` | Amendment applied, vault updated, version bumped | approve action |
| `dismissed` | Judged not relevant, no vault change | reject action |

**Badges - CONFIRMED 2026-09-05, exactly two, both always present:**

| Badge | Values | Source |
|---|---|---|
| Impact severity | `High Impact` (red) / `Medium Impact` (amber) / `Low Impact` (slate) | max severity of the task's clause proposals |
| Legislation type | `Amendment` / `New Legislation` | `parliament_items.legislation_type` |

The earlier three-badge set (`Recently modified`, `Also assigned to N others`,
`Unsupported file type`) is dropped - see `DECISIONS.md` 2026-09-05. Parse
failures surface as `documents.parse_error` text in the documents list instead.

**Severity - separate axis, drives ranking:** `high` / `medium` / `low`.

Three notes on why this shape:

- The designs use both "Approved" (filter pill, screen 1) and "Applied by Amelia
  Tan" (card 5, screen 1) for the same state. Pick one label. Recommend
  **Approved** in filters and chips, "Applied by X at Y" only as metadata text.
- "Action Required" and "Pending Review" on screen 2 are not task states - they
  are *document* states within a task. Model them as a per-document
  `review_state` of `pending` / `reviewed`, or drop them for the demo.
- `in_progress` carrying the colleague's name is the whole anti-duplication
  feature. A bare "In Progress" sends the lawyer to Slack to find out who.

**Open question for you:** do you want a review step between `in_progress` and
`approved` (a second partner signs off), or is approve-directly correct for the
demo? The designs hint at sign-off ("Standard clause locks remain active until
senior partner sign-off") but nothing implements it. Recommend leaving it out.

---

## 3. Design system - must be normalised before porting

The five screens do **not** share a token vocabulary. Stitch generated each one
independently, so the same colour has different names and near-duplicate values
per screen. Porting screen-by-screen would import that inconsistency permanently
and directly undercuts the "easy to customize" requirement.

Constant across all five (safe to adopt):

```
primary        #E8762D      primary-hover  #C75F1C
text-main      #1A1A1A      text-secondary #5A5A5A
divider        #E2E2E2      surface        #FFFFFF
font           Plus Jakarta Sans (400/500/600/700) + Material Symbols Outlined
```

Drifted, needs one value chosen:

| Concept | Values found | Adopt |
|---|---|---|
| Sidebar dark | `#141C24` (s1), `#13181F` (s3), `#0B1528` (s4), `#141415`/`#18181B` (s5) | **`#141C24`** |
| Page background | `#F7F5F3` (s1, s4), `#FCF9F8` (s5), `#F4F1EE` (s2) | **`#F7F5F3`** |
| Muted text | `#8A8A8A` (s1), `#8C8C8C` (s3, s5) | **`#8C8C8C`** |
| Naming | `text-main` / `on-surface` / `text-primary`; `surface-card` / `surface` / `surface-container-lowest` | **one set, below** |

Canonical token set - define once in `tailwind.config.ts`, use everywhere:

```
primary, primary-hover, primary-subtle      brand orange + tint for badge fills
sidebar, sidebar-border                     dark chrome
background, surface, surface-subtle         page / card / inset
text-main, text-secondary, text-muted
border-hairline
severity-high, severity-medium, severity-low
status-new, status-progress, status-approved, status-dismissed
```

Severity and status get their own tokens rather than reusing red/amber/grey
directly - that is what makes a firm's palette swappable later without hunting
through components. **Never colour-only:** every chip pairs colour with a text
label (already true in the exports; keep it).

Note Stitch dropped the serif heading direction from the original prompt and
used Plus Jakarta Sans throughout. That is fine and arguably cleaner - accept it,
but then remove the serif reference from `STITCH_PROMPT.md` if regenerating.

---

## 4. Routes

Current stubs under `frontend/app/` are `page.tsx`, `documents/[slug]`,
`proposals/[id]`, `graph`. The proposals route is superseded.

| Route | Screen | Notes |
|---|---|---|
| `/` | - | redirect to `/tasks` |
| `/tasks` | 1 | morning briefing, filters, task cards |
| `/tasks/[taskId]` | 2 | affected documents overview |
| `/tasks/[taskId]/documents/[docSlug]` | 3 | clause redline + approve/reject |
| `/inbox` | 4 | notification feed |
| `/documents` | 5 | vault grouped by practice area |
| `/documents/[slug]` | - | existing stub; document + clause list + history |
| `/parliament` | - | nav item exists in all five sidebars; list of scraped items |
| `/settings` | - | nav item exists; can be a stub for the demo |

`/graph` is M6 and is not in any Stitch screen - keep the stub, no sidebar entry
unless M6 lands.

---

## 5. Component inventory

Shared shell (identical in all five exports - build once):

- `AppShell` - 240px fixed sidebar + top bar + content area
- `Sidebar` - wordmark, nav items with count badges (Tasks 7, Inbox 3), the
  practice-area sub-list with per-sector counts (screen 1), footer status block
- `TopBar` - search field, date, user chip with switcher caret

Primitives:

- `SeverityChip` (high/medium/low) · `StatusChip` (the four above, renders
  assignee avatar + name for `in_progress`) · `Badge` (neutral/warning)
- `Avatar` / `AvatarStack` · `EmptyState` · `ConfirmDialog` · `FilterPills`

Feature components:

- `TaskCard` (screen 1) - severity, status, title, plain-English explanation,
  metadata row, primary action. The `in_progress` variant gets a tinted
  background - that visual difference is the anti-duplication signal.
- `AffectedDocumentCard` (screen 2) - document, exposure, flagged-clause count,
  conflict summary, inline quoted before/after preview
- `HansardSourcePanel` (screens 2, 3) - item title, type, date, ministry,
  speaker, quoted extract, link out
- `RedlineDiff` (screen 3) - the most important component in the app.
  `<del>` red strikethrough, `<ins>` green underline, unchanged plain. Renders
  in body font, not monospace - it must read like a contract.
- `ClauseAccordion` (screen 3) - second affected clause, collapsed by default
- `NotificationRow` (screen 4) - avatar, sentence-form message with semibold
  names/documents, one-line preview, action link, unread dot + tint
- `SectorSection` (screen 5) - collapsible practice-area group with count
- `DocumentRow` (screen 5) - icon, name, clause count, version, badges, chevron
- `UnsupportedFileNotice` (screen 5) - the parse-failure card, rendered for any
  document the parser could not read (none in the current corpus)

---

## 6. How to port the Stitch HTML

The exports are **not** droppable into Next.js. Per file:

1. Tailwind is loaded from `cdn.tailwindcss.com` with an inline
   `tailwind.config` - replace with the project's real Tailwind build and the
   canonical token set from section 3.
2. Icons are Material Symbols via Google Fonts stylesheet. Either keep that one
   `<link>` in `app/layout.tsx`, or swap to `lucide-react`. Keeping Material
   Symbols is closer to the design and cheaper.
3. Fonts: load Plus Jakarta Sans via `next/font/google` rather than a CDN link.
4. Every screen repeats the full sidebar and top bar inline - extract to
   `AppShell` once and delete four copies.
5. All content is hard-coded. Replace with props/fetches against the FastAPI
   routers. Keep the exports as visual reference in `docs/stitch/`.
6. `::-webkit-scrollbar { display: none }` in the exports hides scrollbars -
   drop it, it hurts usability on a long tasks list.
7. Per CLAUDE.md: strict TypeScript, function components, Tailwind utilities
   only - no CSS modules.

---

## 7. Fiction to cut before demo day

Stitch invented a large amount of enterprise chrome that the system does not do.
Some is harmless stagecraft; some would misrepresent the product to judges,
which the project has already ruled out once (`DECISIONS.md`: "passing a planted
item off as scraped would misrepresent the system").

**Cut - claims an integration that does not exist:**
- "Firm Folder Sync: Active via SharePoint - iManage Work 10.4" (screen 5)
- "Create a folder in your firm repository inbox (SharePoint or iManage)" -
  should read `data/inbox/`, which is what actually happens
- "Synced 07:15 Today" per document - nothing syncs; use ingested/updated dates
- "8 Active Client Matters Bound", "11 linked active transactions in the
  Singapore Corporate & Conveyancing registry" (screen 2) - no matter registry
- "Repository Hash: SHA256-...", "HASH: c9a4...f01d" (screens 5, 3) - decorative
  hashes implying provenance that is not computed
- "Gazette" nav item - only Hansard is scraped. Remove it or leave `/parliament`
  only.

**Fix - contradicted by real fixture data.** The designs say "SG Parliament
Session 14 - Sitting No. 38" and "Vol. 95 No. 12". The actual 5 Aug 2026 sitting
in `data/fixtures/getHansardReport/05-08-2026.json` is:

```
parlimentNO 15   sessionNO 1   volumeNO 96   sittingNO 34
```

Drive these from `metadata` in the fixture rather than hard-coding. Same for the
speaker attribution and the quoted extract on screens 2 and 3 - both are
invented text; use the real `content` field.

**Keep - good stagecraft, harmless:**
- Task reference ids (`TASK-SG-2026-0884`, `SG-HA-2026-0805-41`) - generate them
  for real from item id + date; they make the product feel institutional
- "Detected 42 mins ago via Official SG Hansard Feed" - true once the scheduler
  runs, just compute it
- Statutory citation panel (JTC Act s 18(2), circular refs) - real legislation
  and a genuinely good idea; populate from the LLM judge output or omit the
  panel rather than faking specific circular numbers

---

## 8. Build order

Freeze the model change in section 1 first - everything else depends on it.

1. Tailwind config + tokens + `AppShell` + `Sidebar` + `TopBar` (unblocks all screens)
2. Primitives: `SeverityChip`, `StatusChip`, `Badge`, `EmptyState`
3. `/tasks` with `TaskCard` - the screen judges see first
4. `/tasks/[taskId]/documents/[docSlug]` with `RedlineDiff` - the money shot
5. `/tasks/[taskId]` affected-documents overview
6. `/documents` grouped by sector - proves the customizable-taxonomy story
7. `/inbox` - proves the multi-lawyer story
8. `/parliament`, `/settings` - stubs if time runs out

Steps 3-7 are independent once 1-2 land, so they parallelise cleanly with no
shared files.

---

## 9. Open questions

1. ~~**Status set** (section 2)~~ - RESOLVED 2026-09-05. The four statuses stand.
   Badges cut to exactly two: colour-coded impact severity, and
   `Amendment` / `New Legislation`. Sign-off step still unanswered; proceeding
   without it.
2. **Per-document review state** - keep `Action Required` / `Pending Review` on
   screen 2, or drop for the demo? Recommend drop.
3. **Icon library** - Material Symbols (matches design, one CDN link) vs
   `lucide-react` (bundled, no external font). Recommend Material Symbols.
