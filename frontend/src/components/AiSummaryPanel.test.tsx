import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../testUtils";
import { AiSummaryPanel } from "./AiSummaryPanel";
import * as ai from "../api/ai";

vi.mock("../api/ai");

beforeEach(() => {
  vi.resetAllMocks();
});

describe("AiSummaryPanel", () => {
  it("renders the summary when available", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "ok", data: { summary: "A summary." } });
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText("A summary.")).toBeInTheDocument());
  });

  it("reports when AI is not configured", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "unconfigured" });
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
  });

  it("offers a retry when generation failed", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "failed" });
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));

    await waitFor(() => expect(screen.getByText(/couldn't generate/i)).toBeInTheDocument());

    vi.mocked(ai.getSummary).mockResolvedValue({ state: "ok", data: { summary: "Worked now." } });
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByText("Worked now.")).toBeInTheDocument());
  });

  it("never shows the retired Phase 2 placeholder", async () => {
    vi.mocked(ai.getSummary).mockResolvedValue({ state: "unconfigured" });
    render(renderWithProviders(<AiSummaryPanel articleId={1} />));
    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
    expect(screen.queryByText(/coming in Phase 2/)).not.toBeInTheDocument();
  });
});
