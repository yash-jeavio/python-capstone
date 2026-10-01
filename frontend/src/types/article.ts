export interface Article {
  id: number;
  title: string;
  url: string | null;
  author: string | null;
  score: number;
  comment_count: number;
  item_type: string;
  sources: string[];
  posted_at: string;
}

export type SourceFilter = "top" | "best" | "ask" | "show";
export type SortOption = "score_desc" | "posted_at_desc";

export interface ArticleFilters {
  keyword?: string;
  min_score?: number;
  source?: SourceFilter;
  sort?: SortOption;
  page?: number;
  page_size?: number;
}

export interface RefreshResult {
  fetched: number;
  created: number;
  updated: number;
  failed: number;
}
