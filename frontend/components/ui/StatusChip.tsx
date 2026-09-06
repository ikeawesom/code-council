import type { Assignee, TaskStatus } from "@/lib/api";
import Avatar from "./Avatar";

const LABEL: Record<TaskStatus, string> = {
  new: "New",
  in_progress: "In progress",
  approved: "Approved",
  dismissed: "Dismissed",
};

const COLOR: Record<TaskStatus, string> = {
  new: "bg-status-new/10 text-status-new",
  in_progress: "bg-status-progress/10 text-status-progress",
  approved: "bg-status-approved/10 text-status-approved",
  dismissed: "bg-status-dismissed/10 text-status-dismissed",
};

// Renders the assignee's avatar + name for in_progress - the anti-duplication
// signal ("who already has this") that a bare status word can't carry.
export default function StatusChip({
  status,
  assignee,
}: {
  status: TaskStatus;
  assignee?: Assignee | null;
}) {
  if (status === "in_progress" && assignee) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 pl-1 pr-2.5 py-0.5 rounded-full text-[12.5px] font-medium ${COLOR[status]}`}
      >
        <Avatar initials={assignee.initials} size="sm" title={assignee.name} />
        {assignee.name}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[12.5px] font-medium ${COLOR[status]}`}
    >
      {LABEL[status]}
    </span>
  );
}
