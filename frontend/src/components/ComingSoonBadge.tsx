export function ComingSoonBadge({ label }: { label: string }) {
  return (
    <span className="inline-block rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
      {label} — coming in Phase 2
    </span>
  );
}
