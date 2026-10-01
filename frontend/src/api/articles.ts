import { apiFetch } from "./client";
import type { Article, ArticleFilters, RefreshResult } from "../types/article";

function buildQuery(filters: ArticleFilters): string {
  const params = new URLSearchParams();
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.min_score !== undefined) params.set("min_score", String(filters.min_score));
  if (filters.source) params.set("source", filters.source);
  if (filters.sort) params.set("sort", filters.sort);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.page_size ?? 20));
  return params.toString();
}

export function listArticles(filters: ArticleFilters = {}): Promise<Article[]> {
  return apiFetch<Article[]>(`/articles?${buildQuery(filters)}`);
}

export function getArticle(id: number): Promise<Article> {
  return apiFetch<Article>(`/articles/${id}`);
}

export function refreshArticles(): Promise<RefreshResult> {
  return apiFetch<RefreshResult>(`/articles/refresh`, { method: "POST" });
}
