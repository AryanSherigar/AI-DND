import React from "react";
import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { router } from "./router";
import { AuthProvider } from "@/features/auth/providers/AuthProvider";
import { ErrorBoundary } from "@/shared/components/feedback/ErrorBoundary";
import { queryClient } from "@/shared/lib/query-client";

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};
