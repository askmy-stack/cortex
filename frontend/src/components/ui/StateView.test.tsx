import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StateView } from "./StateView";

describe("StateView", () => {
  it("renders title and body", () => {
    render(
      <StateView title="No data yet">
        Connect your API to populate memory.
      </StateView>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("No data yet")).toBeInTheDocument();
    expect(screen.getByText(/connect your api/i)).toBeInTheDocument();
  });

  it("uses alert role for error tone", () => {
    render(<StateView tone="error" title="Failed" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
