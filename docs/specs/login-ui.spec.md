# Spec: Frontend Login UI (Retro Console Redesign)

## 1. Objective & User Outcome
- **Problem Statement:** The current login page is generic. We need a premium, immersive entry point that establishes the "gaming" theme of AI-DND immediately upon arrival, without sacrificing performance.
- **User Story:** As a user, I want to see a visually stunning, nostalgic retro console login screen so that I feel immersed in the gaming platform experience from the very first interaction.
- **Success Criteria:** 
  - Render a vertical retro handheld console (classic beige) mimicking a **True Pixel Art aesthetic** using pure CSS (hard 0-blur box shadows for stepped corners, flat 16-bit colors).
  - Achieve a 60FPS drifting **"Twilight Window" background** (deep indigo to warm sunset orange gradient with slow-falling CSS "snow"/dust motes).
  - Integrate existing Firebase Google Sign-In behind a retro "Press Start" UI.
  - Maintain full mobile responsiveness (console scales to fit viewport).

## 2. Technical Architecture & Data Flow
- **Components Involved:** 
  - `apps/frontend/src/features/auth/pages/LoginPage.tsx` (Main layout).
  - `apps/frontend/src/features/auth/components/RetroConsole.tsx` (New component for the console shell and screen).
  - `apps/frontend/src/index.css` (Tailwind utilities, custom animations, and Google Fonts import).
- **Sequence Flow:**
  1. User navigates to `/login`.
  2. The page renders the static CSS pixel-art console and the Twilight Window background.
  3. The console screen plays a lightweight CSS "boot up" flicker.
  4. User clicks "Press Start" (or the physical 'A' button) triggering the `signInWithGoogle` Firebase method.
  5. On success: user is redirected. On failure: Screen state changes to "GAME OVER" with the error message in pixelated text.

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `npm run build --workspace=apps/frontend`
- Test: `npm run test --workspace=apps/frontend`
- Lint / Type-Check: `npm run lint --workspace=apps/frontend && npm run typecheck --workspace=apps/frontend`

### 3.2. Testing Strategy & Conformance
- Ensure the login button retains its `aria-label` or `role="button"` for accessibility despite the retro styling.
- Mock the Firebase auth call to verify the "GAME OVER" error state renders the correct error string.

### 3.3. Project Structure & File Layout
- Files to create: 
  - `apps/frontend/src/features/auth/components/RetroConsole.tsx`
- Files to modify: 
  - `apps/frontend/src/features/auth/pages/LoginPage.tsx`
  - `apps/frontend/src/index.css` (to add `@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');` and keyframes).

### 3.4. Code Style & Interfaces
- Use Tailwind for structural layout, but standard CSS modules or global CSS for complex `box-shadow` console shapes and CRT scanlines if Tailwind becomes too verbose.
- Use Zustand or local state (`useState`) to manage the "booting", "idle", and "error" states of the console screen.

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/retro-login-ui`
- Commit scope guidelines: `feat(frontend): implement retro console login UI`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use GPU-accelerated CSS properties (`transform`, `opacity`) for animations.
- ⚠️ **Ask First:** Adding external audio files or heavy image assets (strictly avoiding per user request).
- 🚫 **Never:** Use JavaScript `setInterval` or `requestAnimationFrame` for background ambient animations; rely strictly on CSS.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Mobile Viewports:** The console will use `transform: scale()` or CSS `vw`/`vh` relative sizing to ensure it never overflows the viewport on small devices.
- **Font Loading:** While "Press Start 2P" loads, use `monospace` as a fallback to prevent layout shift.
- **Auth Errors:** If Firebase rate limits or fails, the generic error message must fit within the physical constraints of the console screen UI (use `text-xs` or overflow handling).

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (Global Styles & Assets):** Update CSS keyframes for the Twilight Window falling snow and modify boot-up flicker.
- [x] **Task 2 (Console Shell Layout):** Refactor `RetroConsole.tsx` to use hard, 0-blur `box-shadow` techniques for true pixel art stepped corners and shading.
- [x] **Task 3 (Screen & Auth Integration):** Ensure the screen UI matches the new flat pixel-art color palette.
- [x] **Task 4 (Error States & Mobile Polish):** Add the pixelated "GAME OVER" error state and ensure the entire console scales gracefully on mobile viewports.
