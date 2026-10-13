import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listArticles } from "../api/articles";
import type { ArticleFilters as Filters, SourceFilter, SortOption } from "../types/article";
import { ArticleFilters } from "../components/ArticleFilters";
import { ArticleCard } from "../components/ArticleCard";
import { Pagination } from "../components/Pagination";
import { RefreshButton } from "../components/RefreshButton";

const PAGE_SIZE = 20;

// The URL is the single source of truth for the filters, not component state.
// Keeping them here is what lets the browser restore them on Back: returning
// from an article detail page replays the list URL, filters included.
function filtersFromParams(params: URLSearchParams): Filters {
  const minScore = params.get("min_score");
  return {
    keyword: params.get("keyword") || undefined,
    min_score: minScore ? Number(minScore) : undefined,
    source: (params.get("source") as SourceFilter) || undefined,
    sort: (params.get("sort") as SortOption) || "score_desc",
    page: Number(params.get("page")) || 1,
    page_size: PAGE_SIZE,
  };
}

// page_size is a constant, not a user choice, so it stays out of the URL --
// as does page 1, which is the default and only adds noise.
function paramsFromFilters(filters: Filters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));
  if (filters.source) params.set("source", filters.source);
  if (filters.sort) params.set("sort", filters.sort);
  if ((filters.page ?? 1) > 1) params.set("page", String(filters.page));
  return params;
}

export function ArticlesListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromParams(searchParams);

  // replace, not push: tweaking a filter shouldn't leave a history entry the
  // user has to click back through. Opening an article is a push, so Back from
  // the detail page still lands on this list with these filters applied.
  const setFilters = (next: Filters) =>
    setSearchParams(paramsFromFilters(next), { replace: true });

  const {
    data: articles,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["articles", filters],
    queryFn: () => listArticles(filters),
  });

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Hacker News Articles</h1>
        <RefreshButton />
      </div>
      <ArticleFilters filters={filters} onChange={setFilters} />
      {isLoading && <p className="mt-4 text-gray-500">Loading articles...</p>}
      {isError && (
        <div className="mt-4 flex items-center gap-3">
          <p className="text-red-600">Failed to load articles.</p>
          <button className="rounded border border-gray-300 px-3 py-1" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}
      {articles && articles.length === 0 && (
        <p className="mt-4 text-gray-500">No articles match your filters.</p>
      )}
      {articles && articles.length > 0 && (
        <>
          <div className="mt-4 space-y-3">
            {articles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
          <Pagination
            page={filters.page ?? 1}
            hasNextPage={articles.length === (filters.page_size ?? PAGE_SIZE)}
            onPageChange={(page) => setFilters({ ...filters, page })}
          />
        </>
      )}
    </div>
  );
}
