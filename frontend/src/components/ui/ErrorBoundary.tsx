import { Component, type ErrorInfo, type ReactNode } from "react";
import { StateView } from "./StateView";

type Props = {
  children: ReactNode;
};

type State = {
  error: Error | null;
};

/** Catches render errors so the dashboard never shows a blank screen. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Cortex UI error:", error, info.componentStack);
  }

  private retry = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="error-boundary">
          <StateView
            tone="error"
            title="Something went wrong"
            action={
              <button type="button" className="btn btn--secondary" onClick={this.retry}>
                Try again
              </button>
            }
          >
            {this.state.error.message || "An unexpected error occurred in the dashboard."}
          </StateView>
        </div>
      );
    }
    return this.props.children;
  }
}
