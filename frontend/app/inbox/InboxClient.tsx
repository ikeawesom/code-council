"use client";

import { useState } from "react";
import type { Notification } from "@/lib/api";
import { markNotificationRead } from "@/lib/api";
import EmptyState from "@/components/ui/EmptyState";
import NotificationRow from "@/components/inbox/NotificationRow";

const BUCKET_ORDER = ["Today", "Yesterday", "Earlier"] as const;
type Bucket = (typeof BUCKET_ORDER)[number];

function bucketFor(iso: string): Bucket {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return "Earlier";
}

// Screen 4: notification feed. Holds its own read/unread state locally so a
// row click feels instant, while POST /api/notifications/{id}/read fires
// alongside it (fire-and-forget - a failed mark-read shouldn't block navigation).
export default function InboxClient({ notifications }: { notifications: Notification[] }) {
  const [items, setItems] = useState(notifications);

  const handleOpen = (id: number) => {
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    markNotificationRead(id).catch(() => {});
  };

  if (items.length === 0) {
    return (
      <EmptyState
        icon="task_alt"
        heading="You're all caught up"
        description="No colleague activity or system alerts yet. New items appear here as the 07:00 scan runs and colleagues act on proposals."
      />
    );
  }

  const unreadCount = items.filter((n) => !n.read).length;

  const grouped: Record<Bucket, Notification[]> = { Today: [], Yesterday: [], Earlier: [] };
  for (const n of items) grouped[bucketFor(n.created_at)].push(n);

  return (
    <div className="flex flex-col w-full">
      <div className="flex items-baseline gap-3 pb-3 border-b border-border-hairline mb-6">
        <h1 className="text-[30px] font-medium text-text-main tracking-tight leading-tight">Inbox</h1>
        <span className="text-[15px] text-text-secondary">
          {unreadCount} unread update{unreadCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="bg-surface border border-border-hairline rounded-lg shadow-sm overflow-hidden flex flex-col">
        {BUCKET_ORDER.filter((b) => grouped[b].length > 0).map((bucket) => (
          <div key={bucket} className="flex flex-col">
            <div className="bg-surface-subtle px-6 py-2.5 border-b border-border-hairline">
              <span className="text-[12px] uppercase tracking-[0.08em] text-text-main font-bold">
                {bucket}
              </span>
            </div>
            {grouped[bucket].map((n) => (
              <NotificationRow key={n.id} notification={n} onOpen={handleOpen} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
