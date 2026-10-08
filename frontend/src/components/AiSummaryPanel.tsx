import { useQuery } from "@tanstack/react-query";
import { getSummary } from "../api/ai";

export function AiSummaryPanel({
  articleId,
  variant = "full",
}: {
  articleId: number;
  variant?: "compact" | "full";
}) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["summary", articleId],
    queryFn: () => getSummary(articleId),
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading summary...</p>;
  }
  if (data?.state === "unconfigured") {
    return <p className="text-sm text-gray-400">AI features are not configured.</p>;
  }
  if (data?.state !== "ok") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-500">Couldn't generate a summary.</span>
        <button className="rounded border border-gray-300 px-2 py-0.5" onClick={() => refetch()}>
          Try again
        </button>
      </div>
    );
  }
  return (
    <p className={variant === "compact" ? "line-clamp-2 text-sm text-gray-600" : "text-base text-gray-700"}>
      {data.data.summary}
    </p>
  );
}
