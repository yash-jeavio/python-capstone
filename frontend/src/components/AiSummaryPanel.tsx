import { useQuery } from "@tanstack/react-query";
import { getSummary } from "../api/ai";
import { ComingSoonBadge } from "./ComingSoonBadge";

export function AiSummaryPanel({
  articleId,
  variant = "full",
}: {
  articleId: number;
  variant?: "compact" | "full";
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["summary", articleId],
    queryFn: () => getSummary(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading summary...</p>;
  }
  if (!data?.available) {
    return <ComingSoonBadge label="AI summary" />;
  }
  return (
    <p className={variant === "compact" ? "line-clamp-2 text-sm text-gray-600" : "text-base text-gray-700"}>
      {data.data.summary}
    </p>
  );
}
