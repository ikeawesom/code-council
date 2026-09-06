import Link from "next/link";
import { getTaskDocument, getUsers } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import SeverityChip from "@/components/ui/SeverityChip";
import HansardSourcePanel from "@/components/task-detail/HansardSourcePanel";
import RedlineDiff from "@/components/task-detail/RedlineDiff";
import ClauseAccordion from "@/components/task-detail/ClauseAccordion";
import ProposalActions from "@/components/task-detail/ProposalActions";

// Screen 3: the redline. `users[0]` stands in for the signed-in lawyer - the
// same no-real-auth convention AppShell/TopBar already use for the whole app.
export default async function TaskDocumentPage({
  params,
}: {
  params: Promise<{ taskId: string; docSlug: string }>;
}) {
  const { taskId, docSlug } = await params;
  const id = Number(taskId);

  const [detail, users] = await Promise.all([
    Number.isFinite(id) ? getTaskDocument(id, docSlug) : Promise.resolve(null),
    getUsers(),
  ]);

  if (detail === null) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load this clause redline."
          action={
            <Link href={`/tasks/${taskId}`} className="text-[13px] font-medium text-primary hover:text-primary-hover">
              Back to affected documents
            </Link>
          }
        />
      </div>
    );
  }

  const currentUserId = users?.[0]?.id ?? 1;
  const [primary, ...rest] = detail.proposals;

  if (!primary) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <EmptyState
          icon="task_alt"
          heading="No clauses flagged for this document"
          action={
            <Link href={`/tasks/${id}`} className="text-[13px] font-medium text-primary hover:text-primary-hover">
              Back to affected documents
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-8 py-8 flex flex-col gap-6">
      <Link
        href={`/tasks/${id}`}
        className="inline-flex items-center gap-1.5 text-text-secondary hover:text-primary transition-colors text-[13px] font-medium w-fit"
      >
        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        Back to affected documents
      </Link>

      <header className="flex flex-col gap-1.5 pb-6 border-b border-border-hairline max-w-3xl">
        <h1 className="text-[24px] font-semibold text-text-main tracking-tight leading-tight">
          {detail.document.title}
        </h1>
        <div className="flex items-center gap-2 flex-wrap text-[13px] text-text-secondary">
          <SeverityChip severity={detail.document.severity} />
          <span className="text-border-hairline">&bull;</span>
          <span className="font-medium text-text-main">{detail.task.reference}</span>
          <span className="text-border-hairline">&bull;</span>
          <span>Version {detail.document.version}</span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <main className="flex flex-col gap-5 lg:col-span-8">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-bold tracking-wider uppercase text-primary">
              Suggested amendment
            </span>
            <span className="text-[12px] text-text-secondary font-medium">
              1 of {detail.proposals.length} clause{detail.proposals.length === 1 ? "" : "s"} flagged
            </span>
          </div>

          <section className="bg-surface border border-border-hairline rounded-lg p-6 shadow-sm flex flex-col gap-5">
            <div className="flex items-start justify-between gap-3 pb-4 border-b border-border-hairline">
              <div>
                <h2 className="text-[19px] font-semibold text-text-main tracking-tight">
                  Clause {primary.clause.number} &mdash; {primary.clause.heading}
                </h2>
                <p className="text-[13px] text-text-secondary mt-0.5">
                  {detail.document.title} &bull; Version {detail.document.version}
                </p>
              </div>
              <SeverityChip severity={primary.severity} />
            </div>

            <div className="bg-surface-subtle border border-border-hairline rounded-md p-5">
              <RedlineDiff diff={primary.diff} />
            </div>

            <div className="bg-surface-subtle border border-border-hairline rounded-md p-4">
              <div className="flex items-center gap-2 mb-1.5 text-text-main">
                <span className="material-symbols-outlined text-[19px] text-primary">error_outline</span>
                <h3 className="text-[14.5px] font-semibold text-text-main">Why this was flagged</h3>
              </div>
              <p className="text-[13.5px] text-text-secondary leading-relaxed">{primary.rationale}</p>
            </div>

            <ProposalActions
              proposal={primary}
              userId={currentUserId}
              documentTitle={detail.document.title}
              documentVersion={detail.document.version}
            />
          </section>

          {rest.map((p) => (
            <ClauseAccordion
              key={p.id}
              proposal={p}
              userId={currentUserId}
              documentTitle={detail.document.title}
              documentVersion={detail.document.version}
            />
          ))}
        </main>

        <div className="lg:col-span-4">
          <HansardSourcePanel item={detail.task.item} />
        </div>
      </div>
    </div>
  );
}
