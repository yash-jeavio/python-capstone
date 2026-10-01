import { apiFetch, ApiError } from "./client";
import type { Article } from "../types/article";

export type AiResult<T> = { available: true; data: T } | { available: false };

async function callStub<T>(path: string, init?: RequestInit): Promise<AiResult<T>> {
  try {
    const data = await apiFetch<T>(path, init);
    return { available: true, data };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
      return { available: false };
    }
    if (err instanceof TypeError) {
      return { available: false };
    }
    throw err;
  }
}

export function getSummary(articleId: number): Promise<AiResult<{ summary: string }>> {
  return callStub(`/articles/${articleId}/summary`);
}

export function getRelated(articleId: number): Promise<AiResult<{ related: Article[] }>> {
  return callStub(`/articles/${articleId}/related`);
}

export function askQuestion(question: string): Promise<AiResult<{ answer: string; sources: Article[] }>> {
  return callStub(`/chat/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
