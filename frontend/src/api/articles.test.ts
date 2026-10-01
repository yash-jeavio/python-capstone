import { describe, it, expect, vi, afterEach } from "vitest";
import { listArticles, getArticle, refreshArticles } from "./articles";

function mockFetchOnce(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) }));
}

describe("articles api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds a query string from the provided filters plus pagination defaults", async () => {
    mockFetchOnce([]);
    await listArticles({ keyword: "ai" });
    expect(fetch).toHaveBeenCalledWith("/api/articles?keyword=ai&page=1&page_size=20", expect.anything());
  });

  it("defaults to page 1 / page_size 20 with no filters", async () => {
    mockFetchOnce([]);
    await listArticles({});
    expect(fetch).toHaveBeenCalledWith("/api/articles?page=1&page_size=20", expect.anything());
  });

  it("URL-encodes special characters in the keyword", async () => {
    mockFetchOnce([]);
    await listArticles({ keyword: "rust & go" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/articles?keyword=rust+%26+go&page=1&page_size=20",
      expect.anything()
    );
  });

  it("fetches a single article by id", async () => {
    mockFetchOnce({ id: 1 });
    await getArticle(1);
    expect(fetch).toHaveBeenCalledWith("/api/articles/1", expect.anything());
  });

  it("posts to the refresh endpoint", async () => {
    mockFetchOnce({ fetched: 1, created: 1, updated: 0, failed: 0 });
    await refreshArticles();
    expect(fetch).toHaveBeenCalledWith("/api/articles/refresh", expect.objectContaining({ method: "POST" }));
  });
});
