"use client";

export interface FilterOption {
  value: string;
  label: string;
  count: number;
}

export default function FilterPills({
  options,
  active,
  onChange,
}: {
  options: FilterOption[];
  active: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      {options.map((opt) => {
        const isActive = opt.value === active;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={
              "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[13px] font-medium transition-all shrink-0 " +
              (isActive
                ? "bg-primary text-white shadow-sm"
                : "bg-surface-subtle text-text-main hover:bg-border-hairline/40")
            }
          >
            <span>{opt.label}</span>
            <span
              className={
                "px-1.5 py-0.5 rounded-full text-[11px] font-semibold " +
                (isActive ? "bg-white/20 text-white" : "bg-surface text-text-secondary")
              }
            >
              {opt.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
