export default function Avatar({
  initials,
  size = "md",
  title,
}: {
  initials: string;
  size?: "sm" | "md";
  title?: string;
}) {
  const dimension = size === "sm" ? "w-6 h-6 text-[10px]" : "w-8 h-8 text-[13px]";
  return (
    <div
      title={title}
      className={`shrink-0 rounded-full bg-sidebar text-white flex items-center justify-center font-medium ${dimension}`}
    >
      {initials}
    </div>
  );
}
