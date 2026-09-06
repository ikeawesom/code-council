import Link from "next/link";
import type { DocumentSummary } from "@/lib/api";

const FILE_ICON: Record<string, string> = {
  pdf: "picture_as_pdf",
  docx: "description",
  doc: "description",
};

function formatUpdated(iso: string): string {
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

// Screen 5 row. Every value here is real: clause_count / version / updated_at /
// open_task_count all come straight from GET /api/documents - no invented
// "Synced HH:MM" sync language, no repository hashes (see UI_PLAN.md section 7).
export default function DocumentRow({ document }: { document: DocumentSummary }) {
  const icon = FILE_ICON[document.file_type] ?? "description";
  return (
    <Link
      href={`/documents/${document.slug}`}
      className="flex flex-col sm:flex-row sm:items-center justify-between px-5 py-3.5 hover:bg-surface-subtle/60 transition-colors group"
    >
      <div className="flex items-start sm:items-center gap-3.5 min-w-0">
        <div className="w-8 h-8 rounded bg-surface-subtle border border-border-hairline flex items-center justify-center shrink-0 text-text-secondary group-hover:text-primary group-hover:border-primary/40 transition-colors">
          <span className="material-symbols-outlined text-[18px]">{icon}</span>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-[14px] font-medium text-text-main group-hover:text-primary transition-colors truncate">
              {document.title}
            </span>
            {document.open_task_count > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-primary-subtle text-primary">
                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                {document.open_task_count} open task{document.open_task_count === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <p className="text-[13px] text-text-secondary mt-0.5">
            {document.clause_count} clause{document.clause_count === 1 ? "" : "s"} &middot; Version{" "}
            {document.version} &middot; Updated {formatUpdated(document.updated_at)}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-end gap-3 mt-2 sm:mt-0 shrink-0">
        <span className="material-symbols-outlined text-text-muted group-hover:text-primary group-hover:translate-x-0.5 transition-all text-[18px]">
          chevron_right
        </span>
      </div>
    </Link>
  );
}
