import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { refreshArticles } from "../api/articles";
import type { RefreshResult } from "../types/article";

export function RefreshButton() {
  const queryClient = useQueryClient();
  const [lastResult, setLastResult] = useState<RefreshResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: refreshArticles,
    onSuccess: (result) => {
      setLastResult(result);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: () => {
      setError("Refresh failed. Please try again.");
    },
  });

  return (
    <div className="flex items-center gap-3">
      <button
        className="rounded bg-orange-600 px-4 py-2 text-white disabled:opacity-50"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? "Refreshing..." : "Refresh from Hacker News"}
      </button>
      {lastResult && (
        <span className="text-sm text-gray-600">
          Fetched {lastResult.fetched}, created {lastResult.created}, updated {lastResult.updated}, failed{" "}
          {lastResult.failed}
        </span>
      )}
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  );
}
