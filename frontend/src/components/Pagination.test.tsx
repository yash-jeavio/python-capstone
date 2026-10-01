import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("disables Prev on page 1", () => {
    render(<Pagination page={1} hasNextPage={true} onPageChange={vi.fn()} />);
    expect(screen.getByText("Prev")).toBeDisabled();
  });

  it("disables Next when hasNextPage is false", () => {
    render(<Pagination page={2} hasNextPage={false} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).toBeDisabled();
  });

  it("enables Next when a full page was returned, even on what may be the last page", () => {
    // Known limitation (documented in the plan's Review Focus): the backend
    // returns no total count, so "a full page came back" is the only signal
    // we have, and it can't distinguish a true last page from one that isn't.
    render(<Pagination page={5} hasNextPage={true} onPageChange={vi.fn()} />);
    expect(screen.getByText("Next")).not.toBeDisabled();
  });

  it("calls onPageChange with the next page number", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} hasNextPage={true} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("Next"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("calls onPageChange with the previous page number", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={2} hasNextPage={true} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("Prev"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});
