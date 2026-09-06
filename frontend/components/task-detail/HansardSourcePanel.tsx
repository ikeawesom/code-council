import type { ParliamentItemSummary } from "@/lib/api";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-SG", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// Screens 2 & 3, right column. Every field here is real data from the
// scraped parliament item - no invented ministry names, sitting numbers, or
// ministry attribution beyond what the API returns (see docs/UI_PLAN.md
// section 7, "fiction to cut").
export default function HansardSourcePanel({ item }: { item: ParliamentItemSummary }) {
  return (
    <aside className="flex flex-col gap-3">
      <div className="flex items-center justify-between px-0.5">
        <span className="text-[12px] font-bold tracking-wider uppercase text-primary">
          What changed in Parliament
        </span>
      </div>
      <article className="bg-surface border border-border-hairline rounded-lg p-5 shadow-sm flex flex-col gap-4">
        <div>
          <span className="inline-block text-[11px] uppercase font-bold text-text-secondary bg-surface-subtle px-2 py-0.5 rounded border border-border-hairline mb-1.5 capitalize">
            {item.item_type}
          </span>
          <h2 className="text-[16px] font-semibold text-text-main leading-snug">{item.title}</h2>
        </div>

        <div className="space-y-1.5 py-2.5 border-y border-border-hairline text-[13px] text-text-secondary">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-text-muted">Date</span>
            <span className="text-text-main font-medium text-right">{formatDate(item.sitting_date)}</span>
          </div>
          {item.speaker && (
            <div className="flex flex-col mt-0.5">
              <span className="text-text-muted">Speaker</span>
              <span className="text-text-main font-medium leading-tight">{item.speaker}</span>
            </div>
          )}
        </div>

        {item.summary && (
          <blockquote className="bg-surface-subtle border-l-2 border-primary p-3.5 text-[13px] text-text-main leading-relaxed italic rounded-r">
            &ldquo;{item.summary}&rdquo;
          </blockquote>
        )}

        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:text-primary-hover font-semibold text-[13px] transition-colors underline underline-offset-4 decoration-primary/40 hover:decoration-primary w-fit"
          >
            Read full Hansard report
            <span className="material-symbols-outlined text-[15px]">north_east</span>
          </a>
        )}
      </article>
    </aside>
  );
}
