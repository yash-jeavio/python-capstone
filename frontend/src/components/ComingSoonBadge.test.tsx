import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ComingSoonBadge } from "./ComingSoonBadge";

describe("ComingSoonBadge", () => {
  it("renders the label with a coming-in-Phase-2 suffix", () => {
    render(<ComingSoonBadge label="AI summary" />);
    expect(screen.getByText("AI summary — coming in Phase 2")).toBeInTheDocument();
  });
});
