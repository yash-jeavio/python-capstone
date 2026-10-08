import { describe, expect, it, vi, afterEach } from "vitest";
import { getSummary, getRelated, askQuestion } from "./ai";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(status: number, body: unknown = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })
  );
}

describe("ai api", () => {
  it("returns ok with data on success", async () => {
    stubFetch(200, { summary: "A summary." });
    const result = await getSummary(1);
    expect(result).toEqual({ state: "ok", data: { summary: "A summary." } });
  });

  it("returns unconfigured on 501", async () => {
    stubFetch(501);
    expect(await getSummary(1)).toEqual({ state: "unconfigured" });
  });

  it("returns failed on 503", async () => {
    stubFetch(503);
    expect(await getSummary(1)).toEqual({ state: "failed" });
  });

  it("returns failed on 404", async () => {
    stubFetch(404);
    expect(await getSummary(1)).toEqual({ state: "failed" });
  });

  it("returns failed on a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    expect(await getRelated(1)).toEqual({ state: "failed" });
  });

  it("posts the question to /chat/ask", async () => {
    stubFetch(200, { answer: "An answer.", sources: [] });
    const result = await askQuestion("Which is faster?");
    expect(result).toEqual({ state: "ok", data: { answer: "An answer.", sources: [] } });
    expect(fetch).toHaveBeenCalledWith(
      "/api/chat/ask",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ question: "Which is faster?" }) })
    );
  });
});
