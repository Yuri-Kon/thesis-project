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
      const message = this.state.error?.message ?? "未知错误";
      const truncated =
        message.length > 120 ? message.slice(0, 120) + "..." : message;
      const nameLabels: Record<ColumnErrorBoundaryProps["name"], string> = {
        sidebar: "侧边栏",
        main: "主工作区",
        inspector: "检查器",
      };
      return (
        <div className="column-error-card">
          <strong>{nameLabels[this.props.name]}不可用</strong>
          <p>{truncated}</p>
          <button type="button" onClick={this.handleRetry}>
            重试
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
          <h2>页面出现异常</h2>
          <p className="muted">
            工作区遇到未预期错误，请重新加载页面。
          </p>
          <pre>{this.state.error?.message ?? "未知错误"}</pre>
          <button type="button" onClick={() => window.location.reload()}>
            重新加载页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
