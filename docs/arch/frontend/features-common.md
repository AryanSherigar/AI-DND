# Frontend Architecture — Common Features (Auth, Profile, Landing)

This document details the cross-cutting feature modules in `apps/frontend/src/features/` that support both Studio and Play surfaces: Authentication, User Profiles, and the Landing Page.

---

## 1. Authentication Feature (`src/features/auth/`)

The authentication module integrates Google Firebase Auth with local JWT synchronization and route protection:
- **`AuthProvider.tsx`**: Context provider wrapping the application root. Listens to Firebase `onAuthStateChanged`, extracts idTokens, and syncs user profiles with Core API via `POST /v1/auth/sync`.
- **`AuthGuard/AuthGuard.tsx`**: Higher-order component protecting routes requiring authentication (e.g. `/studio`, `/profile`). Redirects unauthenticated users to `/login` while preserving return paths.
- **`LoginPage.tsx` & `RetroConsole.tsx`**: Retro CRT command-line-styled login screen with glowing phosphor aesthetic and Google OAuth popup authentication.
- **`LoginButton/LoginButton.tsx`**: Universal header login/logout button displaying the authenticated user's avatar.
- **`useAuth.ts`**: Hook exposing `user`, `isAuthenticated`, `isLoading`, `signInWithGoogle`, and `signOut`.
- **`auth.store.ts`**: Zustand store caching client session token status and local authentication flags.
- **`auth.api.ts`**: Direct HTTP client communicating with `/v1/auth/sync` and `/v1/auth/me`.

---

## 2. User Profile Feature (`src/features/profile/`)

The profile module provides player campaign histories, creator showcases, and social bookmarking:
- **`ProfilePage.tsx`**: Tabbed profile dashboard accessible via `/profile` (self) or `/profile/:id` (public creator view).
- **`ProfileHeader.tsx` & `ProfileStatsRibbon.tsx`**: Displays creator avatar, bio, total scenarios created, playthroughs completed, and community rating averages.
- **`EditProfileModal.tsx`**: Modal for editing display name, bio, and genre preferences.
- **Profile Tabs**:
  - **`CreationsTab.tsx`**: Scenarios published or drafted by the creator.
  - **`CampaignsTab.tsx`**: Active and completed playthrough campaigns with resume buttons.
  - **`BookmarksTab.tsx`**: Scenarios bookmarked for later play.
  - **`ReviewsTab.tsx`**: Reviews submitted by the user.
- **Hooks & API**:
  - `useProfile.ts`: React Query hook fetching user profile data.
  - `useUpdateProfile.ts`: Mutation hook for profile patches.
  - `useUserPlaythroughs.ts`: Fetches player campaigns.
  - `useAbandonPlaythrough.ts`: Mutation to abandon active campaigns.
  - `profileApi.ts`: HTTP endpoints for `/v1/users/:id` and `/v1/auth/me`.

---

## 3. Landing Page Feature (`src/features/landing/`)

The landing page introduces players to the AI-DND platform:
- **`LandingPage.tsx`**: Root landing container (`/`).
- **`LivingBookHero.tsx` & `HeroContent.tsx`**: Interactive hero presentation styled as an open ancient grimoire with animated page flipping and live text generation demonstrations.
- **`ScenarioCarousel.tsx`**: Auto-scrolling carousel showcasing trending and top-rated community scenarios.
- **`HeroSection.tsx`**: Call-to-action headers inviting players to enter the discovery catalog or launch the authoring studio.
