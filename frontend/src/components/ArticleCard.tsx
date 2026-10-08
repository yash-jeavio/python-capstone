import { Link } from "react-router-dom";
import type { Article } from "../types/article";

export function ArticleCard({ article }: { article: Article }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <Link to={`/articles/${article.id}`} className="text-lg font-semibold text-gray-900 hover:underline">
        {article.title}
      </Link>
      <div className="mt-1 text-sm text-gray-500">
        {article.author ?? "unknown"} · {article.score} points · {article.comment_count} comments ·{" "}
        {new Date(article.posted_at).toLocaleDateString()}
      </div>
      <div className="mt-1 flex gap-1">
        {article.sources.map((source) => (
          <span key={source} className="rounded bg-orange-100 px-2 py-0.5 text-xs text-orange-700">
            {source}
          </span>
        ))}
      </div>
      {article.url && (
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block text-sm text-blue-600 hover:underline"
        >
          View original ↗
        </a>
      )}
    </div>
  );
}
