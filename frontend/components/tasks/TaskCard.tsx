import Link from "next/link";
import type { Task } from "@/lib/api";
import SeverityChip from "@/components/ui/SeverityChip";
import Badge from "@/components/ui/Badge";
import StatusChip from "@/components/ui/StatusChip";

function formatSittingDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-SG", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatFlaggedAt(iso: string): string {
  try {
    const d = new Date(iso);
    const time = d.toLocaleTimeString("en-SG", {
      hour: "2-digit",
      minute: "2-digit",
    });
    const today = new Date().toDateString() === d.toDateString();
    return today
      ? `Flagged ${time} today`
      : `Flagged ${formatSittingDate(iso)}`;
  } catch {
    return "Flagged recently";
  }
}

// Screen 1 (morning briefing). The contract's task-list endpoint gives
// aggregate counts, not per-document titles/sectors - so the metadata row
// below shows document_count/proposal_count rather than inventing document
// names the API doesn't return at this level (see report for the full note).
export default function TaskCard({ task }: { task: Task }) {
  const tinted = task.status === "in_progress";

  const primaryAction = (() => {
    switch (task.status) {
      case "new":
        return (
          <Link
            href={`/tasks/${task.id}`}
            className="px-3.5 py-1.5 bg-primary hover:bg-primary-hover text-white rounded text-[13px] font-medium transition-colors inline-flex items-center gap-1 shadow-sm"
          >
            Review amendment
            <span className="material-symbols-outlined text-[15px]">
              arrow_forward
            </span>
          </Link>
        );
      case "in_progress":
        return (
          <Link
            href={`/tasks/${task.id}`}
            className="px-3 py-1.5 bg-surface-subtle hover:bg-border-hairline/40 text-text-main rounded text-[13px] font-medium transition-colors inline-flex items-center gap-1.5 shadow-sm"
          >
            <span className="material-symbols-outlined text-[15px] text-text-secondary">
              visibility
            </span>
            Continue review
          </Link>
        );
      case "approved":
        return (
          <Link
            href={`/tasks/${task.id}`}
            className="px-3.5 py-1.5 bg-background hover:bg-surface-subtle border border-border-hairline text-text-main rounded text-[13px] font-medium transition-colors inline-flex items-center gap-1.5 shadow-sm"
          >
            <span className="material-symbols-outlined text-[16px] text-status-approved">
              verified
            </span>
            View applied changes
          </Link>
        );
      case "dismissed":
        return (
          <Link
            href={`/tasks/${task.id}`}
            className="px-3.5 py-1.5 text-text-secondary hover:text-text-main rounded text-[13px] font-medium transition-colors inline-flex items-center gap-1.5"
          >
            View details
          </Link>
        );
    }
  })();

  return (
    <article
      className={
        "relative border rounded-lg p-6 shadow-sm transition-all hover:border-text-muted/40 " +
        (tinted
          ? "bg-status-progress/[0.04] border-status-progress/20"
          : "bg-surface border-border-hairline")
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityChip severity={task.severity} />
            <Badge label={task.item.legislation_type} />
            {/* {task.is_demo && (
              <span
                title="Planted for the demo - not scraped from a live Hansard sitting"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] tracking-[0.05em] uppercase font-semibold text-text-muted border border-dashed border-text-muted/50"
              >
                <span className="material-symbols-outlined text-[13px]">science</span>
                Demo fixture
              </span>
            )} */}
          </div>
          <span className="text-[13px] text-text-secondary font-mono">
            Ref: {task.reference}
          </span>
        </div>

        <div className="flex flex-col gap-1.5 max-w-3xl">
          <h2 className="text-[20px] font-medium text-text-main leading-snug tracking-tight">
            <Link
              href={`/tasks/${task.id}`}
              className="hover:text-primary transition-colors"
            >
              {task.item.title}
            </Link>
          </h2>
          {task.item.summary && (
            <p className="text-[14.5px] text-text-secondary leading-relaxed">
              {task.item.summary}
            </p>
          )}
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-3 border-t border-border-hairline/60">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[13px] text-text-secondary">
            <StatusChip status={task.status} assignee={task.assignee} />
            <span className="text-border-hairline">•</span>
            <span>
              {task.document_count} document
              {task.document_count === 1 ? "" : "s"}
            </span>
            <span className="text-border-hairline">•</span>
            <span>
              {task.proposal_count} clause{task.proposal_count === 1 ? "" : "s"}{" "}
              flagged
            </span>
            <span className="text-border-hairline">•</span>
            <span className="text-text-secondary/70">
              {formatFlaggedAt(task.created_at)}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {primaryAction}
          </div>
        </div>
      </div>
    </article>
  );
}
