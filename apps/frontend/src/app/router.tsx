import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/shared/components/layout/AppLayout";
import { LoginPage } from "@/features/auth/pages/LoginPage";
import { LandingPage } from "@/features/landing/pages/LandingPage";
import { DiscoveryPage } from "@/features/play/pages/DiscoveryPage";
import { StudioPage } from "@/features/studio/pages/StudioPage";
import { NewScenarioPage } from "@/features/studio/pages/NewScenarioPage";
import { EditScenarioPage } from "@/features/studio/pages/EditScenarioPage";
import { PlayPage } from "@/features/play/pages/PlayPage";
import { SetupPage } from "@/features/play/pages/SetupPage";
import { ScenarioFocusPage } from "@/features/play/pages/ScenarioFocusPage";
import { SpectatorPage } from "@/features/play/pages/SpectatorPage";
import { JoinPage } from "@/features/play/pages/JoinPage";
import { ProfilePage } from "@/features/profile/pages/ProfilePage";
import { NotFoundPage } from "@/features/misc/pages/NotFoundPage";
import { TermsPage } from "@/features/misc/pages/TermsPage";
import { PrivacyPage } from "@/features/misc/pages/PrivacyPage";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/discover", element: <DiscoveryPage /> },
      { path: "/studio", element: <StudioPage /> },
      { path: "/scenario/:id", element: <ScenarioFocusPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/profile/:id", element: <ProfilePage /> },
    ],
  },
  { path: "/login", element: <LoginPage /> },
  { path: "/play", element: <PlayPage /> },
  { path: "/play/:id", element: <PlayPage /> },
  { path: "/setup/:id", element: <SetupPage /> },
  { path: "/spectate/:id", element: <SpectatorPage /> },
  { path: "/join", element: <JoinPage /> },
  { path: "/studio/new", element: <NewScenarioPage /> },
  { path: "/studio/:id/edit", element: <EditScenarioPage /> },
  { path: "/terms", element: <TermsPage /> },
  { path: "/privacy", element: <PrivacyPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
