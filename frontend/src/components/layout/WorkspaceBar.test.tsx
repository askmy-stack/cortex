import type { ReactNode } from "react";
import { fireEvent, render, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkspaceBar } from "./WorkspaceBar";
import { AppProvider } from "../../context/AppContext";
import { ToastProvider } from "../ui/Toast";

function wrap(ui: ReactNode) {
  return (
    <AppProvider>
      <ToastProvider>{ui}</ToastProvider>
    </AppProvider>
  );
}

describe("WorkspaceBar", () => {
  it("renders workspace controls and expandable connection settings", () => {
    const view = render(wrap(<WorkspaceBar />));
    const bar = view.getByLabelText(/workspace and api connection/i);
    expect(within(bar).getByLabelText(/organization workspace/i)).toBeInTheDocument();
    fireEvent.click(within(bar).getByRole("button", { name: "Connection" }));
    expect(within(bar).getByLabelText(/^api key$/i)).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: /test connection/i })).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: /replay tour/i })).toBeInTheDocument();
  });
});
