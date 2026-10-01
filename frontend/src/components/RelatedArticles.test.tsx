import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { RelatedArticles } from "./RelatedArticles";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RelatedArticles", () => {
  it("renders related article titles when available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ related: [{ id: 2, title: "Related One" }] }),
      })
    );
    render(renderWithProviders(<RelatedArticles articleId={1} />));
    await waitFor(() => expect(screen.getByText("Related One")).toBeInTheDocument());
  });

  it("renders a coming-soon badge when not available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(renderWithProviders(<RelatedArticles articleId={1} />));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
