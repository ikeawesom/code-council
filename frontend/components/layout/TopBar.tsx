import Avatar from "@/components/ui/Avatar";

export default function TopBar({
  userName,
  userRole,
  userInitials,
}: {
  userName: string;
  userRole: string;
  userInitials: string;
}) {
  const today = new Date().toLocaleDateString("en-SG", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <header className="fixed top-0 left-[240px] right-0 h-16 bg-surface border-b border-border-hairline z-40 flex items-center justify-between px-8">
      <div className="flex items-center gap-6 flex-1 max-w-xl">
        <div className="relative w-full max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-[18px]">
            search
          </span>
          <input
            className="w-full h-9 pl-9 pr-4 rounded-md bg-surface-subtle border border-transparent text-[13.5px] text-text-main placeholder:text-text-secondary/70 focus:outline-none focus:border-border-hairline focus:bg-surface transition-all"
            placeholder="Search clauses, documents, or parliament items"
            type="text"
          />
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="hidden md:flex items-center text-text-secondary text-[13px] font-medium">
          <span className="material-symbols-outlined text-text-muted text-[16px] mr-1.5">
            calendar_today
          </span>
          {today}
        </div>
        <div className="h-4 w-px bg-border-hairline hidden md:block" />
        <div className="flex items-center gap-2.5 py-1 px-1.5 rounded-md">
          <Avatar initials={userInitials} />
          <div className="flex flex-col text-left">
            <span className="text-[13px] text-text-main font-semibold leading-tight">
              {userName}
            </span>
            <span className="text-[11px] text-text-secondary leading-tight">{userRole}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
