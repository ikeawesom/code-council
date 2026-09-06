export default function EmptyState({
  icon = "inbox",
  heading,
  description,
  action,
}: {
  icon?: string;
  heading: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="bg-surface border border-border-hairline rounded-lg p-12 shadow-sm flex flex-col items-center justify-center text-center max-w-3xl mx-auto w-full">
      <div className="w-12 h-12 rounded-full bg-surface-subtle flex items-center justify-center mb-6 text-text-main">
        <span className="material-symbols-outlined text-[24px]">{icon}</span>
      </div>
      <h3 className="text-[22px] font-medium text-text-main tracking-tight mb-2 max-w-xl leading-snug">
        {heading}
      </h3>
      {description && (
        <p className="text-[14.5px] text-text-secondary max-w-lg mb-6 leading-relaxed">
          {description}
        </p>
      )}
      {action}
    </div>
  );
}
