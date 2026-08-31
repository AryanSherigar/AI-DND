# Spec: LivingBookHero Component

## 1. Objective & User Outcome
- **Problem Statement:** The landing page requires a high-performance, atmospheric "Living Book" hero section that relies entirely on CSS/SVG compositing over a single static image, rather than heavy video or multiple image assets.
- **User Story:** As a player visiting the platform, I want to be greeted by an immersive, atmospheric title screen with drifting mist, floating dust motes, and subtle mouse-responsive parallax, conveying a premium "high-fantasy" feel.
- **Success Criteria:** 
  - Smooth 60fps animations using only GPU-composited CSS properties (`opacity`, `transform`, `filter`).
  - Seamless fallback to static image when `prefers-reduced-motion` is active.
  - Implements a prop-controlled toggle (`mistRenderMode`) to switch between CSS blobs and SVG turbulence for A/B testing visual quality.
  - Maintains a clear left-third "negative space" area for the hero headline.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - `LivingBookHero.tsx`: Main component housing the structural DOM and `requestAnimationFrame` parallax loop.
  - `LivingBookHero.types.ts`: Props and configuration interfaces.
- **Data Flow:**
  - Component mounts -> Generates random positions/durations for dust motes and mist blobs once (preventing React hydration/re-render churn).
  - Mouse moves over the component -> Updates a mutable `ref` tracking target cursor coordinates.
  - A `requestAnimationFrame` loop uses `lerp` (Linear Interpolation) to smoothly interpolate current layer positions towards the target cursor coordinates, applying values directly to DOM node refs (bypassing React state for 60fps performance).

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Lint / Type-Check: `npx eslint . --ext .ts,.tsx` and `npx tsc --noEmit`

### 3.2. Testing Strategy & Conformance
- Visual testing: Using the internal dev toggle to compare `mistRenderMode="blobs"` vs `mistRenderMode="svg-turbulence"`.
- Accessibility: Ensure all animations are wrapped in standard `motion-safe` CSS media queries. If reduced motion is requested, all animation elements render statically or are removed.

### 3.3. Project Structure & File Layout
- Files to create: 
  - `apps/frontend/src/features/landing/components/LivingBookHero.tsx`
  - `apps/frontend/src/features/landing/components/LivingBookHero.types.ts`

### 3.4. Code Style & Interfaces
- Types:
  ```typescript
  export interface LivingBookHeroProps {
    baseImageUrl?: string;
    mistRenderMode?: 'blobs' | 'svg-turbulence';
    mistOpacity?: number;
    blobCount?: number;
    dustCount?: number;
    parallaxIntensity?: number;
  }
  ```

### 3.5. Git & Review Workflow
- Branch name: `feat/living-book-hero`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use pure CSS for ambient ambient drift (mist/dust). Use JS only for mouse parallax.
- 🚫 **Never:** Trigger React state updates in the parallax loop or animation frames. Do not animate layout properties (`top`, `left`, `width`).

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Touch Devices:** The parallax effect is disabled by checking for `window.matchMedia('(pointer: fine)')` or relying on standard CSS hover/pointer rules to avoid jank on mobile scroll.
- **SVG Performance:** `<feTurbulence>` can be heavy. We will limit the filter area to just the required mist zone (right 2/3rds) to avoid unnecessary GPU pixel calculations over the entire screen.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1:** Create `LivingBookHero.types.ts` with strict prop definitions.
- [ ] **Task 2:** Implement `LivingBookHero.tsx` layout structure (Base Image, Glow Layer).
- [ ] **Task 3:** Implement Dust Mote generation (memoized array with randomized CSS properties restricted to X >= 33%).
- [ ] **Task 4:** Implement Mist Layer (Blobs mode) using CSS animations.
- [ ] **Task 5:** Implement Mist Layer (SVG mode) using SMIL `<animate>` tags.
- [ ] **Task 6:** Wire up the custom `requestAnimationFrame` parallax hook.
- [ ] **Task 7:** Add a temporary Dev toggle button within the component to switch `mistRenderMode`.
