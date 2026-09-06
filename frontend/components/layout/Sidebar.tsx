"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface SectorCount {
  sector: string;
  label: string;
  count: number;
}

const NAV = [
  { href: "/tasks", icon: "task_alt", label: "Tasks" },
  { href: "/inbox", icon: "inbox", label: "Inbox" },
  { href: "/documents", icon: "description", label: "Documents" },
  { href: "/parliament", icon: "account_balance", label: "Parliament" },
  { href: "/settings", icon: "settings", label: "Settings" },
] as const;

export default function Sidebar({
  tasksCount,
  inboxCount,
  sectors,
  liveLabel,
}: {
  tasksCount: number;
  inboxCount: number;
  sectors: SectorCount[];
  liveLabel: string | null;
}) {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[240px] bg-sidebar text-white z-50 flex flex-col justify-between border-r border-sidebar-border select-none">
      <div className="flex flex-col min-h-0">
        <div className="p-5 pb-4 border-b border-sidebar-border">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="material-symbols-outlined text-primary text-[22px]">gavel</span>
            <span className="text-[16px] font-semibold tracking-tight">Code Council</span>
          </div>
          <p className="text-[10.5px] uppercase tracking-[0.08em] text-[#8694A6] font-semibold leading-tight">
            Singapore legal advisory &amp; Hansard monitor
          </p>
        </div>

        <nav className="flex flex-col py-3 px-2 space-y-1 overflow-y-auto">
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            const badge =
              item.href === "/tasks" ? tasksCount : item.href === "/inbox" ? inboxCount : null;
            return (
              <div key={item.href} className="flex flex-col">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    "flex items-center justify-between px-3 py-2 rounded-md text-[13.5px] font-medium transition-colors " +
                    (active
                      ? "bg-primary text-white shadow-sm"
                      : "text-[#9CA9B8] hover:bg-white/5 hover:text-white")
                  }
                >
                  <span className="flex items-center gap-2.5">
                    <span className="material-symbols-outlined text-[19px]">{item.icon}</span>
                    <span>{item.label}</span>
                  </span>
                  {badge !== null && (
                    <span
                      className={
                        "inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-[11px] font-semibold " +
                        (active ? "bg-white/20 text-white" : "bg-white/10 text-[#C4D0DE]")
                      }
                    >
                      {badge}
                    </span>
                  )}
                </Link>

                {item.href === "/tasks" && sectors.length > 0 && (
                  <div className="flex flex-col pl-5 pr-1 py-1 space-y-0.5 text-[12px]">
                    {sectors.map((s) => (
                      <Link
                        key={s.sector}
                        href={`/tasks?sector=${encodeURIComponent(s.sector)}`}
                        className="flex items-center justify-between px-2.5 py-1 rounded text-[#9CA9B8] hover:bg-white/5 hover:text-white transition-colors"
                      >
                        <span className="truncate">{s.label}</span>
                        <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-white/10 text-white">
                          {s.count}
                        </span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-sidebar-border bg-[#0E141B]">
        <div className="flex items-center gap-2 text-[#8694A6] mb-1">
          <span className="w-2 h-2 rounded-full bg-status-approved inline-block animate-pulse" />
          <span className="text-[10px] font-semibold tracking-[0.08em] uppercase text-[#8694A6]">
            Live Hansard feed
          </span>
        </div>
        <p className="text-[11.5px] text-[#C4D0DE]/80 leading-snug">
          {liveLabel ?? "Not yet synced"}
        </p>
      </div>
    </aside>
  );
}

