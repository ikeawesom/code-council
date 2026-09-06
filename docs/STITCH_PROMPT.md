# Google Stitch prompts - Code Council dashboard

How to use: pick **Web / Desktop** mode in Stitch (this is a desktop app, not mobile).
Paste **Prompt 0** first to set the style, then generate **one screen at a time**
with prompts 1-4 - a single giant prompt produces mush. Refinement prompts are at
the bottom. Sample data below is real (actual documents in `data/inbox/` and real
Hansard titles from 5 Aug 2026), so the mockups double as demo screenshots.

---

## Prompt 0 - style foundation (paste first)

```
I am designing a desktop web app called Code Council, used by lawyers at a
Singapore law firm. Every morning it reads new Singapore parliamentary reports
(Hansard) and flags which clauses in the firm's contracts are affected, then
proposes an amendment for a lawyer to approve or reject.

The user is a practising lawyer with no technical background. They are busy,
skim-read, and will not tolerate jargon or clutter. Design for calm authority,
not excitement.

Visual direction:
- Professional legal-tech. Restrained, editorial, trustworthy. Think a quality
  broadsheet newspaper rather than a startup SaaS dashboard.
- Light theme. Off-white page background (#FAFAF8), white cards, hairline
  borders rather than heavy drop shadows.
- Ink navy (#1B2A41) for primary text and the main action colour. One warm
  accent (#B4541E) used sparingly for high-severity flags only.
- Severity colours: high = deep red, medium = amber, low = slate grey. Never
  use colour as the only signal - always pair it with a text label.
- Generous whitespace and a comfortable reading measure. Body text 15-16px
  minimum. Legal documents are dense; the interface around them must not be.
- Serif headings (like Source Serif or Lora), clean sans-serif for UI labels
  and body (like Inter).
- Squared-off cards, 6px corner radius. No gradients, no glassmorphism, no
  illustrations, no emoji.

Language rules for all labels:
- Plain professional English. Say "Amendment suggested", not "Proposal object".
  Say "Affected clause", not "Retrieved candidate".
- Never surface internal machinery: no mention of models, embeddings, scores,
  pipelines, or confidence percentages.
- Every screen has exactly one obvious primary action.

Layout shell used by every screen:
- A slim left sidebar, 240px, ink navy background, with the wordmark
  "Code Council" at the top and these nav items with simple line icons:
  Tasks, Inbox, Documents, Parliament, Settings. "Tasks" carries a count badge
  showing 7. "Inbox" carries a count badge showing 3.
- A top bar with a search field ("Search clauses, documents, or parliament
  items"), a date reading "Wednesday, 5 August 2026", and on the right a user
  chip with initials and the name "Amelia Tan" plus a small caret for switching
  user.
- Content area to the right of the sidebar, below the top bar.
```

---

## Prompt 1 - Tasks (the home screen)

