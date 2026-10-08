import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskAiPage } from "./AskAiPage";
import * as ai from "../api/ai";

vi.mock("../api/ai");

beforeEach(() => {
  vi.resetAllMocks();
});

async function ask(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByPlaceholderText("Ask a question..."), question);
  await user.click(screen.getByRole("button", { name: "Send" }));
}

describe("AskAiPage", () => {
  it("shows the question and the answer when the backend answers", async () => {
    vi.mocked(ai.askQuestion).mockResolvedValue({
      state: "ok",
      data: { answer: "Rust is trending.", sources: [] },
    });
    render(<AskAiPage />);
    await ask("What is trending?");

    await waitFor(() => expect(screen.getByText("Rust is trending.")).toBeInTheDocument());
    expect(screen.getByText("What is trending?")).toBeInTheDocument();
    expect(ai.askQuestion).toHaveBeenCalledWith("What is trending?");
    // The input clears so the next question starts from a blank field.
    expect(screen.getByPlaceholderText("Ask a question...")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled();
  });

  it("reports when AI is not configured", async () => {
    vi.mocked(ai.askQuestion).mockResolvedValue({ state: "unconfigured" });
    render(<AskAiPage />);
    await ask("What is trending?");

    await waitFor(() => expect(screen.getByText(/not configured/i)).toBeInTheDocument());
    expect(screen.getByText("What is trending?")).toBeInTheDocument();
  });

  it("reports when the question could not be answered", async () => {
    vi.mocked(ai.askQuestion).mockResolvedValue({ state: "failed" });
    render(<AskAiPage />);
    await ask("What is trending?");

    await waitFor(() => expect(screen.getByText(/couldn't answer that/i)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled();
  });

  it("disables the send button while a question is in flight", async () => {
    let resolveAsk: (value: ai.AiResult<{ answer: string; sources: never[] }>) => void = () => {};
    vi.mocked(ai.askQuestion).mockReturnValue(
      new Promise((resolve) => {
        resolveAsk = resolve;
      })
    );
    render(<AskAiPage />);
    await ask("What is trending?");

    await waitFor(() => expect(screen.getByRole("button", { name: "Asking..." })).toBeDisabled());

    resolveAsk({ state: "ok", data: { answer: "Rust is trending.", sources: [] } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled());
  });
});
