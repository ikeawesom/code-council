"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Task, TaskStatus } from "@/lib/api";
import FilterPills from "@/components/ui/FilterPills";
import EmptyState from "@/components/ui/EmptyState";
import TaskCard from "@/components/tasks/TaskCard";

type FilterValue = "all" | TaskStatus;

export default function TasksClient({
  tasks,
  activeSector,
}: {
  tasks: Task[];
  activeSector?: { value: string; label: string } | null;
}) {
  const [active, setActive] = useState<FilterValue>("all");

  const counts = useMemo(() => {
    const c: Record<FilterValue, number> = {
      all: tasks.length,
      new: 0,
      in_progress: 0,
      approved: 0,
      dismissed: 0,
    };
    for (const t of tasks) c[t.status]++;
    return c;
  }, [tasks]);

  const options = [
    { value: "all", label: "All", count: counts.all },
    { value: "new", label: "New", count: counts.new },
    { value: "in_progress", label: "In progress", count: counts.in_progress },
    { value: "approved", label: "Approved", count: counts.approved },
    { value: "dismissed", label: "Dismissed", count: counts.dismissed },
  ];

  const visible = active === "all" ? tasks : tasks.filter((t) => t.status === active);

  const latestSitting = tasks.reduce<string | null>((latest, t) => {
    if (!latest || t.item.sitting_date > latest) return t.item.sitting_date;
    return latest;
  }, null);

  return (
    <div className="flex flex-col w-full">
      <div className="flex flex-col mb-7">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-3 pb-3 border-b border-border-hairline">
          <div className="flex flex-col">
            <div className="flex items-center gap-3">
              <h1 className="text-[30px] font-medium text-text-main tracking-tight leading-tight">
                Tasks
              </h1>
              <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-full text-[12px] font-semibold bg-text-main text-white">
                {tasks.length} total
              </span>
              {activeSector && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-primary/10 text-primary">
                  Practice area: {activeSector.label}
                  <Link
                    href="/tasks"
                    className="text-primary/70 hover:text-primary"
                    aria-label="Show all practice areas"
                  >
                    ×
                  </Link>
                </span>
              )}
            </div>
            <p className="text-[14px] text-text-secondary mt-1">
              {tasks.length === 0
                ? "Nothing flagged yet."
                : `${tasks.length} item${tasks.length === 1 ? "" : "s"} flagged${
                    latestSitting
                      ? ` from Parliament, ${new Date(latestSitting).toLocaleDateString("en-SG", {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                        })}`
                      : ""
                  }`}
            </p>
          </div>
        </div>
        <div className="pt-4">
          <FilterPills options={options} active={active} onChange={(v) => setActive(v as FilterValue)} />
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon="task_alt"
          heading={
            tasks.length === 0
              ? "Nothing flagged today"
              : "No tasks match this filter"
          }
          description={
            tasks.length === 0
              ? "Parliament hasn't produced anything that touches the firm's contracts yet."
              : "Try a different status filter, or select All to see everything."
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          {visible.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      )}
    </div>
  );
}
