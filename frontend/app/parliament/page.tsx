import Link from "next/link";
import { getParliament } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import Badge from "@/components/ui/Badge";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-SG", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// List of scraped Hansard items from GET /api/parliament. `sitting` is real
// fixture metadata (parliament/session/volume/sitting numbers) - never
// hard-coded, per docs/UI_PLAN.md section 7's "Fix" note on the invented
// "Session 14 - Sitting No. 38" text in the Stitch export.
export default async function ParliamentPage() {
  const data = await getParliament();

  if (data === null) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load Hansard items."
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8 flex flex-col gap-6">
      <div className="flex flex-col gap-2 pb-6 border-b border-border-hairline">
        <h1 className="text-[30px] font-medium text-text-main tracking-tight leading-tight">
          Parliament
        </h1>
        <p className="text-[14.5px] text-text-secondary">
          {data.items.length} item{data.items.length === 1 ? "" : "s"} scraped from the Singapore
          Parliament Reports (Hansard)
        </p>
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-text-secondary mt-1">
          <span className="font-medium text-text-main">Parliament No. {data.sitting.parliament_no}</span>
          <span className="text-border-hairline">&middot;</span>
          <span>Session No. {data.sitting.session_no}</span>
          <span className="text-border-hairline">&middot;</span>
          <span>Volume No. {data.sitting.volume_no}</span>
          <span className="text-border-hairline">&middot;</span>
          <span>Sitting No. {data.sitting.sitting_no}</span>
        </div>
      </div>

      {data.items.length === 0 ? (
        <EmptyState
          icon="account_balance"
          heading="No Hansard items yet"
          description="Run scripts/run_daily.py --offline to replay the scraped sitting."
        />
      ) : (
        <div className="flex flex-col divide-y divide-border-hairline bg-surface border border-border-hairline rounded-lg overflow-hidden">
          {data.items.map((item) => (
            <div key={item.id} className="p-5 flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge label={item.legislation_type} />
                <span className="text-[11px] px-2 py-0.5 rounded uppercase tracking-wide font-semibold bg-surface-subtle text-text-secondary border border-border-hairline">
                  {item.item_type}
                </span>
                {item.task_reference && (
                  <Link
                    href={item.task_id ? `/tasks/${item.task_id}` : "/tasks"}
                    className="text-[11px] px-2 py-0.5 rounded uppercase tracking-wide font-semibold bg-primary-subtle text-primary hover:bg-primary/20 transition-colors"
                    title="Open Tasks to find this flagged item"
                  >
                    Flagged: {item.task_reference}
                  </Link>
                )}
              </div>
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="text-[15.5px] font-medium text-text-main hover:text-primary transition-colors leading-snug"
              >
                {item.title}
              </a>
              {item.summary && (
                <p className="text-[13.5px] text-text-secondary leading-relaxed">{item.summary}</p>
              )}
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-text-secondary">
                <span>{formatDate(item.sitting_date)}</span>
                {item.speaker && (
                  <>
                    <span className="text-border-hairline">&middot;</span>
                    <span>{item.speaker}</span>
                  </>
                )}
                <span className="text-border-hairline">&middot;</span>
                <span className="font-mono text-text-muted truncate">{item.vault_path}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
