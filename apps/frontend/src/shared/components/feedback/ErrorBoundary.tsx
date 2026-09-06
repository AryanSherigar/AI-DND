import React from "react";
import { logEvent } from "@/shared/lib/logger";
import { ErrorFallback } from "./ErrorFallback";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    logEvent("error", "react_error_boundary", {
      message: error.message,
      stack: error.stack,
      componentStack: info.componentStack ?? undefined,
    });
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return this.props.fallback ?? <ErrorFallback />;
    }
    return this.props.children;
  }
}
