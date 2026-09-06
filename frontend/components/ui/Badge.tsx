// The one other badge kind allowed alongside SeverityChip: legislation type.
// Exactly two badge kinds exist in this app - do not add a third.
export default function Badge({ label }: { label: string }) {
  const isAmendment = label.toLowerCase() === "amendment";
  return (
    <span
      className={
        "inline-flex items-center px-2 py-0.5 rounded text-[10.5px] tracking-[0.08em] uppercase font-semibold " +
        (isAmendment
          ? "text-text-secondary border border-border-hairline bg-surface"
          : "text-primary border border-primary/20 bg-primary-subtle")
      }
    >
      {label}
    </span>
  );
}
