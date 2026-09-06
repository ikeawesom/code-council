// Document view: rendered clause list + edit history from GET /api/documents/{slug}.
import Link from "next/link";
import { getDocument } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import UnsupportedFileNotice from "@/components/documents/UnsupportedFileNotice";

function formatDate(iso: string): string {
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

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const doc = await getDocument(slug);

  if (doc === null) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't load this document"
          description="The Code Council API may be down, or this document isn't in the vault. Go back to Documents and try again."
          action={
            <Link
              href="/documents"
              className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded text-[13px] font-medium transition-colors"
            >
              Back to Documents
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8 flex flex-col gap-8">
      <div className="flex items-center gap-2 text-[12px] uppercase tracking-[0.08em] font-semibold text-text-secondary">
        <Link href="/documents" className="hover:text-primary transition-colors">
          Documents
        </Link>
        <span className="text-border-hairline">/</span>
        <span className="text-text-main">{doc.title}</span>
      </div>

      <div className="flex flex-col gap-2 pb-6 border-b border-border-hairline">
        <h1 className="text-[28px] font-medium text-text-main tracking-tight leading-snug">
          {doc.title}
        </h1>
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-text-secondary">
          <span>
            {doc.clause_count} clause{doc.clause_count === 1 ? "" : "s"}
          </span>
          <span className="text-border-hairline">&middot;</span>
          <span>Version {doc.version}</span>
          <span className="text-border-hairline">&middot;</span>
          <span className="uppercase">{doc.file_type}</span>
          <span className="text-border-hairline">&middot;</span>
          <span>Updated {formatDate(doc.updated_at)}</span>
          {doc.open_task_count > 0 && (
            <>
              <span className="text-border-hairline">&middot;</span>
              <span className="text-primary font-medium">
                {doc.open_task_count} open task{doc.open_task_count === 1 ? "" : "s"}
              </span>
            </>
          )}
        </div>
      </div>

      {doc.parse_error ? (
        <UnsupportedFileNotice document={doc} />
      ) : (
        <section className="flex flex-col gap-3">
          <h2 className="text-[16px] font-semibold text-text-main">Clauses</h2>
          {doc.clauses.length === 0 ? (
            <p className="text-[13.5px] text-text-secondary">
              This document has not been ingested with clause segmentation yet.
            </p>
          ) : (
            <div className="flex flex-col divide-y divide-border-hairline bg-surface border border-border-hairline rounded-lg overflow-hidden">
              {doc.clauses.map((c) => (
                <div key={c.anchor} className="p-5 flex flex-col gap-1.5">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-[13px] font-mono text-text-muted">{c.number}</span>
                    <span className="text-[14.5px] font-medium text-text-main">{c.heading}</span>
                  </div>
                  <p className="text-[14px] text-text-secondary leading-relaxed whitespace-pre-wrap">
                    {c.text}
                  </p>
                  {c.concepts.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {c.concepts.map((concept) => (
                        <span
                          key={concept}
                          className="px-2 py-0.5 rounded-full text-[11px] bg-surface-subtle text-text-secondary border border-border-hairline"
                        >
                          {concept}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-[16px] font-semibold text-text-main">Edit history</h2>
        {doc.history.length === 0 ? (
          <p className="text-[13.5px] text-text-secondary">No edits recorded for this document yet.</p>
        ) : (
          <div className="flex flex-col divide-y divide-border-hairline bg-surface border border-border-hairline rounded-lg overflow-hidden">
            {doc.history.map((h, i) => (
              <div key={`${h.clause_ref}-${i}`} className="p-5 flex flex-col gap-2">
                <div className="flex flex-wrap items-center justify-between gap-1.5 text-[13px] text-text-secondary">
                  <span className="font-mono text-text-muted">{h.clause_ref}</span>
                  <span>
                    {h.user?.name ?? "Unknown"} &middot; {formatDate(h.created_at)} &middot; v{h.version_after}
                  </span>
                </div>
                <div className="grid sm:grid-cols-2 gap-3 text-[13.5px]">
                  <div className="rounded bg-severity-high/[0.04] border border-severity-high/15 p-3">
                    <p className="text-[10.5px] uppercase tracking-wide text-severity-high font-semibold mb-1">
                      Before
                    </p>
                    <p className="text-text-secondary whitespace-pre-wrap">{h.before_text}</p>
                  </div>
                  <div className="rounded bg-status-approved/[0.05] border border-status-approved/15 p-3">
                    <p className="text-[10.5px] uppercase tracking-wide text-status-approved font-semibold mb-1">
                      After
                    </p>
                    <p className="text-text-main whitespace-pre-wrap">{h.after_text}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
