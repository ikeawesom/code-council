# Code Council

**Regulatory change, propagated - not just announced.**

Code Council turns a law firm's contracts into a linked, machine-readable
knowledge base, watches Singapore's parliamentary record, and when something
changes it tells you _which clauses in the firm's own documents just went stale,
in what way, and what the amended text should say_ - then propagates the
approved fix through the firm.

Built for **SMU LIT Hackathon 2026** - _Designing a Sustainable and Resilient
LegalTech_.

---

## The problem we took on

> How might legal teams build tools, systems, or practices that are resilient to
> regulatory change - not just responsive to it?

Law firms are built on artifacts that silently assume the rules stay still:
template clauses, playbooks, checklists, client advisories, compliance
workflows. In Singapore alone, well over a thousand subsidiary legislation
instruments are gazetted, on top of consultation papers, circulars, notices and
guidelines. The moment an amendment lands, every artifact that encoded the old
rule stops being a control and becomes a liability - and nobody knows which ones
they are.

**Awareness is not the gap.** Horizon-scanning services and alert platforms
already exist, and they all stop in the same place: a notification. The lawyer
still has to work out which of their hundreds of documents are affected, read
each one, decide _how_ it is affected, draft the amendment, and remember to tell
whoever else relies on that document. That manual span between _alert_ and
_amended artifact_ is where the risk actually lives.

Code Council is built to close exactly that span.

## How it answers the brief

The brief asks for three things. Each maps to a mechanism, not a promise:

| The brief asks for                                                                  | What Code Council does                                                                                                                                                                                                                                                                                     | Where it lives                                                                  |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **Identify** which existing tools, documents and working practices a change affects | Every document is split into individually addressed clauses and tagged with legal concepts, forming a graph. A new regulatory item is matched against that graph by hybrid retrieval - BM25 over clause text plus concept-tag overlap - so the system names the _specific clauses_, not just the documents | `backend/app/ingest/`, `backend/app/graph/`, `backend/app/analysis/retrieve.py` |
| **Understand** in what way they are affected                                        | Each surviving candidate clause goes to an LLM judge returning a structured verdict - impacted yes/no, severity, written rationale, and suggested replacement text - rendered as a word-level redline against the clause as it stands today                                                                | `backend/app/analysis/impact.py`, `proposal.py::render_diff()`                  |
| **Propagate** the update before the stale version causes harm                       | Approving a proposal rewrites the clause in the vault markdown, bumps the document version in both the database and the file frontmatter, records an immutable `Edit` holding the before-text, and fans out notifications to every lawyer linked to that document                                          | `backend/app/routers/proposals.py`                                              |

The resilience claim is structural rather than aspirational. Because the corpus
is decomposed to clause level and addressed by **stable anchors**
(`warehouse-lease#7-2`), a change can be traced mechanically to its blast
radius. Anchors survive re-ingestion, so proposals, edits and graph edges made
months ago still point at the right text. That is the property that lets a
firm's tooling adapt to change instead of quietly rotting under it.

## The loop

```
ingest      PDF/DOCX -> clauses -> markdown vault + concept tags -> graph.json
scrape      parliamentary record (SPRS JSON API), every response recorded to disk
retrieve    BM25 + concept overlap, top-5 candidate clauses per item   <- the cost filter
judge       LLM: impacted? severity? rationale? suggested text?
propose     task -> affected documents -> per-clause redline proposals
apply       rewrite the vault, bump the version, record the edit, notify the firm
```

Runs unattended at 07:00 SGT; the proposals are waiting by 08:00.

The retrieval gate exists because judging 168 items against 509 clauses with an
LLM is neither affordable nor fast. Cheap lexical and structural matching does
the elimination; the model is spent only where it adds judgment. The thresholds
are configuration, not code (`CC_RETRIEVE_MIN_SCORE`, `CC_ANALYSIS_MAX_ITEMS`).

## What actually runs today

Real figures from the demo corpus, read out of the running system:

|                                   |                                                      |
| --------------------------------- | ---------------------------------------------------- |
| Documents ingested                | 10, across 4 practice sectors                        |
| Clauses addressed                 | 509                                                  |
| Legal concepts extracted          | 125, with 942 clause-concept links                   |
| Parliamentary items ingested      | 168, from a single sitting                           |
| Surviving the gate into proposals | 2 tasks, 3 document reviews, 7 clause-level redlines |
| Firm members wired to documents   | 4 lawyers, 20 document links                         |
| Backend tests                     | 125 passing, `ruff` clean, `tsc` clean               |

A full daily run replays end to end **with the network unplugged**
(`CC_OFFLINE=1`), which is also how the live demo is guaranteed to work on
stage.

## Quick start

```bash
# backend
cd backend && python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

Drop contracts (PDF/DOCX) into `data/inbox/<practice-sector>/`, then:

```bash
python scripts/ingest.py                 # documents -> vault + graph
python scripts/ingest.py --llm mock      # same, no LLM calls (fast, deterministic)
python scripts/run_daily.py --offline --llm mock   # replay -> gate -> judge -> proposals, no network
python scripts/run_daily.py              # same, live scrape + configured LLM (CC_LLM_PROVIDER)
```

`ingest.py` flags: `--llm mock|claude_cli|local` overrides the provider,
`--force` re-tags concepts that are already recorded, `--only <slug>` ingests a
single document. Re-running is idempotent - the vault markdown comes out
byte-identical apart from `ingested_at`, and no database row is duplicated.

The sub-folder name under `data/inbox/` becomes the document's practice sector,
so `data/inbox/real-estate/lease.pdf` is filed under `real-estate`. Add a new
sector by creating a folder; nothing in the code needs to change.

`reset.bat` rewinds every approval - clause text, document versions, vault
markdown, proposals, tasks, edits and notifications - back to a pristine demo
state.

## Layout

| Path        | What                                                                 |
| ----------- | -------------------------------------------------------------------- |
| `backend/`  | FastAPI, SQLite, APScheduler, scraper, retrieval and LLM analysis    |
| `frontend/` | Next.js dashboard - tasks, documents, parliament, inbox              |
| `vault/`    | the knowledge base - plain markdown, Obsidian-compatible             |
| `data/`     | inbox (your documents), fixtures (recorded responses), llm_cache     |
| `scripts/`  | ingest, daily run, demo seeding, demo reset                          |
| `docs/`     | vault format, API contract, decision log, demo script, QA checklists |

## Design Decisions

**The vault is plain markdown, and it is the source of truth for content.**
Obsidian opens it, `git diff` reads it, and a lawyer can edit it with no
software at all. A resilience tool that locks the firm's knowledge inside its
own database has simply become the next thing that goes stale. SQLite holds only
state, relations and workflow.

**A human approves every change.** The system proposes; it never amends
unilaterally. Every applied change carries its rationale, its before-text and
its author, so the audit trail explains _why_ a clause reads the way it does -
which is what makes the next regulatory change tractable too.

**The source layer is replaceable.** The parliamentary record is the first feed,
not the only conceivable one. Everything downstream operates on normalised
items, so adding a second source - gazette, regulator circulars, consultation
papers - means writing one client that emits rows through
`normalize.persist_items()`; retrieval, judging and propagation are unchanged.

**Nothing has to leave the firm.** The LLM sits behind a provider interface with
an on-prem Ollama implementation (`local`) alongside the hosted one used for the
demo - swapping is one config line, not a rewrite. Client documents are
gitignored, and so is everything derived from them.
