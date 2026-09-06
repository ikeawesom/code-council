import { getNotifications, getUsers } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import InboxClient from "./InboxClient";

// Screen 4: notification feed for the current user (first user from
// GET /api/users - same "current user" convention AppShell uses for the top bar).
export default async function InboxPage() {
  const users = await getUsers();
  const currentUser = users?.[0] ?? null;

  if (!currentUser) {
    return (
      <div className="max-w-4xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load notifications."
        />
      </div>
    );
  }

  const data = await getNotifications(currentUser.id);

  if (data === null) {
    return (
      <div className="max-w-4xl mx-auto px-8 py-8">
        <EmptyState
          icon="cloud_off"
          heading="Can't reach the Code Council API"
          description="Start the backend (uvicorn app.main:app --reload --port 8000 from backend/) and refresh to load notifications."
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-8 py-8">
      <InboxClient notifications={data.notifications} />
    </div>
  );
}
