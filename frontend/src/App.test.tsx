import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { App } from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders the nav links and defaults to the articles list route", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    render(<App />);
    expect(screen.getByText("Articles")).toBeInTheDocument();
    expect(screen.getByText("Ask AI")).toBeInTheDocument();
    expect(await screen.findByText("Hacker News Articles")).toBeInTheDocument();
  });
});
