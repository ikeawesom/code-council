import { getTasks } from "@/lib/api";
import { sectorLabel } from "@/lib/sector";
import EmptyState from "@/components/ui/EmptyState";
import TasksClient from "./TasksClient";

// Screen 1: the morning briefing. Fetches tasks once server-side, optionally
// scoped to a practice area via `?sector=` (the sidebar's per-sector links
// land here); the status filter pills then operate on that array client-side
// (see TasksClient) so switching filters never re-hits the API.
export default async function TasksPage({
  searchParams,
}: {
  searchParams: Promise<{ sector?: string }>;
}) {
  const { sector } = await searchParams;
  const tasks = await getTasks(sector ? { sector } : undefined);

  if (tasks === null) {
    return (
      <div className="max-w-7xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load today's tasks."
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-8 py-8">
      <TasksClient
        tasks={tasks}
        activeSector={sector ? { value: sector, label: sectorLabel(sector) } : null}
      />
    </div>
  );
}
