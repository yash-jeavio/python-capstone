import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { ArticleFilters } from "./ArticleFilters";

afterEach(() => {
  vi.useRealTimers();
});

describe("ArticleFilters", () => {
  it("debounces keyword changes before calling onChange", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Search title..."), { target: { value: "rust" } });
    expect(onChange).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);
    expect(onChange).toHaveBeenCalledWith({ keyword: "rust", page: 1 });
  });

  it("updates min_score immediately without debounce", () => {
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Min score"), { target: { value: "50" } });
    expect(onChange).toHaveBeenCalledWith({ min_score: 50, page: 1 });
  });

  it("updates the source filter immediately", () => {
    const onChange = vi.fn();
    render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByDisplayValue("All sources"), { target: { value: "top" } });
    expect(onChange).toHaveBeenCalledWith({ source: "top", page: 1 });
  });

  it("uses the latest filters when the debounced keyword change fires, even if another filter changed in between", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    const { rerender } = render(<ArticleFilters filters={{}} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText("Search title..."), { target: { value: "rust" } });

    // Simulate an immediate filter change (e.g. min_score) landing before the debounce fires,
    // which updates the `filters` prop from the parent.
    rerender(<ArticleFilters filters={{ min_score: 50, page: 1 }} onChange={onChange} />);

    vi.advanceTimersByTime(300);
    expect(onChange).toHaveBeenLastCalledWith({ min_score: 50, page: 1, keyword: "rust" });
  });
});
