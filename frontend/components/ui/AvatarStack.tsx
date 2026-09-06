import Avatar from "./Avatar";

export default function AvatarStack({
  people,
  max = 4,
}: {
  people: { initials: string; name: string }[];
  max?: number;
}) {
  const shown = people.slice(0, max);
  const overflow = people.length - shown.length;
  return (
    <div className="flex items-center -space-x-2">
      {shown.map((p, i) => (
        <div key={`${p.initials}-${i}`} className="ring-2 ring-surface rounded-full">
          <Avatar initials={p.initials} size="sm" title={p.name} />
        </div>
      ))}
      {overflow > 0 && (
        <div className="ring-2 ring-surface rounded-full w-6 h-6 text-[10px] flex items-center justify-center font-medium bg-surface-subtle text-text-secondary">
          +{overflow}
        </div>
      )}
    </div>
  );
}
