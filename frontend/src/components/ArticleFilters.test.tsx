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
});
