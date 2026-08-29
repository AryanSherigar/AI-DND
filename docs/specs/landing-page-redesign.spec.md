# Spec: Landing Page & UI Aesthetics Redesign

## 1. Objective & User Outcome
- **Problem Statement:** The current landing page utilizes generic rounded UI components ("bootstrapped SaaS" look) and lacks the immersive, awe-inspiring threshold feeling required for a high-fantasy AI storytelling platform. 
- **User Story:** As a prospective player, I want to land on a visually stunning, genre-adaptive page with deliberate motion and crafted UI, so that I immediately feel like I am stepping into a premium gaming experience.
- **Success Criteria:** 
  - Implementation of a strict dark mode shell (#0d0f14 to #14171f base).
  - Dynamic accent coloring applied to cards based on story genre.
  - Pixel-perfect typography system (`Pixelify Sans` for display, `Manrope` for body).
  - High-performance micro-interactions using pure CSS.
  - Seamless staggered mount reveals and page transitions via Framer Motion.

## 2. Technical Architecture & Data Flow
- **Components Involved:** 
  - `apps/frontend/src/features/play/pages/LandingPage.tsx`
  - `apps/frontend/src/features/play/components/HeroSection.tsx`
  - `apps/frontend/src/features/play/components/ScenarioCard.tsx`
  - `apps/frontend/src/features/play/components/ScenarioCarousel.tsx`
- **Sequence Flow:** 
  1. User navigates to the landing page.
  2. Framer Motion orchestrates the entry transition ("stepping into a scene").
  3. The `HeroSection` mounts with a slow, deliberate fade/rise (600-800ms) revealing the generated glowing portal artwork.
  4. As the user scrolls, `ScenarioCarousel` rows trigger staggered mount reveals.
  5. The `ScenarioCard` component reads the `genre` field from the mock/API data and maps it to a specific HEX accent color.
  6. Hovering a card triggers pure CSS transforms to reveal the `logline` and `playerCount` within the crafted clip-path silhouette.

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- Build: `cd apps/frontend && npm run build`
- Test: `cd apps/frontend && npm run test` *(assuming standard test scripts)*
- Lint: `cd apps/frontend && npm run lint`

### 3.2. Testing Strategy & Conformance
- Ensure Framer Motion accessibility: use `reducedMotion` hooks if needed, but primarily test that layout animations do not cause layout thrashing.
- Verify CSS clip-paths render correctly across browsers.
- Verify genre-to-color mapping gracefully degrades to a default accent if a genre is missing or unrecognized.

### 3.3. Project Structure & File Layout
- Files to modify:
  - `apps/frontend/src/features/play/pages/LandingPage.tsx`
  - `apps/frontend/src/features/play/components/HeroSection.tsx`
  - `apps/frontend/src/features/play/components/ScenarioCard.tsx`
  - `apps/frontend/tailwind.config.js` (to add typography and custom colors/easings)
  - `apps/frontend/index.css` (for global base styles and custom font imports)
  - `apps/frontend/package.json` (add framer-motion)

### 3.4. Code Style & Interfaces
```typescript
export type ScenarioGenre = 
  | 'High Fantasy'
  | 'Sci-Fi'
  | 'Noir / Detective'
  | 'Horror'
  | 'Slice of Life'
  | 'Mystery/Thriller'
  | 'Adventure/Survival'
  | 'Post-Apocalyptic/Dystopian';

export const GENRE_COLORS: Record<ScenarioGenre, string> = {
  'High Fantasy': '#D4AF6A',
  'Sci-Fi': '#4FD1E8',
  'Noir / Detective': '#C97A3D',
  'Horror': '#8B2635',
  'Slice of Life': '#C98BA8',
  'Mystery/Thriller': '#5B6EE1',
  'Adventure/Survival': '#7FA65C',
  'Post-Apocalyptic/Dystopian': '#9B9B7A',
};
```

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/landing-aesthetics-redesign`
- Ensure all Tailwind classes are successfully built and that CSS micro-interactions do not cause React re-renders.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use pure CSS/Tailwind for hover states on the cards. Use Framer Motion only for mount/scroll reveals and route transitions.
- ⚠️ **Ask First:** If changing the global routing structure is required to implement AnimatePresence for page transitions.
- 🚫 **Never:** Use inline styles for dynamic colors unless mapping CSS variables.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Performance Report:** CSS transforms (`transform`, `opacity`) for hover states run on the GPU compositor thread, costing ~0ms in JS execution time. Framer Motion for scroll reveals incurs a small parse/execution penalty (~15-30ms) on initial load, but provides standard `IntersectionObserver` performance for scroll reveals. It is a highly optimized library and completely justifiable for layout/mount transitions where CSS alone fails to manage React unmounts gracefully.
- Unrecognized genres in `ScenarioCard` should fallback to a neutral color (e.g., `#6B7280`).

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Design System & Shell):** Update `tailwind.config.js` with Pixelify Sans, Manrope, custom base colors (`#0d0f14`), and inject Google Fonts into `index.css`.
- [ ] **Task 2 (Hero Section & Image):** Refactor `HeroSection.tsx` to include the glowing portal artwork, implement the 600-800ms slow fade/rise, and adjust layout spacing.
- [ ] **Task 3 (Cards):** Refactor `ScenarioCard.tsx` using `clip-path` for the outer silhouette, a pseudo-element for the inset accent border, and dynamic inline CSS variables for the genre color. Implement hover state reveals using CSS transitions.
- [ ] **Task 4 (Framer Motion & Reveals):** Install `framer-motion`, wrap `ScenarioCarousel` items in staggered mount animations, and configure `AnimatePresence` for page transitions.
