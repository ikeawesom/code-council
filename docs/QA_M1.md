# M1 manual QA - the ingest pipeline

Ten tests, roughly 15 minutes. Each says what to run, what you should see, and
what it means if you don't. Report back with the test number and what you got.

**Before you start:** the backend deps are already installed and the vault is
already built, so you can go straight to test 1. If you want to start from
nothing, see test 9.

**Servers.** Start them yourself:

```bash
# backend  (from repo root)
cd backend && uvicorn app.main:app --reload --port 8000

# frontend (separate terminal, needs npm install the first time)
cd frontend && npm install && npm run dev
```

⚠️ **The frontend is still an M4 stub.** `http://localhost:3000` will render the
words "Lex Sentinel - dashboard (M4)" and nothing else. That is expected at this
milestone - there is no UI to QA yet. Tests 6 and 7 use the API directly.

---

## 1. Ingest runs clean on the real documents

```bash
python scripts/ingest.py --llm mock
```

**Expect:** ten lines, one per document, then a summary. Every document except
the `.doc` shows a non-zero clause count. Runtime a few seconds.

```
  nda-template                       general                    14 clauses  cached tags
  joint-venture-agreement            mergers-and-acquisition   101 clauses  cached tags
  ...
Ingested 10 document(s). Vault now holds 10 documents, 219 concepts.
```

**Fails if:** a traceback appears, or any document reports 0 clauses other than
`vima-2-0-model-term-sheet-long-form`.

## 2. The unreadable file is reported, not skipped

Same output as test 1. Find this line:

```
  vima-2-0-model-term-sheet-long-form  mergers-and-acquisition  0 clauses  !! Legacy binary .doc format is not supported - convert to .docx ...
```

Then open `vault/documents/vima-2-0-model-term-sheet-long-form.md`. It should
exist, carry `parse_error:` in the frontmatter, and explain the conversion needed.

**Why this matters:** a document the firm can't parse must stay *visible*. A
missing file is a document nobody knows they're not monitoring.

## 3. Re-running changes nothing (idempotency)

```bash
python scripts/ingest.py --llm mock
python scripts/ingest.py --llm mock
git status --short vault/
```

**Expect:** `git status` reports nothing for `vault/` (the generated vault is
gitignored - see test 10). More importantly, the second run prints the same
clause counts as the first, and says `cached tags` rather than `tagged`.

**Fails if:** clause counts drift between runs, or the run reports a growing
number of concepts. That would mean re-ingest is duplicating data - the thing
that silently corrupts the vault.

## 4. The vault opens in Obsidian

Open the `vault/` folder as an Obsidian vault (Open folder as vault).

**Check:**
- `index.md` lists all 10 documents and the concepts.
- Open `documents/nda-template.md` - clauses render as `##` headings, each
  followed by its text, with a `**Concepts:**` line of working `[[wikilinks]]`.
- Click a concept link, e.g. `[[confidentiality]]`. It opens
  `concepts/confidentiality.md`, which lists every clause tagged with it across
  documents.
- Open Obsidian's graph view. You should see documents clustered around shared
  concept hubs, not 10 disconnected islands.

**This is the demo's knowledge-base story** - if it looks wrong here, it looks
wrong on stage.

## 5. Clause anchors are stable and sane

Open any document file. Each clause has a hidden anchor comment:

```markdown
## 7.2 Notice Period
<!-- anchor: 7-2 -->
```

**Check:** anchors are lowercase, hyphenated, and match the clause's own
numbering. No duplicates within a file.

**Why this matters:** `<doc-slug>#<anchor>` is the address every future
proposal, edit and notification points at. If anchors move, stored work breaks.

## 6. The API serves what was ingested

With the backend running:

```bash
curl http://localhost:8000/health
```

**Expect:** `{"status":"ok", ..., "counts":{"documents":10,"clauses":301,"concepts":219}}`

```bash
curl http://localhost:8000/api/documents
```

**Expect:** 10 entries. Confirm the two Options to Purchase have **different**
titles - `Option To Purchase (Private Commercial)` and `Option To Purchase (JTC
Industrial)`. They were identical earlier; that was a bug.

```bash
curl http://localhost:8000/api/documents/nda-template
```

**Expect:** 14 clauses, each with `ref`, `anchor`, `heading`, `text` and a
`concepts` list.

## 7. Interactive API docs

Open `http://localhost:8000/docs`. FastAPI's Swagger UI should list `/health`
and the two document endpoints, and let you run them from the browser.

## 8. Tests and lint

```bash
cd backend && python -m pytest -q
cd .. && python -m ruff check .
```

**Expect:** `38 passed` and `All checks passed!`. One Pydantic deprecation
warning is known and harmless.

## 9. Cold start from nothing

The real test that a teammate could clone this and run it.

```bash
rm -f data/app.db vault/graph.json vault/documents/*.md vault/concepts/*.md
python scripts/ingest.py --llm mock
```

**Expect:** rebuilds to 10 documents / 301 clauses with no errors. Concept count
will be **13**, not 219 - the mock provider uses a fixed keyword table. To
rebuild with real LLM tagging instead (takes ~10 minutes, one call per document):

```bash
python scripts/ingest.py --llm claude_cli
```

## 10. Client documents are not committable

```bash
git status --short
git check-ignore -v vault/documents/nda-template.md
```

**Expect:** `git status` shows **no** `vault/documents/*.md` files, and
`check-ignore` confirms the rule that excludes them.

**Why this matters:** the vault now contains the full text of the firm's
contracts, derived from the gitignored `data/inbox/`. I gitignored the generated
vault so a `git add -A` can't leak client contract text into git history. **Tell
me if you'd rather commit it** - it's a one-line change, and it's your call, but
the safe default is not committing client documents.

---

## Known issues - already found, not blocking

| # | Issue | Impact | When to fix |
|---|---|---|---|
| 1 | **Concept fragmentation.** 115 of 219 concepts are attached to a single clause (`Solicitors' Details`, `Forfeiture Sharing`). The hubs that matter are healthy - `Notice Period` spans 6 documents, `Governing Law` 8 - but half the graph is dust. | Retrieval still works via the hubs; the graph view will look noisy. | M3. Fix is a controlled vocabulary in the tagging prompt: seed the common Singapore commercial-contract concepts and let the model add new ones only when nothing fits. |
| 2 | **First clause of some documents is a cover-page blob** with anchor `s0` - party names, recitals and "THIS AGREEMENT made on..." collapsed into one clause. | Cosmetic. It's real document text, just not a real clause. | Optional. Would need a "front matter ends at clause 1" rule. |
| 3 | **Clause counts fell** from the first run (JVA 121 → 101, Tenancy 37 → 23) once empty and junk sections were filtered out. | None - the removed sections were page headers and form fields with no body. | Done deliberately. |
| 4 | **`.doc` file is not ingested.** One of nine source documents is legacy binary. | It appears in the vault with a `parse_error` and 0 clauses. | Convert it to `.docx` and re-run ingest, whenever convenient. |

## What is NOT in M1

Don't QA these - they aren't built: the dashboard UI, the Hansard scraper,
proposals, the task list, approve/apply, notifications. M1 is ingest only:
documents in, vault + graph out.
