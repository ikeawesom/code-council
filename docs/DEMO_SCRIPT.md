# Demo script - 3 minutes

Pre-flight: backend and frontend running, `python scripts/run_daily.py --offline`
already executed so the LLM cache is warm, browser at the dashboard, second
browser tab on the vault folder in Obsidian.

| Time | Beat |
|---|---|
| 0:00 | **The problem.** A lawyer reads Hansard every morning and cross-checks every contract by hand. Show the real sprs.parl.gov.sg page - dense, daily, unstructured. |
| 0:25 | **The knowledge base.** Obsidian open on `vault/` - the firm's contracts as linked markdown, clauses connected through legal concepts. Not a black box; plain files. |
| 0:50 | **07:00 happened.** Dashboard shows today's proposals, newest sitting first, severity-coded. |
| 1:15 | **One proposal, three panes.** Left: the parliamentary item with a link to the official report. Middle: the affected clause and what else in the graph touches it. Right: the suggested redline and the rationale. |
| 1:50 | **Approve.** Click. The vault file updates live, version bumps, the edit is recorded. |
| 2:10 | **The firm stays in sync.** Switch user to the second lawyer - notification: "the Warehouse Lease §7.2 was amended." |
| 2:30 | **Nothing leaves the firm.** The LLM sits behind a provider interface; swap `claude_cli` for the on-prem local model with one config line. Close on that. |

## Hard requirements for demo day
- `CC_OFFLINE=1` produces a full run with the network unplugged.
- The planted fixture item is visibly labelled as a demo fixture.
- The approve action visibly changes a file on disk - show the diff if there is time.
