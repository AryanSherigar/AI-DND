# Spec: Redesign ScenarioCard & Carousel (YouTube-Style 16:9 Frameless Layout)

## 1. Objective & User Outcome
- **Problem Statement:** The scenario cards need to reflect YouTube's clean 16:9 layout: frameless presentation, floating thumbnail metadata badges, circular author avatars, and exact 3-card visible horizontal carousel layout with genre mist glow on hover.
- **User Story:** As a player browsing scenarios, I want to view scenarios in a clean 3-card-per-view horizontal row with 16:9 thumbnails, floating rating/player badges, circular author icons, and genre-specific hover glows.
- **Success Criteria:**
  - **Frameless Card Design:** No outer container border or background block in default state.
  - **16:9 Thumbnail Aspect Ratio:** Rounded corners (`rounded-2xl`) thumbnail with overlay badges in bottom-right for Rating (`★ 4.8`) and Player Count.
  - **Metadata Section Below Thumbnail:** Circular author avatar/icon on the left; Title (`IM Fell English SC`), Author, and Genre (`IBM Plex Mono`) on the right.
  - **Hover Container Tint:** On hover, a rounded background container (`p-3 rounded-2xl`) fills with a dark tint of the scenario's genre color (`backgroundColor: ${accentColor}18`), accompanied by a genre-tinted border (`borderColor: ${accentColor}70`) and subtle ambient glow.
  - **3-Card Horizontal Carousel:** Horizontal scroll carousel formatted to show exactly 3 cards visible at a time (`gap-6`) with smooth scroll controls.

---

## 2. Technical Architecture & Data Flow

### Components Involved
1. `apps/frontend/src/features/play/components/ScenarioCard.tsx`
   - YouTube-inspired frameless card structure.
   - 16:9 thumbnail with dark rounded stat badges (`rating`, `playerCount`).
   - Bottom metadata section with circular author avatar and title/author text block.
   - Hover state: Genre color ambient glow without image scaling.
2. `apps/frontend/src/features/play/components/ScenarioCarousel.tsx`
   - Horizontal carousel displaying 3 cards per view (`w-[calc((100%-3rem)/3)]` or responsive grid flex snap).
   - Handles sibling dimming on hover.

---

## 3. Implementation Plan & Tasks

- [ ] **Task 1: Redesign `ScenarioCard.tsx` (YouTube Frameless Style)**
  - Update `ScenarioCard.tsx` to 16:9 frameless design.
  - Add thumbnail stat badges (Rating, Player Count).
  - Add circular author avatar beside title and metadata.
  - Implement genre-colored hover glow (disable zoom).

- [ ] **Task 2: Update `ScenarioCarousel.tsx` (3 Cards Per View Layout)**
  - Configure card widths and gap spacing (`gap-6`, `w-[calc((100%-3rem)/3)]`) to display 3 cards visible per row.

- [ ] **Task 3: Quality & Build Verification**
  - Run `npm run build --prefix apps/frontend` to verify zero type or build errors.
