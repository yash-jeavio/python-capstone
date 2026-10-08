import { apiFetch, ApiError } from "./client";
import type { Article } from "../types/article";

export type AiResult<T> =
  | { state: "ok"; data: T }
  | { state: "unconfigured" } // 501 — no OPENAI_API_KEY configured
  | { state: "failed" }; // 503, any other non-2xx, or a network error

async function callAi<T>(path: string, init?: RequestInit): Promise<AiResult<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { state: "ok", data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 501) {
      return { state: "unconfigured" };
    }
    // Everything else is transient from the user's point of view: a 503, an
    // unexpected status, or a network failure all mean "try again".
    return { state: "failed" };
  }
}

export function getSummary(articleId: number): Promise<AiResult<{ summary: string }>> {
  return callAi(`/articles/${articleId}/summary`);
}

export function getRelated(articleId: number): Promise<AiResult<{ related: Article[] }>> {
  return callAi(`/articles/${articleId}/related`);
}

export function askQuestion(
  question: string
): Promise<AiResult<{ answer: string; sources: Article[] }>> {
  return callAi(`/chat/ask`, { method: "POST", body: JSON.stringify({ question }) });
}
