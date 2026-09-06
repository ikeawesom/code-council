import Link from "next/link";
import { getTask } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import SeverityChip from "@/components/ui/SeverityChip";
import StatusChip from "@/components/ui/StatusChip";
import Badge from "@/components/ui/Badge";
import AffectedDocumentCard from "@/components/task-detail/AffectedDocumentCard";
import HansardSourcePanel from "@/components/task-detail/HansardSourcePanel";

// Screen 2: affected documents overview for one task (one parliament item).
export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  const id = Number(taskId);
  const task = Number.isFinite(id) ? await getTask(id) : null;

  if (task === null) {
    return (
      <div className="max-w-7xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load this task."
          action={
            <Link
              href="/tasks"
              className="text-[13px] font-medium text-primary hover:text-primary-hover"
            >
              Back to tasks
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-8 py-8 flex flex-col gap-6">
      <Link
        href="/tasks"
        className="inline-flex items-center gap-1.5 text-text-secondary hover:text-primary transition-colors text-[13px] font-medium w-fit"
      >
        <span className="material-symbols-outlined text-[18px]">
          arrow_back
        </span>
        Back to tasks
      </Link>

      <header className="flex flex-col gap-3 pb-6 border-b border-border-hairline">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityChip severity={task.severity} />
          <Badge label={task.item.legislation_type} />
          <StatusChip status={task.status} assignee={task.assignee} />
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

        <h1 className="text-[26px] font-semibold text-text-main tracking-tight leading-tight max-w-4xl">
          {task.item.title}
        </h1>

        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-text-secondary">
          <span className="font-semibold text-text-main">{task.reference}</span>
          <span className="text-border-hairline">&bull;</span>
          <span>
            {task.documents.length} document
            {task.documents.length === 1 ? "" : "s"} affected
          </span>
          <span className="text-border-hairline">&bull;</span>
          <span>
            {task.proposal_count} clause{task.proposal_count === 1 ? "" : "s"}{" "}
            flagged
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 flex flex-col gap-5">
          <div className="flex items-center gap-2 px-0.5">
            <h2 className="text-[18px] font-semibold tracking-tight text-text-main">
              Affected documents
            </h2>
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-text-main text-white text-[11px] font-bold">
              {task.documents.length}
            </span>
          </div>

          {task.documents.length === 0 ? (
            <EmptyState
              icon="task_alt"
              heading="No documents affected"
              description="This parliament item did not match any clauses in the vault."
            />
          ) : (
            task.documents.map((doc) => (
              <AffectedDocumentCard key={doc.id} doc={doc} taskId={task.id} />
            ))
          )}
        </div>

        <div className="lg:col-span-4">
          <HansardSourcePanel item={task.item} />
        </div>
      </div>
    </div>
  );
}