```
Design the "Tasks" screen for Code Council, using the style and layout shell
already described.

This is the morning briefing: everything the system flagged overnight that a
lawyer needs to decide on.

Page header: "Tasks" with the subheading "7 items flagged from Parliament,
5 August 2026". A secondary text button on the right reads "Mark all as read".

Below the header, a horizontal filter row of pill-shaped toggles:
"All (7)", "New (4)", "In progress (2)", "Applied (1)", plus a separate
dropdown labelled "All practice areas" listing: Real Estate, Mergers &
Acquisitions, Energy & Infrastructure, General.

The main content is a vertical list of task cards, comfortably spaced. Each
card has this structure:

- Top-left: a severity chip - one of "High impact" (deep red), "Medium impact"
  (amber), "Low impact" (grey).
- Top-right: a status chip. Exactly one of:
    "New" - dark outline, plain
    "In progress - Daniel Ong" - filled navy, with a small circular avatar
    "Applied" - green, with a small check mark
    "Dismissed" - grey, muted
- Beneath that, the task title in serif, 20px, e.g.
  "Subletting rules may affect 2 clauses in Tenancy Agreement (Pte)".
- A single line of plain-English explanation, e.g. "Parliament discussed new
  conditions on subletting JTC industrial properties. Clauses 7.2 and 7.3 set
  out subletting consent and may now be inconsistent."
- A metadata row in small grey text: practice area, the document name, and
  "Flagged 07:04 today".
- Optional small badges that can appear alongside the status chip and are
  independent of it: "Recently modified" (this document changed in the last 7
  days) and "Also assigned to 2 others".
- Bottom-right of the card: a primary button "Review amendment".

Show 5 cards covering the full range of states, using this real sample data:

1. High impact / New / Real Estate - "Subletting rules may affect 2 clauses in
   Tenancy Agreement (Pte)" - source: "Data on Applications for Subletting of
   JTC Properties" - badge "Recently modified".
2. High impact / In progress - Daniel Ong / Real Estate - "Rental relief
   measures affect the rent review clause in Option To Purchase (Private
   Commercial)" - source: "Rental Reductions, Free Lunchtime Parking to Boost
   Footfall".
3. Medium impact / New / Mergers & Acquisitions - "Foreign investment review
   thresholds may affect completion conditions in Joint Venture Agreement" -
   badge "Also assigned to 2 others".
4. Medium impact / New / Energy & Infrastructure - "Revised BCA contractor
   duties affect the indemnity clause in Agreement for Consultancy (BCA)".
5. Low impact / Applied / General - "Data-handling obligations affect clause 4
   of NDA template" - metadata reads "Applied by Amelia Tan, 08:20 today".

The "In progress" card should be visually distinct enough that a lawyer
instantly understands someone else is already working on it and they should not
duplicate the work - a subtle tinted card background and the colleague's name
and avatar shown clearly.

Include an empty state below the fold as a second frame: a calm centred message
reading "Nothing flagged today. Parliament last sat on 5 August 2026." with a
secondary button "Browse documents".
```

---

## Prompt 2 - Task detail with redline

```
Design the task detail screen for Code Council, using the established style.
This is where a lawyer decides whether to accept a suggested amendment.

A back link at the top reads "Back to Tasks". Below it the task title in serif,
26px: "Subletting rules may affect 2 clauses in Tenancy Agreement (Pte)", with
a "High impact" severity chip and a "New" status chip beside it.

A prominent action bar sits at the top right of the content area and stays
visible while scrolling: a primary navy button "Approve and update document", a
secondary outline button "Reject", and a text button "Assign to a colleague".

The body is three columns, but weighted - not equal thirds:

LEFT COLUMN (narrow, about 280px), headed "What changed in Parliament":
  A card showing the source item: the title "Data on Applications for
  Subletting of JTC Properties", the type "Written Answer", the date
  "5 August 2026", and the speaker "The Minister for Trade and Industry".
  Below, a short quoted extract of the parliamentary text in a bordered
  blockquote, with a link "Read the full report".

CENTRE COLUMN (widest), headed "Suggested amendment":
  This is the most important element on the page - a redline diff shown the way
  a lawyer expects it in Word: removed text in red with strikethrough, inserted
  text in green with underline, unchanged text in plain black. Monospace is
  wrong here - use the serif body font so it reads like a contract.
  Above the diff, a label: "Clause 7.2 - Subletting and assignment", and a
  small "Tenancy Agreement (Pte) - version 3" caption.
  Below the diff, a bordered panel headed "Why this was flagged" containing two
  or three sentences of plain-English reasoning.
  Then a second collapsed section headed "Clause 7.3 - Consent not to be
  unreasonably withheld", showing it is also affected and can be expanded.

RIGHT COLUMN (narrow, about 280px), headed "Who this affects":
  A list of three colleagues with avatars, names and roles - "Daniel Ong,
  Partner", "Priya Nair, Senior Associate", "Marcus Lee, Associate" - with the
  caption "These lawyers will be notified if you approve this change."
  Below it, a "Document history" mini-timeline with three entries showing
  version, who changed it and when.

Include a confirmation dialog as a separate frame: centred modal titled
"Approve this amendment?" with the plain-English body "Clause 7.2 of Tenancy
Agreement (Pte) will be updated and saved as version 4. Three colleagues will be
notified. You can undo this from the document history." and two buttons,
"Approve and update" (primary) and "Cancel".
```

