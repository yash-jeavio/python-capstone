import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getArticle } from "../api/articles";
import { ApiError } from "../api/client";
import { AiSummaryPanel } from "../components/AiSummaryPanel";
import { RelatedArticles } from "../components/RelatedArticles";

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const articleId = Number(id);

  const {
    data: article,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["article", articleId],
    queryFn: () => getArticle(articleId),
  });

  if (isLoading) {
    return <p className="p-6 text-gray-500">Loading article...</p>;
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="p-6">
        <p className="text-red-600">Article not found.</p>
        <Link to="/" className="text-blue-600 hover:underline">
          Back to list
        </Link>
      </div>
    );
  }

  if (!article) {
    return <p className="p-6 text-red-600">Failed to load article.</p>;
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        ← Back to list
      </Link>
      <h1 className="mt-2 text-2xl font-bold">{article.title}</h1>
      <div className="mt-1 text-sm text-gray-500">
        {article.author ?? "unknown"} · {article.score} points · {article.comment_count} comments ·{" "}
        {article.item_type}
      </div>
      {article.url && (
        <a href={article.url} target="_blank" rel="noreferrer" className="mt-1 block text-blue-600 hover:underline">
          View original ↗
        </a>
      )}
      <section className="mt-6">
        <h2 className="text-lg font-semibold">AI Summary</h2>
        <AiSummaryPanel articleId={article.id} variant="full" />
      </section>
      <section className="mt-6">
        <h2 className="text-lg font-semibold">Related Articles</h2>
        <RelatedArticles articleId={article.id} />
      </section>
    </div>
  );
}
