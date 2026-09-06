import Link from "next/link";
import type { Notification } from "@/lib/api";
import Avatar from "@/components/ui/Avatar";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-SG", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

// Contract gives one prebuilt sentence (`message`), not separate name/document
// fields - so this bolds only the actor's own name, the one piece we can
// match reliably, rather than guessing at document names inside free text.
function highlightActor(message: string, actorName: string): React.ReactNode {
  if (!actorName || !message.includes(actorName)) return message;
  const parts = message.split(actorName);
  const out: React.ReactNode[] = [];
  parts.forEach((part, i) => {
    if (part) out.push(<span key={`t-${i}`}>{part}</span>);
    if (i < parts.length - 1) {
      out.push(
        <span key={`n-${i}`} className="font-semibold text-text-main">
          {actorName}
        </span>
      );
    }
  });
  return out;
}

// document_slug has no title field alongside it in the contract - this turns
// the kebab-case slug back into a readable label rather than showing raw slug.
function titleFromSlug(slug: string): string {
  return slug
    .replace(/^\d+-/, "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function NotificationRow({
  notification,
  onOpen,
}: {
  notification: Notification;
  onOpen: (id: number) => void;
}) {
  // Prefer the task the notification is about; the document page is the
  // fallback when the notification is not tied to a task.
  const href = notification.task_id
    ? `/tasks/${notification.task_id}`
    : notification.document_slug
      ? `/documents/${notification.document_slug}`
      : "/tasks";
  const actionLabel = notification.document_slug ? "View document" : "View tasks";
  const targetLabel = notification.document_slug
    ? titleFromSlug(notification.document_slug)
    : notification.task_reference
      ? `Task ${notification.task_reference}`
      : null;

  return (
    <Link
      href={href}
      onClick={() => onOpen(notification.id)}
      className={
        "relative flex items-start justify-between gap-4 p-5 border-b border-border-hairline last:border-b-0 transition-colors group " +
        (notification.read
          ? "bg-surface hover:bg-background"
          : "bg-primary-subtle/40 hover:bg-primary-subtle/70")
      }
    >
      <div className="flex items-start gap-3.5 flex-1 min-w-0">
        <div className="pt-2 shrink-0">
          <span
            className={"block w-2 h-2 rounded-full " + (notification.read ? "opacity-0" : "bg-primary")}
          />
        </div>
        <Avatar initials={notification.actor.initials} title={notification.actor.name} />
        <div className="flex flex-col min-w-0">
          <p className="text-[14.5px] leading-snug text-text-main">
            {highlightActor(notification.message, notification.actor.name)}
          </p>
          {targetLabel && <p className="text-[13px] text-text-secondary mt-1 truncate">{targetLabel}</p>}
          <p className="text-[11.5px] text-text-muted mt-1">{formatTime(notification.created_at)}</p>
        </div>
      </div>
      <div className="flex items-center self-center shrink-0">
        <span className="inline-flex items-center gap-1 text-[13px] font-medium text-text-secondary group-hover:text-primary transition-colors">
          {actionLabel}
          <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
        </span>
      </div>
    </Link>
  );
}
