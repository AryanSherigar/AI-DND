import React, { Suspense, lazy } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/shared/components/layout/AppLayout";
import { AuthGuard } from "@/features/auth/components/AuthGuard/AuthGuard";
import { RouteLoadingSpinner } from "@/shared/components/feedback/RouteLoadingSpinner";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { LandingPage } from "@/features/landing/pages/LandingPage";
import { DiscoveryPage } from "@/features/play/pages/DiscoveryPage";
import { ScenarioFocusPage } from "@/features/play/pages/ScenarioFocusPage";
import { JoinPage } from "@/features/play/pages/JoinPage";
import { ProfilePage } from "@/features/profile/pages/ProfilePage";
import { NotFoundPage } from "@/features/misc/pages/NotFoundPage";
import { TermsPage } from "@/features/misc/pages/TermsPage";
import { PrivacyPage } from "@/features/misc/pages/PrivacyPage";

const StudioPage = lazy(() =>
  import("@/features/studio/pages/StudioPage").then((m) => ({
    default: m.StudioPage,
  })),
);
const NewScenarioPage = lazy(() =>
  import("@/features/studio/pages/NewScenarioPage").then((m) => ({
    default: m.NewScenarioPage,
  })),
);
const EditScenarioPage = lazy(() =>
  import("@/features/studio/pages/EditScenarioPage").then((m) => ({
    default: m.EditScenarioPage,
  })),
);
const PlayPage = lazy(() =>
  import("@/features/play/pages/PlayPage").then((m) => ({
    default: m.PlayPage,
  })),
);
const SetupPage = lazy(() =>
  import("@/features/play/pages/SetupPage").then((m) => ({
    default: m.SetupPage,
  })),
);
const SpectatorPage = lazy(() =>
  import("@/features/play/pages/SpectatorPage").then((m) => ({
    default: m.SpectatorPage,
  })),
);

const withSuspense = (Component: React.ComponentType) => (
  <Suspense fallback={<RouteLoadingSpinner />}>
    <Component />
  </Suspense>
);

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/discover", element: <DiscoveryPage /> },
      {
        path: "/studio",
        element: <AuthGuard>{withSuspense(StudioPage)}</AuthGuard>,
      },
      { path: "/scenario/:id", element: <ScenarioFocusPage /> },
      {
        path: "/profile",
        element: (
          <AuthGuard>
            <ProfilePage />
          </AuthGuard>
        ),
      },
      { path: "/profile/:id", element: <ProfilePage /> },
    ],
  },
  { path: "/login", element: <LoginPage /> },
  { path: "/play", element: withSuspense(PlayPage) },
  { path: "/play/:id", element: withSuspense(PlayPage) },
  { path: "/setup/:id", element: withSuspense(SetupPage) },
  { path: "/spectate/:id", element: withSuspense(SpectatorPage) },
  { path: "/join", element: <JoinPage /> },
  {
    path: "/studio/new",
    element: <AuthGuard>{withSuspense(NewScenarioPage)}</AuthGuard>,
  },
  {
    path: "/studio/:id/edit",
    element: <AuthGuard>{withSuspense(EditScenarioPage)}</AuthGuard>,
  },
  { path: "/terms", element: <TermsPage /> },
  { path: "/privacy", element: <PrivacyPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
