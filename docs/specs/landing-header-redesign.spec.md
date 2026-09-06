# Spec: Landing Page Header Redesign & Platform Navigation Unification

## 1. Objective & User Outcome
- **Problem Statement:** The landing page (`LandingPage.tsx`) currently embeds a bespoke, hardcoded header with non-functional placeholder links (`Home`, `Inventory`, `About`), an unlinked text logo, and an unconditional `/login` link that ignores authenticated session state. Meanwhile, internal pages (such as `ProfilePage.tsx`) utilize a separate shared `<Header />` component (`shared/components/layout/Header.tsx`) that lacks the landing page's scroll-reactive transparent-to-dark aesthetics and responsive mobile navigation.
- **User Story:** As a visitor or returning adventurer, I want a unified, responsive header that reflects my authentication state, provides direct navigation to core game loops (`Discover`, `Studio`, `Profile`), adapts seamlessly from transparent to dark-frosted glass on scroll, and offers a smooth mobile experience so that I can explore and play without broken navigation.
- **Success Criteria:**
  - Landing page header replaced with the enhanced shared `Header` component configured with `variant="landing"`.
  - Seamless scroll-reactive styling: transparent at the top of the hero (`scrollY <= 50`), transitioning to `#0d0f14`/90 with backdrop blur, shadow, and border on scroll (`scrollY > 50`).
  - Active route highlighting for primary links (`Discover` -> `/discover`, `Studio` -> `/studio`).
  - Smooth scroll to top when clicking the "AI-DND" logo if already at `/`, and route navigation to `/` if on another page.
  - Authenticated Adventurer Badge & Dropdown: displays user display name with quick links to Profile (`/profile`), My Creations (`/profile?tab=creations`), Bookmarks (`/profile?tab=bookmarks`), and Sign Out.
  - Unauthenticated State: 'Sign In' button linking to `/login` with frosted-glass border and glow.
  - Responsive Mobile Navigation: Animated hamburger toggle opening a drawer/dropdown for mobile viewports.
  - `ProfilePage.tsx` updated to synchronize with the `?tab=` search param.
  - Zero TypeScript errors, zero ESLint warnings, 100% adherence to `CLAUDE.md` rules (functions <= 30 lines, nesting depth <= 2 levels, one component per file, props colocated in `.types.ts`).

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - `apps/frontend/src/shared/components/layout/Header.tsx` (Main shared header container)
  - `apps/frontend/src/shared/components/layout/Header.types.ts` (Props and navigation types)
  - `apps/frontend/src/shared/components/layout/UserDropdown.tsx` (Adventurer profile pill and dropdown menu)
  - `apps/frontend/src/shared/components/layout/MobileNav.tsx` (Responsive mobile menu drawer/dropdown)
  - `apps/frontend/src/features/landing/pages/LandingPage.tsx` (Consumes `<Header variant="landing" />`)
  - `apps/frontend/src/features/profile/pages/ProfilePage.tsx` (Consumes `<Header />` and reads `?tab=` search param)
- **Sequence Flow:**
  1. On mount, `Header` checks `variant`:
     - If `variant="landing"`, sets up a scroll event listener. While `scrollY <= 50`, renders transparent styling without border; when `scrollY > 50`, applies `bg-[#0d0f14]/90 backdrop-blur-md border-b border-zinc-800/80 shadow-lg`.
     - If `variant="default"` (or omitted), applies constant frosted-glass container styling (`bg-white/5 backdrop-blur-lg border-b border-white/20`).
  2. `Header` consumes `useAuth()`:
     - If `user` is null: displays "Sign In" button pointing to `/login`.
     - If `user` is present: renders `<UserDropdown user={user} onLogout={logout} />`.
  3. Clicking "Bookmarks" or "My Creations" navigates to `/profile?tab=bookmarks` or `/profile?tab=creations`.
  4. `ProfilePage` reads `useSearchParams().get("tab")` on mount/param change and switches the active tab accordingly.
  5. Clicking the hamburger icon on mobile viewports toggles `<MobileNav />` with animated expand/collapse.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- Build: `cd apps/frontend && npm run build`
- Test: `cd apps/frontend && npx vitest run src/shared/components/layout`
- Lint / Type-Check: `cd apps/frontend && npm run lint`

