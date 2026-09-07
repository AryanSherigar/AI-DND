# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Creators & Worldbuilders:** Authors seeking to build interactive worlds, ranging from casual creators writing short premises and lore to dedicated dungeon masters crafting complex, deterministic worlds with stats, factions, inventories, and win/loss conditions without writing code.
- **Players:** Tabletop RPG enthusiasts, interactive fiction readers, and AI gamers who want immersive, turn-by-turn narrative gameplay where the game world and rules remain persistently consistent.
- **Spectators & Co-players:** Community members discovering, following, spectating, or participating in shared turn-based playthroughs.

## Product Purpose

wevr is an engine and platform for creating, publishing, discovering, and playing text-based AI-driven games turn by turn. It solves the gap between generic amnesiac AI roleplay chat (which lacks persistent rules and world state) and complex traditional game development engines (which demand heavy coding skill). Success means creators can author and publish rich, repeatable worlds at any complexity tier, while players experience coherent, high-stakes narratives guided by an AI narrator that respects the author's world rules.

## Positioning

- **Dual-mode authoring on a unified schema:** Creators can write freeform lore in Newbie mode or author deterministic state (stats, active conditions, faction dynamics, win/loss conditions) in Master mode on the same underlying scenario data model.
- **Deterministic AI narrator via validated tool-calling:** Story narration (driven by Gemini) cannot arbitrarily mutate game state; it proposes state changes via tool calls strictly validated against author-defined rules.
- **Persistent graph memory:** Backed by an external graph-based memory layer to eliminate LLM amnesia and ensure world events, NPCs, and lore remain durable across dozens of turns.
- **Published and shareable games:** Scenarios are published, tagged, discoverable, snapshot-versioned, and playable solo or cooperatively, with public spectator links.

## Operating Context

- **Web client:** Runs in modern desktop and mobile browsers. Primary interaction surfaces are:
  - **Studio (`/studio`):** Authoring workspace for scenario overview, lore ingestion, character/stat configuration, faction relationship graphs, active condition authoring, and pre-publish validation.
  - **Play (`/discover`, `/play`, `/spectate`, `/setup`):** Scenario discovery feed with filtering, playthrough lobby setup, and an immersive turn-by-turn reading and gameplay console featuring live narrative streaming, action entry, dice rolls, and state inspection.
- **Operating Rituals:** Turn resolution cycle (Player submits intent → TRS validates action, fetches state and memory, queries Gemini, validates tool calls, streams narrative chunks over SSE, updates state).

## Capabilities and Constraints

- **Capabilities:**
  - Dual-mode scenario creation (Newbie and Master modes).
  - Pre-playthrough scenario memory templating and state initialization.
  - Server-Sent Events (SSE) streaming for real-time narrative delivery.
  - Turn-based solo and multiplayer session support.
  - Playthrough sharing and spectating.
- **Constraints:**
  - Monorepo architecture: Frontend (Vite/React), Core API (FastAPI CRUD), Turn Resolution Service (FastAPI turn orchestrator).
  - Strict boundary: Gemini calls and SSE streaming exist only within Turn Resolution Service (`apps/turn-resolution-service`).
  - No direct LLM state mutations: Game state changes must pass through validated tool calls before PostgreSQL persistence.
  - Zero-latency local state management via React Query for server data and Zustand for local interactive state.

## Brand Commitments

- **Name:** wevr (stylized lowercase in logo mark and titles).
- **Tone & Voice:** Evocative, immersive, literary, and atmospheric; crafted to elevate storytelling without slipping into generic fantasy clichés or sterile tech jargon.
- **Visual Identity Anchor:** Dark-mode primary (`#0d0f14` base background, deep slate surfaces, amber/gold accents `#d9a441`), tactile and cinematic layout, high typographic hierarchy.

## Evidence on Hand

- Main Product RFC (`README.md`) specifying full technical architecture, C4 container and component diagrams, ADRs 1–10, and API contracts.
- Monorepo codebases in `apps/frontend`, `apps/core-api`, and `apps/turn-resolution-service`.
- Architecture boundaries and engineering guidelines in `CLAUDE.md`.
- No external customer testimonials or commercial partner claims currently exist; future UI work must not fabricate marketing proof or false quotes.

## Product Principles

1. **Dual Modes, Single Schema:** Never split the platform into incompatible toys and tools. Complexity is an incremental dial that creators opt into as their worlds deepen.
2. **World Coherence Over LLM Whim:** The AI narrator operates under the authority of scenario rules and durable memory, never overriding confirmed reality through hallucination.
3. **Atmospheric Immersion:** The interface acts as a quiet, cinematic vessel for world-weaving—prioritizing readability, typographic rhythm, and tactile focus over noisy decorations.
4. **Equal Craft for Authors and Adventurers:** Worldbuilding authoring ergonomics must match the immersion and polish of the player experience.

## Accessibility & Inclusion

- WCAG AA contrast standards across dark surfaces and text tokens.
- Reader accessibility: support for customizable narration typography, adjustable reading sizing, and high-contrast text options for prolonged narrative sessions.
- Full keyboard operability for turn input submission, hotkeys, and authoring forms.
- Semantic ARIA regions and live announcements for streamed narrative turns.
