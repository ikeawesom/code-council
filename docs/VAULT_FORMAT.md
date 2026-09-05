# Vault file format - FROZEN 2026-09-05

The vault is the source of truth for document *content*. It must open natively in
Obsidian with no plugins. Everything downstream (proposals, edits, graph edges)
addresses clauses by `<doc-slug>#<anchor>`, so the anchor scheme below is an API -
changing it invalidates stored work.

Companion contract: `backend/app/models.py` (frozen the same day).

---

## 1. Slugs

`slugify(text)` - lowercase, ASCII, non-alphanumerics collapsed to single `-`,
leading/trailing `-` stripped. Leading numeric prefixes in filenames are kept
(`01. Tenancy Agreement (Pte).pdf` -> `01-tenancy-agreement-pte`) so two
differently-numbered files never collide.

Sector is the inbox sub-folder name, slugified, carried as a plain string. It is
**not** part of any slug or anchor - re-filing a document between practice areas
must never invalidate a proposal.

**Document titles come from the filename, always** (amended 2026-09-05): the stem
with the extension removed, any leading `NN.` / `NN ` numbering stripped, and
whitespace collapsed - `01. Tenancy Agreement (Pte).pdf` -> `Tenancy Agreement
(Pte)`. Deriving the title from the document's own first heading was tried and
produced `BETWEEN`, `TERMS OF SALE` (for two different files) and
`EX-10.82 5 dex1082.htm JOINT VENTURE AGREEMENT`. Deterministic and recognisable
beats clever.

## 2. Clause anchors

Derived from the clause's own numbering, so they survive re-ingest:

| Clause number in the document | `anchor` | `ref` |
|---|---|---|
| `7.2` | `7-2` | `warehouse-lease#7-2` |
| `7.2.1` | `7-2-1` | `warehouse-lease#7-2-1` |
| `7(a)` | `7-a` | `warehouse-lease#7-a` |
| `Clause 14` | `14` | `warehouse-lease#14` |
| Schedule 2, para 3 | `sch-2-3` | `warehouse-lease#sch-2-3` |
| unnumbered, has a heading | slug of the heading, truncated to 40 chars | `nda-template#confidential-information` |
| unnumbered, no heading | `s<order_index>` (e.g. `s17`) - last resort | `nda-template#s17` |

Rules:

- An anchor is unique within a document. On collision, append `-2`, `-3`, ... in
  document order. The first occurrence never gets a suffix, so it stays stable.
- Anchors are lowercase, `[a-z0-9-]` only.
- `Clause.ref` is always exactly `f"{document.slug}#{clause.anchor}"`.

## 3. `vault/documents/<slug>.md`

```markdown
---
title: Tenancy Agreement (Pte)
slug: 01-tenancy-agreement-pte
type: document
sector: real-estate
source: data/inbox/real-estate/01. Tenancy Agreement (Pte).pdf
file_type: pdf
version: 1
clause_count: 42
concepts: [notice-period, rent-review, termination]
ingested_at: 2026-09-05T09:14:00+00:00
parse_error: null
---

# Tenancy Agreement (Pte)

## 7.2 Notice Period
<!-- anchor: 7-2 -->

Either party may terminate this Agreement by giving not less than two (2)
months' written notice to the other party.

**Concepts:** [[notice-period|Notice Period]], [[termination|Termination]]
```

- One `##` heading per clause, in document order. The `<!-- anchor: ... -->`
  comment on the line immediately after the heading is the machine-readable
  anchor; Obsidian renders it invisibly, and the reader parses it, never the
  heading text.
- Clause body follows after a blank line. The `**Concepts:**` line is last and is
  optional (a clause may have no concepts).
- `parse_error: null` normally. When the parser could not read the file, the
  value is the error string, `clause_count` is 0, and the body is a single
  paragraph explaining that the file needs conversion. The document file is
  still written - a document that cannot be parsed must be visible, not missing.

## 4. `vault/concepts/<slug>.md`

```markdown
---
title: Notice Period
slug: notice-period
type: concept
clause_count: 12
---

# Notice Period

Contractual periods of advance warning required before termination, rent review
or variation.

## Clauses
- [[01-tenancy-agreement-pte]] - `7-2` - Notice Period
- [[warehouse-lease]] - `14` - Termination for Convenience
```

Links point at document *files*, not headings - a file wikilink is always valid,
a heading wikilink breaks the moment a heading is reworded. The anchor is
carried as code text alongside.

## 5. `vault/parliament/<YYYY-MM-DD>-<slug>.md`

Written by M2, specified here so the format is settled once:

```markdown
---
title: Amendments to the Residential Tenancies Act
slug: amendments-to-the-residential-tenancies-act
type: parliament_item
sitting_date: 2026-08-05
sprs_id: oral-answer-4165
item_type: oral answer
legislation_type: amendment
speaker: Minister for National Development
url: https://sprs.parl.gov.sg/search/...
concepts: [notice-period]
---
```

`legislation_type` is one of `amendment` / `new_legislation` - badge 2 of the
two-badge set (`DECISIONS.md`, 2026-09-05).

## 6. `vault/graph.json`

```json
{
  "generated_at": "2026-09-05T09:14:00+00:00",
  "nodes": [
    {"id": "document:01-tenancy-agreement-pte", "type": "document",
     "label": "Tenancy Agreement (Pte)", "sector": "real-estate"},
    {"id": "clause:01-tenancy-agreement-pte#7-2", "type": "clause",
     "label": "7.2 Notice Period", "document": "01-tenancy-agreement-pte"},
    {"id": "concept:notice-period", "type": "concept", "label": "Notice Period"},
    {"id": "parliament:2026-08-05-amendments-to-the-rta", "type": "parliament_item",
     "label": "Amendments to the RTA", "sitting_date": "2026-08-05"}
  ],
  "edges": [
    {"source": "document:01-tenancy-agreement-pte",
     "target": "clause:01-tenancy-agreement-pte#7-2", "type": "contains"},
    {"source": "clause:01-tenancy-agreement-pte#7-2",
     "target": "concept:notice-period", "type": "tagged"},
    {"source": "parliament:2026-08-05-amendments-to-the-rta",
     "target": "concept:notice-period", "type": "mentions"}
  ]
}
```

Node ids are `"<type>:<key>"`. Edge types are `contains` / `tagged` / `mentions`
only. The file is rewritten whole on every build - it is derived, never edited.

## 7. Idempotency

Re-running ingest on unchanged inputs must produce byte-identical vault files
except for `ingested_at`, and must not duplicate database rows. Writers upsert on
`slug` (documents, concepts) and `ref` (clauses).
