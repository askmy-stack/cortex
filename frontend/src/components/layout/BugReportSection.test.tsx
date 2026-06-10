import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BugReportSection } from "./BugReportSection";

describe("BugReportSection", () => {
  it("renders visible bug report heading and actions", () => {
    render(<BugReportSection />);
    expect(screen.getByRole("heading", { name: /report a bug or issue/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /file on github/i })).toHaveAttribute(
      "href",
      expect.stringContaining("github.com/askmy-stack/cortex/issues"),
    );
    expect(screen.getByRole("link", { name: /email report/i })).toHaveAttribute(
      "href",
      expect.stringContaining("mailto:"),
    );
  });
});
