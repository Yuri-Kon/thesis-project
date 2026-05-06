import { Component, type ErrorInfo, type ReactNode } from "react";

/* ── ColumnErrorBoundary ────────────────────────────────────── */

interface ColumnErrorBoundaryProps {
  name: "sidebar" | "main" | "inspector";
  children: ReactNode;
}

interface ColumnErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ColumnErrorBoundary extends Component<
  ColumnErrorBoundaryProps,
  ColumnErrorBoundaryState
> {
  state: ColumnErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ColumnErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(
      `[ColumnErrorBoundary:${this.props.name}]`,
      error,
      info.componentStack,
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      const message = this.state.error?.message ?? "Unknown error";
      const truncated =
        message.length > 120 ? message.slice(0, 120) + "..." : message;
      return (
        <div className="column-error-card">
          <strong>{this.props.name} 不可用</strong>
          <p>{truncated}</p>
          <button type="button" onClick={this.handleRetry}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── AppErrorBoundary ───────────────────────────────────────── */

interface AppErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class AppErrorBoundary extends Component<
  { children: ReactNode },
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[AppErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-error-fallback">
          <h2>Something went wrong</h2>
          <p className="muted">
            The workspace encountered an unexpected error. Please reload the
            page.
          </p>
          <pre>{this.state.error?.message ?? "Unknown error"}</pre>
          <button type="button" onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
