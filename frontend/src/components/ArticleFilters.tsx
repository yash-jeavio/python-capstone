import { useEffect, useState } from "react";
import type { ArticleFilters as Filters, SourceFilter, SortOption } from "../types/article";

export function ArticleFilters({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (filters: Filters) => void;
}) {
  const [keyword, setKeyword] = useState(filters.keyword ?? "");

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (keyword !== (filters.keyword ?? "")) {
        onChange({ ...filters, keyword: keyword || undefined, page: 1 });
      }
    }, 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword]);

  return (
    <div className="flex flex-wrap gap-3 rounded-lg border border-gray-200 p-4">
      <input
        type="text"
        placeholder="Search title..."
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="rounded border border-gray-300 px-2 py-1"
      />
      <input
        type="number"
        min={0}
        placeholder="Min score"
        value={filters.min_score ?? ""}
        onChange={(e) =>
          onChange({ ...filters, min_score: e.target.value ? Number(e.target.value) : undefined, page: 1 })
        }
        className="w-28 rounded border border-gray-300 px-2 py-1"
      />
      <select
        value={filters.source ?? ""}
        aria-label="Source"
        onChange={(e) =>
          onChange({ ...filters, source: (e.target.value || undefined) as SourceFilter | undefined, page: 1 })
        }
        className="rounded border border-gray-300 px-2 py-1"
      >
        <option value="">All sources</option>
        <option value="top">Top</option>
        <option value="best">Best</option>
        <option value="ask">Ask</option>
        <option value="show">Show</option>
      </select>
      <select
        value={filters.sort ?? "score_desc"}
        aria-label="Sort"
        onChange={(e) => onChange({ ...filters, sort: e.target.value as SortOption, page: 1 })}
        className="rounded border border-gray-300 px-2 py-1"
      >
        <option value="score_desc">Score (high to low)</option>
        <option value="posted_at_desc">Newest first</option>
      </select>
    </div>
  );
}
