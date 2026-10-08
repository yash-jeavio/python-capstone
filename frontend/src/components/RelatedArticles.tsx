import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getRelated } from "../api/ai";

export function RelatedArticles({ articleId }: { articleId: number }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["related", articleId],
    queryFn: () => getRelated(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading related articles...</p>;
  }
  if (data?.state === "unconfigured") {
    return <p className="text-sm text-gray-400">AI features are not configured.</p>;
  }
  if (data?.state !== "ok") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Couldn't load related articles.</span>
        <button className="rounded border border-gray-300 px-2 py-0.5" onClick={() => refetch()}>
          Try again
        </button>
      </div>
    );
  }
  if (data.data.related.length === 0) {
    return <p className="text-sm text-gray-400">No related articles found.</p>;
  }
  return (
    <ul className="space-y-2">
      {data.data.related.map((article) => (
        <li key={article.id}>
          <Link to={`/articles/${article.id}`} className="text-blue-600 hover:underline">
            {article.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}
