import { createBrowserRouter } from "react-router-dom";
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

export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/discover",
    element: <DiscoveryPage />,
  },
  {
    path: "/play",
    element: <PlayPage />,
  },
  {
    path: "/play/:id",
    element: <PlayPage />,
  },
  {
    path: "/setup/:id",
    element: <SetupPage />,
  },
  {
    path: "/scenario/:id",
    element: <ScenarioFocusPage />,
  },
  {
    path: "/spectate/:id",
    element: <SpectatorPage />,
  },
  {
    path: "/join",
    element: <JoinPage />,
  },
  {
    path: "/studio/new",
    element: <NewScenarioPage />,
  },
  {
    path: "/studio/:id/edit",
    element: <EditScenarioPage />,
  },
  {
    path: "/studio",
    element: <StudioPage />,
  },
  {
    path: "/profile",
    element: <ProfilePage />,
  },
  {
    path: "/profile/:id",
    element: <ProfilePage />,
  },
]);