### 3.2. Testing Strategy & Conformance
- Test directory: `apps/frontend/src/shared/components/layout/__tests__/Header.test.tsx`.
- Automated test cases:
  1. **Render (Unauthenticated):** Renders "AI-DND" logo, "Discover" and "Studio" navigation links, and "Sign In" button when `user` is null.
  2. **Render (Authenticated):** Renders user display name and adventurer icon when `user` is present.
  3. **Dropdown Interaction:** Clicking user badge opens menu with Profile, My Creations, Bookmarks, and Sign Out links. Clicking Sign Out triggers `logout()`.
  4. **Active Route:** Highlights active navigation link when `location.pathname` matches `/discover` or `/studio`.
  5. **Landing Variant Scroll:** Switches styling classes between top (`scrollY <= 50`) and scrolled (`scrollY > 50`).
  6. **Mobile Nav Toggle:** Hamburger button toggles mobile navigation menu open/close on mobile viewport.
  7. **Logo Click Behavior:** Smooth scrolls to top when clicked on `/`.

### 3.3. Project Structure & File Layout
- **Files to create:**
  - `apps/frontend/src/shared/components/layout/Header.types.ts`
  - `apps/frontend/src/shared/components/layout/UserDropdown.tsx`
  - `apps/frontend/src/shared/components/layout/MobileNav.tsx`
  - `apps/frontend/src/shared/components/layout/__tests__/Header.test.tsx`
- **Files to modify:**
  - `apps/frontend/src/shared/components/layout/Header.tsx`
  - `apps/frontend/src/features/landing/pages/LandingPage.tsx`
  - `apps/frontend/src/features/profile/pages/ProfilePage.tsx`

### 3.4. Code Style & Interfaces

#### Header Types (`Header.types.ts`)
```typescript
import { UserResponse } from "@/features/auth/types/auth.types";

export interface HeaderProps {
  variant?: "default" | "landing";
}

export interface UserDropdownProps {
  user: UserResponse;
  onLogout: () => void;
}

export interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserResponse | null;
  onLogout: () => void;
}
```

#### Strict Complexity Enforcements
- Maximum nesting depth: 2 levels.
- Functions under 30 lines.
- Pure components with hooks extracted into helper functions where appropriate.
- Colocated props and clean separation of subcomponents (`UserDropdown`, `MobileNav`).

### 3.5. Git & Review Workflow
- Suggested branch: `feat/landing-header-redesign`
- Validation checklist:
  - Vitest layout suite passes: `npx vitest run src/shared/components/layout`
  - Frontend build passes: `npm run build`
  - Code passes ESLint without warnings: `npm run lint`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use strict TypeScript types; extract subcomponents for mobile drawer and user dropdown; colocate types in `.types.ts`; adhere to <30 lines and <=2 nesting depth.
- ⚠️ **Ask First:** Changing global router definitions or introducing new external dependencies.
- 🚫 **Never:** Use inline styles; introduce `any` types; import feature-specific code into `shared/` (auth types from `features/auth/types/auth.types.ts` are standard domain types).

## 4. Edge Cases & Graceful Degradation
- **Fast Scroll / Resize:** Event listeners for `scroll` and `resize` (or outside click) use cleanup handlers to prevent memory leaks and layout thrashing.
- **Dropdown Click Outside:** Clicking outside or pressing `Escape` gracefully dismisses the user dropdown and mobile nav.
- **Auth Token Expiry / Latency:** If user profile is partially loading or display name is empty, fallback to `"Adventurer"`.
- **Invalid Profile Tab:** If `?tab=` in URL is an unrecognized tab name, `ProfilePage` defaults safely to `"creations"`.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Types & Subcomponents):** Create `Header.types.ts`, `UserDropdown.tsx`, and `MobileNav.tsx`.
- [ ] **Task 2 (Shared Header Refactor):** Refactor `shared/components/layout/Header.tsx` with variant prop (`default` vs `landing`), scroll listener, active link styling, and logo click behavior.
- [ ] **Task 3 (Landing Page Integration):** Replace the inline header in `features/landing/pages/LandingPage.tsx` with `<Header variant="landing" />`.
- [ ] **Task 4 (Profile Tab Synchronization):** Update `features/profile/pages/ProfilePage.tsx` to read `?tab=` from search parameters so Bookmarks and Creations links work seamlessly.
- [ ] **Task 5 (Unit Tests & Verification):** Add `Header.test.tsx`, run Vitest suite, run ESLint, and verify full build.
