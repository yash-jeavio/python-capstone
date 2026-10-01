import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getRelated } from "../api/ai";
import { ComingSoonBadge } from "./ComingSoonBadge";

export function RelatedArticles({ articleId }: { articleId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["related", articleId],
    queryFn: () => getRelated(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading related articles...</p>;
  }
  if (!data?.available) {
    return <ComingSoonBadge label="Related articles" />;
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
