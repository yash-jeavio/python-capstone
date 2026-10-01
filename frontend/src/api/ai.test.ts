import { describe, it, expect, vi, afterEach } from "vitest";
import { getSummary, getRelated, askQuestion } from "./ai";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ai api stub handling", () => {
  it("returns available data when the backend has the endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ summary: "short summary" }) })
    );

    const result = await getSummary(1);
    expect(result).toEqual({ available: true, data: { summary: "short summary" } });
  });

  it("treats a 404 as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    const result = await getSummary(1);
    expect(result).toEqual({ available: false });
  });

  it("treats a 501 as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 501 }));

    const result = await getRelated(1);
    expect(result).toEqual({ available: false });
  });

  it("treats a network error as not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const result = await askQuestion("what is trending?");
    expect(result).toEqual({ available: false });
  });

  it("rethrows unexpected server errors instead of hiding them", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    await expect(getSummary(1)).rejects.toThrow();
  });
});
