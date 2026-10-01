export function Pagination({
  page,
  hasNextPage,
  onPageChange,
}: {
  page: number;
  hasNextPage: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-center gap-4">
      <button
        className="rounded border border-gray-300 px-3 py-1 disabled:opacity-50"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Prev
      </button>
      <span className="text-sm text-gray-600">Page {page}</span>
      <button
        className="rounded border border-gray-300 px-3 py-1 disabled:opacity-50"
        disabled={!hasNextPage}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
