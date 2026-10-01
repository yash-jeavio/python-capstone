import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listArticles } from "../api/articles";
import type { ArticleFilters as Filters } from "../types/article";
import { ArticleFilters } from "../components/ArticleFilters";
import { ArticleCard } from "../components/ArticleCard";
import { Pagination } from "../components/Pagination";
import { RefreshButton } from "../components/RefreshButton";

const PAGE_SIZE = 20;

export function ArticlesListPage() {
  const [filters, setFilters] = useState<Filters>({ page: 1, page_size: PAGE_SIZE, sort: "score_desc" });

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
