# Lex Sentinel

A personal AI assistant that watches Singapore's Parliament for a law firm.

Every morning at 07:00 SGT it scrapes the Hansard reports at
[sprs.parl.gov.sg](https://sprs.parl.gov.sg/), compares them against the firm's
own contracts, and by 08:00 has a dashboard of proposals waiting: *this
parliamentary item affects clause 7.2 of your Warehouse Lease - here is the
suggested redline*. The lawyer approves, the knowledge base updates itself, and
everyone else who touches that document is notified.

Built for a Tech x Law hackathon.

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
python scripts/run_daily.py              # scrape -> match -> proposals   (M3, not built yet)
```

`ingest.py` flags: `--llm mock|claude_cli|local` overrides the provider,
`--force` re-tags concepts that are already recorded, `--only <slug>` ingests a
single document. Re-running is idempotent - the vault markdown comes out
byte-identical apart from `ingested_at`, and no database row is duplicated.

The sub-folder name under `data/inbox/` becomes the document's practice sector,
so `data/inbox/real-estate/lease.pdf` is filed under `real-estate`. Add a new
sector by creating a folder; nothing in the code needs to change.

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI, SQLite, APScheduler, scraper, LLM analysis |
| `frontend/` | Next.js dashboard |
| `vault/` | the knowledge base - plain markdown, Obsidian-compatible |
| `data/` | inbox (your documents), fixtures (cached Hansard), llm_cache |
| `scripts/` | ingest, daily run, demo seeding |

## Privacy

Client documents never need to leave the network: the LLM layer is an interface
with a `local` (on-prem Ollama) implementation alongside the `claude_cli` one
used for the demo. `data/inbox/` is gitignored.
