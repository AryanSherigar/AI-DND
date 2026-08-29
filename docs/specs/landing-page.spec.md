# Spec: AI-DND Landing Page Redesign

## 1. Objective & User Outcome
- **Problem Statement:** The platform requires a premium, visually striking landing page that immediately immerses users in a high-fantasy world while remaining easy to navigate. It needs to combine the intuitive, low-cognitive-load layouts of modern streaming platforms (like Netflix) with the retro identity of 8-bit gaming.
- **User Story:** As a prospective player, I want to browse available game scenarios through a highly visual, categorized interface so that I can easily discover and select my next text-based adventure.
- **Success Criteria:** 
  - A full-screen Hero section featuring static high fantasy art and a single primary CTA (adhering to Hick's Law).
  - Categorized horizontal scrollable carousels below the hero section.
  - Hover-to-expand behavior on scenario cards revealing genre and author, with default visibility for Title, Rating, and Number of Players.
  - An aesthetic blend of sleek, minimal dark mode structural layouts (containers, navbars) and retro 8-bit pixel typography (fonts, primary buttons).
  - Initial implementation uses hardcoded mock data to perfect CSS and animations.

## 2. Technical Architecture & Data Flow
- **Components Involved:** React + Vite (Frontend app in `apps/frontend/`), Tailwind CSS for styling.
- **Data Flow:** For this phase, data is entirely client-side. A mock data file will supply scenario objects to the UI components. State management (Zustand) is not strictly necessary for the static layout but may be used if carousel state requires it.
- **Routing:** The landing page will be built at the root route `/` in the `play` feature boundary. Clicking a scenario card will route to a placeholder `/scenario/:id` page (out of scope for full implementation, but the link must exist).

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `npm run build` (within `apps/frontend`)
- Test: `npm run test` (within `apps/frontend`)
- Lint / Type-Check: `prettier --write . && eslint . --fix`

### 3.2. Testing Strategy & Conformance
- Test framework: React Testing Library.
- Strategy: Verify that the Hero section renders, horizontal carousels mount correctly, and hover states trigger the expanded card UI (if applicable to DOM testing). 
- Responsive checks: Ensure layout does not break on standard mobile viewport widths.

### 3.3. Project Structure & File Layout
- Files to create/modify in `apps/frontend/src/`:
  - `features/play/routes/LandingPage.tsx` (Main layout)
  - `features/play/components/HeroSection.tsx` (Static art, primary CTA)
  - `features/play/components/ScenarioCarousel.tsx` (Horizontal row)
  - `features/play/components/ScenarioCard.tsx` (Individual card with hover state)
  - `features/play/mock/scenarios.ts` (Hardcoded mock data)
  - `assets/fonts/` (Ensure retro font is loaded, e.g., 'Press Start 2P' or similar)

### 3.4. Code Style & Interfaces
- Type contracts (TypeScript interfaces in `features/play/types.ts`):
```typescript
export interface ScenarioMock {
  id: string;
  title: string;
  rating: number;
  playerCount: number;
  genre: string;
  author: string;
  coverImageUrl: string;
}
```

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/landing-page-redesign`

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use strict TypeScript; utilize Tailwind for styling; adhere to the "one component per file" rule; keep components under 30 lines where possible.
- ⚠️ **Ask First:** Adding new animation libraries (e.g., Framer Motion) if CSS/Tailwind transitions are insufficient.
- 🚫 **Never:** Fetch live data from Core API in this phase (stick to hardcoded).

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Mobile Experience:** Hover states do not exist on mobile touch screens. We must ensure the `ScenarioCard` degrades gracefully on mobile (e.g., clicking expands the card instead of routing immediately, or all info is displayed below the card on mobile).
- **Image Loading:** Large high-fantasy art might load slowly. Ensure placeholder backgrounds or CSS skeletons are visible while images load.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Setup & Mock Data):** Setup retro fonts in global CSS, define `ScenarioMock` interface, and populate `mock/scenarios.ts` with 10+ varied scenarios.
- [ ] **Task 2 (Hero Section):** Implement `HeroSection.tsx` with static background art, transparent-to-solid Navbar, and a pixel-styled primary CTA.
- [ ] **Task 3 (Scenario Cards):** Implement `ScenarioCard.tsx` with Tailwind hover transitions (`group-hover`), displaying base stats and revealing Genre/Author on hover.
- [ ] **Task 4 (Carousels & Layout):** Assemble rows in `ScenarioCarousel.tsx` and map mock data. Integrate all components into `LandingPage.tsx` with a dark mode background.
