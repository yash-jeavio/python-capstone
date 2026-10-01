import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { AiSummaryPanel } from "./AiSummaryPanel";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AiSummaryPanel", () => {
  it("renders the summary when the backend has it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ summary: "a short summary" }) })
    );
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText("a short summary")).toBeInTheDocument());
  });

  it("renders a coming-soon badge when the endpoint doesn't exist yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
