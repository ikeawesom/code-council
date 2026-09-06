import { getNotifications, getTasks, getUsers } from "@/lib/api";
import { sectorLabel } from "@/lib/sector";
import Sidebar, { type SectorCount } from "./Sidebar";
import TopBar from "./TopBar";

// The shared chrome for every route: 240px fixed sidebar + top bar + content.
// Counts shown here are real, derived from the API - never fabricated:
//   - Tasks / Inbox badges: live counts from /api/tasks and /api/notifications
//   - Per-sector sidebar counts: distinct tasks from /api/tasks whose
//     `sectors` field includes that sector. A task can span multiple
//     documents in the same sector (e.g. two consultancy agreements both in
//     energy-and-infrastructure) - it must only count once, so this counts
//     tasks, not documents.
// If the API is unreachable every count falls back to 0 - the shell still
// renders so a page's own EmptyState can explain what's wrong.
export default async function AppShell({ children }: { children: React.ReactNode }) {
  const users = await getUsers();
  const currentUser = users?.[0] ?? null;

  const [tasks, notifications] = await Promise.all([
    getTasks(),
    currentUser ? getNotifications(currentUser.id) : Promise.resolve(null),
  ]);

  const tasksCount = tasks?.length ?? 0;
  const inboxCount = notifications?.unread ?? 0;

  const sectorCounts = new Map<string, number>();
  for (const task of tasks ?? []) {
    for (const sector of task.sectors) {
      sectorCounts.set(sector, (sectorCounts.get(sector) ?? 0) + 1);
    }
  }
  const sectors: SectorCount[] = Array.from(sectorCounts.entries())
    .map(([sector, count]) => ({ sector, label: sectorLabel(sector), count }))
    .filter((s) => s.count > 0)
    .sort((a, b) => b.count - a.count);

  const liveLabel = tasks
    ? `${tasks.length} item${tasks.length === 1 ? "" : "s"} synced from Official SG Hansard`
    : null;

  return (
    <div className="min-h-screen">
      <Sidebar
        tasksCount={tasksCount}
        inboxCount={inboxCount}
        sectors={sectors}
        liveLabel={liveLabel}
      />
      <div className="pl-[240px] flex flex-col min-h-screen">
        <TopBar
          userName={currentUser?.name ?? "Guest"}
          userRole={currentUser?.role ?? "Not signed in"}
          userInitials={currentUser?.initials ?? "?"}
        />
        <main className="flex-1 pt-16">{children}</main>
      </div>
    </div>
  );
}
