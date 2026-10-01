import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { RefreshButton } from "./RefreshButton";
import { renderWithProviders } from "../testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RefreshButton", () => {
  it("shows the refresh summary after a successful refresh", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ fetched: 10, created: 8, updated: 2, failed: 0 }),
      })
    );
    render(renderWithProviders(<RefreshButton />));
    fireEvent.click(screen.getByText("Refresh from Hacker News"));
    await waitFor(() =>
      expect(screen.getByText(/Fetched 10, created 8, updated 2, failed 0/)).toBeInTheDocument()
    );
  });

  it("shows an error message when the refresh request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    render(renderWithProviders(<RefreshButton />));
    fireEvent.click(screen.getByText("Refresh from Hacker News"));
    await waitFor(() => expect(screen.getByText("Refresh failed. Please try again.")).toBeInTheDocument());
  });

  it("disables the button while a refresh is in flight so double-clicks can't fire two requests", async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveFetch = resolve;
        })
      )
    );
    render(renderWithProviders(<RefreshButton />));
    const button = screen.getByText("Refresh from Hacker News");
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText("Refreshing...")).toBeDisabled());

    resolveFetch({ ok: true, json: () => Promise.resolve({ fetched: 0, created: 0, updated: 0, failed: 0 }) });
    await waitFor(() => expect(screen.getByText("Refresh from Hacker News")).not.toBeDisabled());
  });
});
