import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { AskAiPage } from "./AskAiPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AskAiPage", () => {
  it("shows the answer when the backend supports it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ answer: "Rust is trending.", sources: [] }),
      })
    );
    render(<AskAiPage />);
    fireEvent.change(screen.getByPlaceholderText("Ask a question..."), {
      target: { value: "What is trending?" },
    });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText("Rust is trending.")).toBeInTheDocument());
  });

  it("shows a coming-soon badge when the backend doesn't support it yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(<AskAiPage />);
    fireEvent.change(screen.getByPlaceholderText("Ask a question..."), {
      target: { value: "What is trending?" },
    });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(screen.getByText(/coming in Phase 2/)).toBeInTheDocument());
  });
});