---

## Prompt 3 - Inbox

```
Design the "Inbox" screen for Code Council, using the established style.

This is a notification feed telling a lawyer what colleagues changed, so nobody
is surprised by an edit to a document they rely on.

Page header: "Inbox" with subheading "3 unread". A text button on the right
reads "Mark all as read".

The feed is a single vertical list, grouped under small date headings "Today",
"Yesterday" and "Earlier this week". Each row contains:
- A circular avatar with the colleague's initials on the left.
- The message in plain sentence form, with names and document titles in
  semibold: "Daniel Ong modified Tenancy Agreement (Pte) - clause 7.2 - at
  09:14 today."
- A one-line preview of what changed in smaller grey text.
- A "View changes" link on the right of the row.
- Unread rows carry a small navy dot on the far left and a very slightly
  tinted background; read rows are plain.

Show 6 rows covering these cases:
1. Unread - "Daniel Ong modified Tenancy Agreement (Pte) - clause 7.2 - at
   09:14 today." preview: "Subletting now requires written landlord consent
   within 14 days."
2. Unread - "Priya Nair approved an amendment to Option To Purchase (JTC
   Industrial) at 08:47 today."
3. Unread - "Code Council flagged 7 new items from Parliament at 07:04 today."
   with the link reading "View tasks" instead of "View changes".
4. Read - "Marcus Lee dismissed a suggested amendment to NDA template
   yesterday at 16:30."
5. Read - "Daniel Ong assigned you a task in Mergers & Acquisitions yesterday
   at 14:02."
6. Read - "Priya Nair added Joint Venture Agreement to the vault on Monday."

Include an empty state as a second frame: "You are all caught up." with a small
line icon and a secondary button "Go to Tasks".
```

---

## Prompt 4 - Documents, grouped by practice area

```
Design the "Documents" screen for Code Council, using the established style.

This is the firm's contract library. It must make clear that practice areas are
the firm's own folders and can be added or renamed freely - not a fixed list
built into the software.

Page header: "Documents" with subheading "9 documents across 4 practice areas".
On the right, a primary button "Add documents".

Below, a search field and a view toggle offering "Grouped by practice area" and
"All documents".

In grouped view, show four collapsible sections, each with a section header
containing the practice area name in serif, a count, and a small chevron:

REAL ESTATE (3)
  - Tenancy Agreement (Pte) - 42 clauses - version 3 - badge "2 open tasks"
  - Option To Purchase (Private Commercial) - 28 clauses - version 1 - badge
    "1 open task"
  - Option To Purchase (JTC Industrial) - 31 clauses - version 2
MERGERS & ACQUISITIONS (3)
  - Joint Venture Agreement - 67 clauses - version 1 - badge "1 open task"
  - JVA Term Sheet - 19 clauses - version 1
  - Project Folklore Term Sheet (Final) - 23 clauses - version 1
ENERGY & INFRASTRUCTURE (2)
  - Agreement for Consultancy (BCA) - 35 clauses - version 1 - badge "1 open
    task"
  - Agreement for Consultancy (Construction Project) - 39 clauses - version 1
GENERAL (1)
  - NDA template - 12 clauses - version 4 - badge "Recently modified"

Each document row shows a small document icon, the name in semibold, the
metadata in grey, any badges, and a chevron on the right indicating it opens.
Rows with open tasks should read as gently attention-worthy without shouting.

At the bottom of the list, show a dashed-outline placeholder card reading
"Add a practice area" with the caption "Create a folder in your inbox and Code
Council will pick it up automatically." This communicates that the taxonomy is
the firm's, not the software's.
```

---

## Refinement prompts (use after a screen is generated)

```
Make the status chips more distinguishable at a glance - a lawyer must tell
"New" from "In progress" from across the room, without reading the text.
```

```
The redline diff is the most important element on the task detail screen.
Increase its visual weight and reduce everything around it.
```

```
Reduce the interface chrome by about a third. Fewer borders, fewer boxes,
more whitespace. Let the document text carry the page.
```

```
Show the same Tasks screen at 1280px width, ensuring the task cards stay
readable and the filter row does not wrap awkwardly.
```
