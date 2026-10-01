import { describe, it, expect, vi, afterEach } from "vitest";
import { apiFetch, ApiError } from "./client";

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ hello: "world" }),
      })
    );

    const result = await apiFetch<{ hello: string }>("/test");
    expect(result).toEqual({ hello: "world" });
  });

  it("calls fetch with the /api prefix", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/articles");
    expect(fetchMock).toHaveBeenCalledWith("/api/articles", expect.anything());
  });

  it("throws an ApiError carrying the status on a non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    const error = await apiFetch("/missing").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
  });
});
