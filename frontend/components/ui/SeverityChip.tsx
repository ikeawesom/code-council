import type { Severity } from "@/lib/api";

const LABEL: Record<Severity, string> = {
  high: "High impact",
  medium: "Medium impact",
  low: "Low impact",
};

const COLOR: Record<Severity, string> = {
  high: "bg-severity-high/10 text-severity-high",
  medium: "bg-severity-medium/10 text-severity-medium",
  low: "bg-severity-low/10 text-severity-low",
};

export default function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[12px] font-medium ${COLOR[severity]}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current inline-block" />
      {LABEL[severity]}
    </span>
  );
}
