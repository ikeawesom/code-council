# QA - M4 dashboard (+ the M5 apply/notify path)

11 manual tests. Run them in order; 6 and 7 are the ones that matter on stage.

## Start

```
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

If a port is already held, kill the listener first - a failed restart silently
serves the OLD build, which cost time during this session:

```
Get-NetTCPConnection -LocalPort 3000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## State the tests assume

|                |                                                                                                                              |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `CC-2026-0002` | the **planted demo** item. High. 3 pending proposals on the tenancy agreement. Untouched - this is your stage task.          |
| `CC-2026-0001` | genuinely scraped. Spans 2 consultancy agreements. 3 of its 4 proposals are already approved, so it shows a real edit trail. |

## Tests

1. **API health.** `curl localhost:8000/health` -> 10 documents, 509 clauses,
   125 concepts.
2. **Tasks list.** `/tasks` shows both tasks. `CC-2026-0002` carries a visible
   "Demo fixture" pill - it must never look scraped. Filter pills narrow the list.
3. **Two badges only.** Severity colour + `Amendment`/`New Legislation`. Any
   third badge kind is a bug (the demo-fixture pill is deliberate and separate).
4. **Task detail.** `/tasks/2` - the Hansard panel shows the real item title,
   date, speaker and a working link out. One affected-document card per document.
5. **Document list.** `/documents` groups by practice area - 9 documents over
   4 sectors, each with a clause count and version.
6. **THE MONEY SHOT.** `/tasks/2/documents/01-tenancy-agreement-pte` - the
   redline renders red strikethrough and green underline, in body font, and reads
   like a contract. Expect ~2 deletions and ~4 insertions on `4(k) Option to
Renew`. A green-only diff means the proposals were regenerated with the mock
   judge; re-run the analysis with `claude_cli`.
7. **Approve end to end.** Approve a proposal on `CC-2026-0002`. Confirm dialog
   appears; after approving, check in order:
   - the proposal status flips to approved,
   - `vault/documents/01-tenancy-agreement-pte.md` contains the new clause text,
   - its frontmatter `version` bumped, and matches the version the UI shows,
   - `/inbox` shows a notification for the other lawyer on that document.
     This is M5; if it works, the product story is complete.
8. **Reject.** Rejecting only changes status - no vault write, no version bump.
9. **Inbox.** `/inbox` rows link through to the task. Clicking marks read.
10. **Parliament.** `/parliament` shows sitting numbers **15 / 1 / 96 / 34** for
    5 Aug 2026. These come from the fixture metadata; hard-coded numbers are a bug.
11. **Offline replay.** `python scripts/run_daily.py --offline --llm mock`
    completes with no network and creates nothing new (everything is tasked).

## Known, deliberate

- `CC-2026-0002` shows 1 affected document, not 3. Finer clause chunking gives
  the tenancy agreement a BM25 advantage; a per-document cap in `retrieve.py`
  would fix it. Deferred - see `PLAN.md`.
- No partner sign-off step. `new -> in_progress -> approved` by the assignee.
- No auth: the acting user is the first user from `/api/users` (John Goh).
