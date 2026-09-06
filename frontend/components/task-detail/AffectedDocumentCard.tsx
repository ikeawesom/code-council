import Link from "next/link";
import type { AffectedDocument } from "@/lib/api";
import SeverityChip from "@/components/ui/SeverityChip";

// Screen 2 - one card per document a task touches. `preview` is a whole-clause
// before/after pair from the API (not a word-level diff), so it's rendered as
// two quoted lines rather than fed through RedlineDiff.
export default function AffectedDocumentCard({
  doc,
  taskId,
}: {
  doc: AffectedDocument;
  taskId: number;
}) {
  const accent =
    doc.severity === "high"
      ? "bg-severity-high"
      : doc.severity === "medium"
        ? "bg-severity-medium"
        : "bg-severity-low";

  return (
    <article className="relative bg-surface border border-border-hairline rounded-lg shadow-sm p-6 overflow-hidden transition-shadow hover:shadow-md">
      <div className={`absolute top-0 left-0 bottom-0 w-1 ${accent}`} />
      <div className="pl-3 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-[17px] font-semibold text-text-main tracking-tight">{doc.title}</h3>
            <p className="text-[13px] text-text-secondary">
              {doc.sector} &bull; Version {doc.version}
            </p>
          </div>
          <div className="flex items-center gap-1.5 self-start shrink-0">
            <span className="px-2 py-0.5 rounded text-[11px] uppercase font-semibold tracking-wide bg-surface-subtle text-text-secondary">
              {doc.proposal_count} clause{doc.proposal_count === 1 ? "" : "s"} flagged
            </span>
            <SeverityChip severity={doc.severity} />
          </div>
        </div>

        {doc.preview && (
          <div className="bg-surface-subtle rounded-lg p-4 flex flex-col gap-2 border border-border-hairline/60">
            <div className="text-[11px] uppercase font-semibold text-text-muted tracking-wide">
              {doc.preview.heading} &bull; {doc.preview.clause_ref}
            </div>
            <p className="text-[13.5px] leading-relaxed">
              <del className="text-severity-high bg-severity-high/10 px-1 rounded-[2px]">
                {doc.preview.before}
              </del>
            </p>
            <p className="text-[13.5px] leading-relaxed">
              <ins className="text-status-approved bg-status-approved/10 px-1 rounded-[2px] no-underline">
                {doc.preview.after}
              </ins>
            </p>
          </div>
        )}

        <div className="flex items-center justify-end pt-1">
          <Link
            href={`/tasks/${taskId}/documents/${doc.slug}`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary hover:bg-primary-hover text-white text-[13px] font-medium shadow-sm transition-colors"
          >
            Review suggested amendments
            <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
          </Link>
        </div>
      </div>
    </article>
  );
}
