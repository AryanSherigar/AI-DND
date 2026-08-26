# AI-DND — Main Product RFC

| | |
|---|---|
| **Authors** | Aryan Sherigar, Parth Dambhare |
| **Status** | Final |
| **Date** | 26 August 2026 |
| **Version** | 1.0 |

---

## Table of Contents

1. [Context & Goals](#context--goals)
   - [Problem Statement](#problem-statement)
   - [What We Are Building](#what-we-are-building)
   - [Target Persona](#target-persona)
   - [Core Product Loop](#core-product-loop)
   - [Key Product Decisions and Trade-offs](#key-product-decisions-and-trade-offs)
   - [Non-Goals](#non-goals)
   - [Open Items Carried Into Architecture](#open-items-carried-into-architecture)
2. [Technology Stack](#technology-stack)
3. [File Structure](#file-structure)
6. [System Architecture — C4 Level 3 — C4 Level 2 — C4 Level 1: Context](#system-architecture---c4-level-1-context)
3. [System Architecture — C4 Level 2: Containers](#system-architecture--c4-level-2-containers)
4. [System Architecture — C4 Level 3: Components](#system-architecture--c4-level-3-components)
7. [Data Flow & Sequence](#data-flow--sequence)
   - [Transport Model](#transport-model)
   - [Critical Path: Player Turn (Solo)](#critical-path-player-turn-solo)
   - [Multiplayer Delta](#multiplayer-delta)
8. [Data Models & Schema](#data-models--schema)
   - [Key Decisions](#key-decisions)
   - [Schema](#schema)
   - [Schema Additions](#schema-additions-post-scenario-ingestion-design)
9. [Scenario Ingestion](#scenario-ingestion)
   - [The Gap](#the-gap)
   - [Two Distinct Ingestion Paths](#two-distinct-ingestion-paths)
   - [Authoring-Time Ingestion by Mode](#authoring-time-ingestion-by-mode)
   - [Template Memory Space](#template-memory-space--ingest-once-clone-per-playthrough)
   - [Memory API Contract Change](#memory-api-contract-change)
   - [Playthrough Setup Screen](#playthrough-setup-screen)
10. [API Specifications](#api-specifications)
   - [Core API](#core-api)
   - [Turn Resolution Service](#turn-resolution-service)
11. [Cross-Cutting Concerns](#cross-cutting-concerns)
   - [Latency & Performance](#latency--performance)
   - [Authentication & Authorization](#authentication--authorization)
   - [Error Handling & Degradation](#error-handling--degradation)
   - [Content Safety](#content-safety)
   - [Data Consistency](#data-consistency)
   - [Partner Track](#partner-track)
12. [Architecture Decision Records](#architecture-decision-records-adrs)
    - [ADR-1: Core API and Turn Resolution Service split](#adr-1-core-api-and-turn-resolution-service-as-two-separate-services)
    - [ADR-2: SSE over WebSocket](#adr-2-sse-over-websocket)
    - [ADR-3: PostgreSQL as single primary store](#adr-3-postgresql-as-single-primary-store)
    - [ADR-4: Validate-before-apply](#adr-4-validate-before-apply-for-ai-tool-call-state-mutations)
    - [ADR-5: Batched memory writes](#adr-5-batched-memory-writes--not-per-turn-not-per-tool-call)
    - [ADR-6: Memory layer as external system](#adr-6-memory-layer-treated-as-an-external-system)
    - [ADR-7: Ingest-once-clone-many](#adr-7-ingest-once-clone-many-for-scenario-memory-template)
    - [ADR-8: Scenario versioning via snapshot](#adr-8-scenario-versioning-via-scenario_snapshot-not-a-version-table)
    - [ADR-9: when_active and active conditions](#adr-9-when_active-on-facts-and-active-conditions-instead-of-trigger-writes-to-memory)
13. [Open Items](#open-items)

---

# Context & Goals

## Problem Statement

Text-based roleplay and interactive fiction have a long, active fan base, from tabletop-style solo journaling and D&D-adjacent play to AI-driven story generators, but no platform currently lets a creator build a genuinely deep, structured world (on the scale of a LOTR or GoT setting, with factions, characters, relationships, history, and rules) and have that world played by others as an actual interactive game, not just read as static lore or a single scripted chat.

Existing tools sit at two extremes. On one end, generic AI chat/roleplay tools let a player improvise a story with an LLM, but offer no durable world model, no rules enforcement, and nothing for a creator to "publish" as a repeatable, shareable game. On the other end, traditional game engines (including text-based ones) demand real technical skill to build anything, putting complex world creation out of reach for most fans.

There is no engine today that lets a newcomer spin up a fun scenario in minutes, while also giving a dedicated creator the tools to build a deterministic, rules-governed world at genuine scale, publish it, and have strangers discover and play it, solo or together.

## What We Are Building

An engine and platform for creating and playing text-based AI-driven games, spanning a full spectrum of complexity:

- **Newbie mode**: a creator writes lore and a premise; the AI narrates freely on top of it, no rules authoring required.
- **Master mode**: a creator defines structured game state (stats, inventory, factions, timelines, win/lose conditions, custom rules) that the AI narrator must respect, enforced through tool-calling rather than free-form generation alone.

Both modes share a single world/scenario model, so complexity is something a creator opts into incrementally, not a separate track. Published scenarios are discoverable by other players through a tagged, filterable feed, and can be played solo or in turn-based multiplayer, with sessions shareable via link for others to spectate or join.

## Target Persona

AI gaming enthusiasts, D&D and tabletop roleplay fans, and interactive fiction readers who want either a quick, low-effort story to play, or the tools to build and share a serious, large-scale world, without needing to be a programmer. No formal "indie AI gaming studio" category exists yet in a structured way; this project is a candidate first step toward one.

## Core Product Loop

1. **Create**: author a scenario, from a short premise to a full structured world, using the engine's unified authoring model.
2. **Publish**: submit the scenario with metadata (genre/tag, complexity tier, player count support, estimated playtime, cover image); it passes a lightweight, creator-declared content check before appearing in the discovery feed.
3. **Discover**: other players browse or filter the feed by tag, genre, complexity, player count, and playtime, and see social signals (play count, ratings).
4. **Play**: a player starts an independent playthrough of a published scenario. An AI narrator, with tool-calling authority over structured game state where the scenario defines it, drives the experience turn by turn, backed by a graph-based memory layer for world consistency at scale.
5. **Share**: any playthrough can be shared via link for others to spectate, or to join as a turn-based multiplayer participant.

## Key Product Decisions and Trade-offs

- **Dual-mode engine, one schema.** Rather than building two separate products for casual and power users, the engine uses a single scenario/world data model that scales from a paragraph of lore to a fully structured, rule-governed setting. This is a harder schema design problem but avoids fragmenting the product or the audience.
- **Turn-based, not real-time, multiplayer.** Multiplayer play is scoped to one participant acting at a time, with the AI narrating between turns. This matches the target audience's existing expectations from tabletop and turn-based roleplay, and avoids the real-time synchronization complexity of simultaneous play.
- **Streaming to absorb AI latency.** Turn resolution may involve graph memory retrieval, one or more tool calls, and narrative generation, which takes real time. Responses are streamed to the player rather than returned all at once. This is an accepted trade-off, not an oversight: the target audience is accustomed to "the AI is thinking" pauses in this genre.
- **Lightweight, creator-declared content safety.** Creators tag their own scenario's content level at publish time; a lightweight check validates against the declared tag rather than performing open-ended content classification. This is intentionally minimal for hackathon scope, with a more robust system planned post-hackathon.
- **Lightweight auth for the hackathon.** Account and identity needs (publishing, ratings, shareable sessions, multiplayer participants) are met with a fast, minimal auth implementation, explicitly to be replaced with a more robust system afterward.
- **Real scale, not simulated scale.** Because the product's premise is supporting genuinely large, structured worlds, the architecture (particularly the graph-based memory and retrieval layer) is built to actually handle that scale, not merely to avoid ruling it out later.

## Non-Goals

The following are explicitly not being built for this project:

- **Real-time multiplayer voice chat.** A separate WebRTC/signaling infrastructure concern, orthogonal to the AI orchestration this project demonstrates.
- **Full audio narration.** The engine does not read the full story aloud.
- **Real-time or simultaneous multiplayer.** Multiplayer is turn-based only.
- **Monetization or creator economy.** No payments, subscriptions, or revenue-sharing are designed or built; noted only as a future direction.
- **Non-text core gameplay.** Images, music, and character-voice audio (if built) are optional presentation layers on top of a text-based core, not alternate modes of play.

The following are conditional stretch goals, attempted only if the core product loop is solid and time remains, and are not committed deliverables:

- **Voice input (speech-to-text)**, allowing a player to speak instead of type.
- **Character-line text-to-speech**, voicing a specific AI character's dialogue line (distinct from full narration, which remains a non-goal).
- **On-click scene images**, generated illustrative images for scenes.
- **Mood-based background music**, from a small curated, non-copyright, mood-tagged track library (not generative music).
- **Forking a playthrough**, letting another player branch their own copy from a shared session, built only if it falls out cheaply from the core session architecture.
- **PNG-tuber style character avatars** (AI-generated sprite states swapped during speech), dependent entirely on character-line TTS existing first.
- User Recommendation System

## Open Items Carried Into Architecture

A small number of decisions are deliberately deferred past Context & Goals and must be resolved before or during the build:

- **Final decision on playthrough forking** (build vs. defer), pending core session architecture being implemented.
- **Partner track selection**, deferred until the architecture is reviewed with the team. Integration slots are identified; track is not.
- **Memory batch trigger specifics** (fixed N turns, checkpoint-based, or time-based) — deferred to implementation, does not affect other architectural decisions.
- **Effect C** (trigger-driven direct game state mutation) — deferred to a future design pass.

The following were open at Context & Goals and have since been resolved: invalid tool-call / state-validation strategy (resolved in Level 3: Pydantic validate-before-apply), runtime content guardrails (resolved as explicit non-goal, flagged for post-hackathon).

## Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| **Frontend language** | TypeScript | Type safety across the full frontend codebase |
| **Frontend framework** | React + Vite | Fast HMR in dev, strong ecosystem, team familiarity. Vite handles bundling and dev server. |
| **Core API** | Python + FastAPI | Consistent with mem1's FastAPI stack; async-native, fast to build |
| **Turn Resolution Service** | Python + FastAPI | Same stack as Core API; SSE streaming supported natively via FastAPI's `StreamingResponse` |
| **Primary database** | PostgreSQL 16 via Cloud SQL | Google Cloud managed Postgres; zero operational overhead, automatic backups |
| **Auth provider** | Google Sign-In (Firebase Auth) | Lightweight, fast to integrate for hackathon; explicitly flagged for replacement post-hackathon |
| **AI narrator** | Gemini via Vertex AI / Google Cloud Agent Builder | Mandatory hackathon platform; handles narrative generation and tool-calling |
| **Image generation** _(stretch)_ | Vertex AI (Imagen) | Co-located on Google Cloud; same billing account, no additional auth setup |
| **TTS service** _(stretch)_ | Deferred to future | Not selected; deferred alongside the character-line TTS feature itself |
| **mem1 deployment** | Cloud Run (Docker container) | mem1 is already a containerized FastAPI service; Cloud Run drops it in with no changes |

### Deployment Platform

All services deploy to **Google Cloud** (mandatory for the hackathon):

- **Cloud Run** — serverless containers for Core API, Turn Resolution Service, and mem1. Scales to zero between requests, no cluster management, straightforward CI/CD via container push.
- **Cloud SQL** — managed Postgres 16 instance. Connects to Cloud Run services via Cloud SQL connector (no public IP needed).
- **Vertex AI** — Gemini API and Imagen API accessed via standard Vertex AI SDKs from within Cloud Run services.
- **Firebase Auth** — handles Google Sign-In token issuance; both Cloud Run services validate tokens on every request.

The architecture is intentionally sized for hackathon scale on Cloud Run. A post-hackathon scaling path would move long-running stateful services (notably the Turn Resolution Service's persistent SSE notification channel for multiplayer) to GKE if volume demands it, without architectural changes.

## File Structure

Monorepo. Three apps share one repository. Every file has a single, precise responsibility — no file mixes concerns. This keeps individual files small, readable, and safe to hand to an AI coding assistant without overwhelming context.

```
AI-DND/
├── apps/
│   ├── frontend/
│   ├── core-api/
│   └── turn-resolution-service/
├── docker-compose.yml         # Full local stack (all services + Postgres)
├── docker-compose.dev.yml     # Dev overrides (hot-reload mounts)
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml
│       ├── deploy-core-api.yml
│       └── deploy-trs.yml
├── .env.example
└── README.md
```

---

### Frontend (`apps/frontend/`)

Feature-based organisation. Each feature owns its components, hooks, store slice, API calls, and types. Nothing leaks across features except through `shared/`.

```
apps/frontend/
├── src/
│   ├── features/
│   │   ├── studio/                        # Scenario authoring surface
│   │   │   ├── components/
│   │   │   │   ├── EntityEditor/
│   │   │   │   │   ├── EntityEditor.tsx
│   │   │   │   │   └── EntityEditor.types.ts
│   │   │   │   ├── FactEditor/
│   │   │   │   │   ├── FactEditor.tsx
│   │   │   │   │   └── FactEditor.types.ts
│   │   │   │   ├── ConditionEditor/
│   │   │   │   │   ├── ConditionEditor.tsx
│   │   │   │   │   ├── ConditionEditor.types.ts
│   │   │   │   │   └── ExpressionBuilder/
│   │   │   │   │       ├── ExpressionBuilder.tsx  # Visual condition builder
│   │   │   │   │       ├── FieldPicker.tsx         # Picks game state field
│   │   │   │   │       ├── OperatorPicker.tsx      # <, >, ==, etc.
│   │   │   │   │       └── ValueInput.tsx          # Typed value entry
│   │   │   │   ├── StateSchemaEditor/
│   │   │   │   │   └── StateSchemaEditor.tsx      # Defines typed game state fields
│   │   │   │   ├── EndConditionsEditor/
│   │   │   │   │   └── EndConditionsEditor.tsx    # Win/lose condition authoring
│   │   │   │   ├── SetupSchemaEditor/
│   │   │   │   │   └── SetupSchemaEditor.tsx      # Player setup fields authoring
│   │   │   │   ├── NarratorPersonaEditor/
│   │   │   │   │   └── NarratorPersonaEditor.tsx  # System prompt / AI persona
│   │   │   │   ├── ScenarioMetaForm/
│   │   │   │   │   └── ScenarioMetaForm.tsx       # Title, tags, cover, playtime
│   │   │   │   └── PublishFlow/
│   │   │   │       ├── PublishFlow.tsx             # Publish confirmation + status
│   │   │   │       └── ContentTagPicker.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useScenario.ts                 # React Query: scenario CRUD
│   │   │   │   ├── useEntities.ts                 # React Query: entity CRUD
│   │   │   │   ├── useFacts.ts                    # React Query: fact CRUD
│   │   │   │   ├── useConditions.ts               # React Query: condition CRUD
│   │   │   │   └── usePublish.ts                  # Publish flow state
│   │   │   ├── stores/
│   │   │   │   └── studio.store.ts                # Zustand: active entity, panel state
│   │   │   ├── api/
│   │   │   │   ├── scenarios.api.ts
│   │   │   │   ├── entities.api.ts
│   │   │   │   ├── facts.api.ts
│   │   │   │   └── conditions.api.ts
│   │   │   ├── types/
│   │   │   │   ├── scenario.types.ts
│   │   │   │   ├── entity.types.ts
│   │   │   │   ├── fact.types.ts
│   │   │   │   └── condition.types.ts
│   │   │   └── pages/
│   │   │       ├── StudioPage.tsx                 # Creator dashboard
│   │   │       ├── NewScenarioPage.tsx
│   │   │       └── EditScenarioPage.tsx
│   │   │
│   │   ├── play/                                  # Discovery + gameplay surface
│   │   │   ├── components/
│   │   │   │   ├── DiscoveryFeed/
│   │   │   │   │   ├── DiscoveryFeed.tsx
│   │   │   │   │   ├── ScenarioCard.tsx
│   │   │   │   │   ├── FeedFilters.tsx
│   │   │   │   │   └── FeedSortBar.tsx
│   │   │   │   ├── SetupScreen/
│   │   │   │   │   ├── SetupScreen.tsx            # Pre-game setup fields
│   │   │   │   │   └── SetupField.tsx             # Single field (text or select)
│   │   │   │   ├── PlayScreen/
│   │   │   │   │   ├── PlayScreen.tsx             # Main play layout
│   │   │   │   │   ├── NarrationStream.tsx        # Renders streaming SSE tokens
│   │   │   │   │   ├── ActionInput.tsx            # Player action text input
│   │   │   │   │   ├── TurnIndicator.tsx          # Whose turn it is (multiplayer)
│   │   │   │   │   └── TurnHistory/
│   │   │   │   │       ├── TurnHistory.tsx        # Scrollable past turns
│   │   │   │   │       └── TurnEntry.tsx          # Single turn (action + narration)
│   │   │   │   └── SpectatorView/
│   │   │   │       └── SpectatorView.tsx          # Read-only play view
│   │   │   ├── hooks/
│   │   │   │   ├── useDiscovery.ts                # React Query: discovery feed
│   │   │   │   ├── usePlaythrough.ts              # React Query: playthrough state
│   │   │   │   ├── useTurnStream.ts               # SSE: per-request narration stream
│   │   │   │   ├── useNotifications.ts            # SSE: multiplayer turn-order channel
│   │   │   │   ├── useSpectator.ts                # SSE: spectator live stream
│   │   │   │   └── useSetup.ts                    # Setup form state
│   │   │   ├── stores/
│   │   │   │   └── play.store.ts                  # Zustand: active turn, SSE state
│   │   │   ├── api/
│   │   │   │   ├── discovery.api.ts
│   │   │   │   ├── playthroughs.api.ts
│   │   │   │   ├── turns.api.ts
│   │   │   │   ├── share.api.ts
│   │   │   │   └── ratings.api.ts
│   │   │   ├── types/
│   │   │   │   ├── playthrough.types.ts
│   │   │   │   ├── turn.types.ts
│   │   │   │   └── participant.types.ts
│   │   │   └── pages/
│   │   │       ├── DiscoveryPage.tsx
│   │   │       ├── SetupPage.tsx
│   │   │       ├── PlayPage.tsx
│   │   │       └── SpectatorPage.tsx
│   │   │
│   │   └── auth/                                  # Auth surface
│   │       ├── components/
│   │       │   ├── LoginButton/
│   │       │   │   └── LoginButton.tsx
│   │       │   └── AuthGuard/
│   │       │       └── AuthGuard.tsx              # Wraps protected routes
│   │       ├── hooks/
│   │       │   └── useAuth.ts
│   │       ├── providers/
│   │       │   └── AuthProvider.tsx               # Firebase Auth context
│   │       ├── stores/
│   │       │   └── auth.store.ts                  # Zustand: current user
│   │       ├── api/
│   │       │   └── auth.api.ts                    # Token exchange
│   │       ├── types/
│   │       │   └── auth.types.ts
│   │       └── pages/
│   │           └── LoginPage.tsx
│   │
│   ├── shared/                                    # Cross-feature shared code only
│   │   ├── components/
│   │   │   ├── ui/                                # shadcn/ui components (owned, customisable)
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Select.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Badge.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   └── Separator.tsx
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx
│   │   │   │   └── Header.tsx
│   │   │   └── feedback/
│   │   │       ├── LoadingSpinner.tsx
│   │   │       ├── ErrorBoundary.tsx
│   │   │       ├── EmptyState.tsx
│   │   │       └── Toast.tsx
│   │   ├── hooks/
│   │   │   ├── useSSE.ts                          # Generic SSE connection hook
│   │   │   ├── usePagination.ts
│   │   │   └── useDebounce.ts
│   │   ├── lib/
│   │   │   ├── api-client.ts                      # Base fetch wrapper (auth headers, errors)
│   │   │   ├── sse-client.ts                      # SSE connection factory
│   │   │   └── query-client.ts                    # React Query client config
│   │   ├── types/
│   │   │   ├── api.types.ts                       # Generic API response shapes
│   │   │   └── common.types.ts
│   │   └── constants/
│   │       ├── genres.ts                          # Fixed genre taxonomy
│   │       ├── predicates.ts                      # Common fact predicates
│   │       └── complexity-tiers.ts
│   │
│   └── app/
│       ├── App.tsx
│       ├── router.tsx                             # Route definitions
│       └── main.tsx                              # Vite entry point
│
├── public/
│   └── fonts/                                     # Retro/monospace font files
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── components.json                                # shadcn/ui config
└── package.json
```

---

### Core API (`apps/core-api/`)

One router, one service, one repository per domain. Service owns business logic; repository owns all SQL. Nothing talks to the database except repositories.

```
apps/core-api/
├── app/
│   ├── routers/                                   # HTTP routing only, no logic
│   │   ├── auth.py
│   │   ├── scenarios.py
│   │   ├── entities.py
│   │   ├── facts.py
│   │   ├── conditions.py
│   │   ├── playthroughs.py
│   │   ├── share.py
│   │   └── ratings.py
│   ├── services/                                  # Business logic, one per domain
│   │   ├── auth_service.py
│   │   ├── scenario_service.py
│   │   ├── entity_service.py
│   │   ├── fact_service.py
│   │   ├── condition_service.py
│   │   ├── playthrough_service.py
│   │   ├── share_service.py
│   │   ├── rating_service.py
│   │   └── publish_service.py                    # Publish flow orchestration
│   ├── repositories/                             # All SQL lives here, nowhere else
│   │   ├── scenario_repo.py
│   │   ├── entity_repo.py
│   │   ├── fact_repo.py
│   │   ├── condition_repo.py
│   │   ├── playthrough_repo.py
│   │   ├── participant_repo.py
│   │   ├── share_repo.py
│   │   ├── rating_repo.py
│   │   └── turn_log_repo.py
│   ├── models/                                   # Pydantic request/response schemas
│   │   ├── scenario.py
│   │   ├── entity.py
│   │   ├── fact.py
│   │   ├── condition.py
│   │   ├── playthrough.py
│   │   ├── participant.py
│   │   ├── share.py
│   │   ├── rating.py
│   │   └── turn_log.py
│   ├── integrations/
│   │   └── memory_client.py                     # Memory layer API (authoring-time ingest + clone)
│   ├── db/
│   │   ├── connection.py                         # Async Postgres connection pool
│   │   ├── base.py                               # SQLAlchemy Base — all models imported here
│   │   └── migrations/
│   │       ├── env.py                            # Alembic environment config
│   │       ├── script.py.mako                    # Migration file template
│   │       └── versions/
│   │           ├── 001_initial_schema.py
│   │           ├── 002_scenario_additions.py
│   │           └── 003_scenario_condition.py
│   ├── exceptions/                               # Custom exception classes, one file per domain
│   │   ├── base.py                               # Base app exception
│   │   ├── scenario_exceptions.py
│   │   ├── playthrough_exceptions.py
│   │   └── auth_exceptions.py
│   ├── middleware/
│   │   ├── auth.py                               # Firebase token validation
│   │   ├── error_handler.py
│   │   └── logging.py
│   ├── config.py                                 # Env vars, settings
│   └── main.py                                   # FastAPI app + router registration
├── tests/
│   ├── routers/
│   ├── services/
│   └── repositories/
├── alembic.ini                                   # Alembic config (points to db/migrations/)
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

### Turn Resolution Service (`apps/turn-resolution-service/`)

The turn flow is a pipeline of discrete steps, each in its own file. `pipeline.py` is the only file that knows the order. Every step file knows only its own job.

```
apps/turn-resolution-service/
├── app/
│   ├── routers/
│   │   ├── turn.py                               # POST /v1/turn
│   │   └── session.py                            # Notifications + spectator SSE
│   ├── turn/
│   │   ├── pipeline.py                           # Orchestrates steps in order
│   │   └── steps/                                # One file = one step, one job
│   │       ├── request_receiver.py               # Validate session, participant, turn order
│   │       ├── state_loader.py                   # Read Playthrough + scenario_snapshot
│   │       ├── condition_evaluator.py            # Evaluate ScenarioCondition expressions
│   │       ├── context_retrieval.py              # Call memory layer query
│   │       ├── ai_orchestrator.py                # Call Gemini with full context
│   │       ├── tool_handler.py                   # Prepare proposed state mutation
│   │       ├── state_validator.py                # Pydantic validate before apply
│   │       ├── state_writer.py                   # Write Playthrough.state + TurnLog
│   │       ├── memory_writer.py                  # Manage batch flush to memory layer
│   │       └── response_streamer.py              # Stream narration SSE to client
│   ├── session/
│   │   ├── notification_manager.py               # Multiplayer turn-order SSE channel
│   │   ├── spectator_manager.py                  # Spectator live SSE stream
│   │   └── turn_counter.py                       # Batch flush trigger + play_count increment
│   ├── integrations/
│   │   ├── memory_client.py                      # POST /v1/memory/query, POST /v1/memory/ingest
│   │   └── gemini_client.py                      # Vertex AI Gemini SDK wrapper
│   ├── models/
│   │   ├── game_state.py                         # Pydantic game state schema (master mode)
│   │   ├── turn.py                               # Turn request/response shapes
│   │   └── tool_call.py                          # Tool invocation + result shapes
│   ├── db/
│   │   └── connection.py                         # Postgres connection (shared schema, no migrations here)
│   ├── exceptions/                               # Custom exception classes
│   │   ├── base.py
│   │   ├── turn_exceptions.py
│   │   ├── session_exceptions.py
│   │   └── validation_exceptions.py
│   ├── middleware/
│   │   ├── auth.py
│   │   └── error_handler.py
│   ├── config.py
│   └── main.py
├── tests/
│   ├── turn/
│   │   └── steps/
│   └── integrations/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## System Architecture - C4 Level 1: Context

**Actors:**
- **Creator** — authors scenarios (from simple lore to full structured worlds) and publishes them
- **Player** — discovers, plays (solo or turn-based multiplayer), shares playthroughs, rates/likes scenarios
- _(Creator and Player are roles on the same account, not separate user types)_
**External systems:**
- **Gemini / Google Cloud Agent Builder** — powers the AI narrator: narrative generation and tool-calling authority over structured game state. Mandatory hackathon platform.
- **mem1** — pre-existing graph-based memory service (reused, not built for this hackathon). Provides world-fact storage, temporal/bitemporal reasoning, and grounded retrieval with an abstention gate. Integrated headlessly via its API (`/v1/chat`, `/v1/memory/search`, `/v1/memory/ingest`, `/v1/memory/stream`), our system does not use its bundled UI.
- **Auth provider** — lightweight identity provider (e.g., Google Sign-In/Firebase Auth), exact choice deferred to implementation
- **Partner service** — placeholder; track undecided, will integrate at whichever boundary fits naturally once chosen
- **Image generation service** _(conditional stretch)_ — for on-click scene images, if built
- **TTS service** _(conditional stretch)_ — for character-line voice, if built


![[Pasted image 20260825170128.png]]
## System Architecture — C4 Level 2: Containers

**Frontend**

- **Web app** — single application, two surfaces sharing one account/session:
    - _Studio surface_: scenario authoring (freeform + AI-assisted for newbie mode, fully manual structured editor for master mode), publish flow
    - _Play surface_: discovery feed, active play screen (streamed narrative, turn indicator, action input), session sharing

**Backend services**

- **Core API** — stateless request/response service handling auth, scenario CRUD, publish, discovery/search/filtering, ratings and social signals
- **Turn Resolution Service** — orchestrates the gameplay loop per player action: validates the action, retrieves context from mem1, calls Gemini with tool-calling authority, streams the narrated response back over SSE, writes new facts to mem1. Owns game-state validation (mechanism deferred). Stretch-goal outputs (mood tag, image/TTS triggers) would attach here without new containers.

**Storage**

- **PostgreSQL** — single durable store: scenarios, playthroughs/sessions, accounts, discovery metadata

**External systems** _(from Level 1, unchanged)_: Gemini/Agent Builder, mem1, auth provider, partner service (track TBD)

![[Pasted image 20260825172042.png]]

## System Architecture — C4 Level 3: Components

1. **Player submits action.** Frontend Play surface sends `POST /turn` to Turn Resolution Service, with the action text, session ID, and auth token. This opens the connection that will carry the streamed response.
2. **Request receiver validates the request.** Confirms the session exists, the player is a valid participant, and (for solo play) that it's a no-op turn-order check, always their turn.
3. **State loader fetches current playthrough state from Postgres.** Narrative history/position (newbie mode) or the full typed game state (master mode).
4. **Context retrieval calls mem1's new lightweight search endpoint**, passing the current action and relevant identifiers, gets back grounded world facts (or an abstention signal if nothing relevant is known).
5. **AI orchestrator calls Gemini**, passing the player action, loaded state, retrieved mem1 context, and (for master-mode) tool definitions.
6. **Gemini generates a response**, optionally invoking one or more tools mid-generation (e.g., "update relationship," "move location").
7. **If a tool was called**, the tool-call handler prepares the proposed state mutation, and the **state validator** checks it against the Pydantic-defined schema _before_ it's applied. If invalid, the mutation is rejected, Gemini's tool-call result is returned as a failure, and the AI is expected to recover in its next output token (still generating within the same call).
8. **Response streamer begins streaming Gemini's narration text back over the still-open connection from step 1**, token by token, to the Play surface, which renders it live.
9. **Once generation completes, state writer persists the updated (validated) playthrough state to Postgres.**
10. **The connection from step 1 closes** once streaming is complete. No memory write happens on this turn (batched/periodic only, per earlier decision), unless this turn happens to trigger the batch flush.

![[Pasted image 20260825182109.png]]
Core API is intentionally simple relative to Turn Resolution Service: standard stateless request/response handling for auth (delegating to the external auth provider), scenario CRUD (create/edit/delete for creators, including both newbie freeform and master structured authoring writes), the publish flow (attaching discovery metadata and running the lightweight content-tag check), and discovery/search (filtered, sorted queries against Postgres for tag, genre, complexity, player count, playtime, and social signals). It has no AI orchestration responsibilities and no streaming, every endpoint is a conventional request-in, response-out call against Postgres. No further component breakdown is needed at this stage; if it grows in complexity post-hackathon (e.g., a dedicated search service), that would warrant its own Level 3 pass at that time.



## Data Flow & Sequence

### Transport Model

Turn responses use **per-request SSE**, not a persistent long-lived connection. Each player action is a `POST /turn`; the response streams back over that same connection (`text/event-stream`) as the AI narrator generates it, then the connection closes. There is no always-open socket between turns. Session continuity comes from server-side state in Postgres, not a kept-open channel. This matches how ChatGPT and Claude web actually work, and is simpler than the original Level 2 assumption: no long-lived connection to manage, no reconnection logic needed for the main turn-response path.

For **multiplayer only**, a separate lightweight SSE channel exists solely for turn-order notifications — carrying almost no data, just a signal to the next participant that it is now their turn. This channel is not used for narration content, which stays on the per-request response stream. Solo play does not use this channel at all.

### Critical Path: Player Turn (Solo)

1. Player submits action — `POST /turn` to the Turn Resolution Service, carrying action text, session ID, and auth token. This opens the connection that will carry the streamed response.
2. **Request receiver** validates the session and participant. For solo play, the turn-order check is a no-op — it is always the player's turn.
3. **State loader** reads current playthrough state from Postgres: narrative history and position for newbie mode, or the full typed game state for master mode.
4. **Context retrieval** calls `POST /v1/memory/query` on the memory layer, passing the action text, scenario ID, playthrough ID, participant ID, and current checkpoint. Returns ranked structured facts, or an explicit abstention signal if nothing relevant is known.
5. **AI orchestrator** calls Gemini with the player action, loaded state, retrieved facts, and tool definitions (master mode only).
6. **Gemini generates a response**, optionally invoking one or more tools mid-generation (e.g., update relationship, move location, modify inventory).
7. **Tool-call handler** prepares the proposed state mutation. **State validator** (Pydantic) validates it against the defined schema *before* applying. If invalid, the mutation is rejected and returned to Gemini as a failure result; the AI recovers within the same generation without an extra round-trip.
8. **Response streamer** streams Gemini's narration back over the still-open connection from step 1, token by token, to the Play surface.
9. **State writer** persists the validated updated playthrough state to Postgres once generation completes.
10. The connection closes. No `POST /v1/memory/ingest` call this turn — memory writes are batched roughly every five turns, not per-turn.

### Multiplayer Delta

Steps 3–9 are identical. The differences are:

- **Step 2 is not a no-op.** The request receiver verifies it is actually this participant's turn, and rejects the action otherwise. This is a backend defense-in-depth check, not the primary enforcement mechanism.
- **Frontend enforcement is required.** It must not even be possible for a non-active participant to submit an action from the UI when it isn't their turn. The Play surface disables or hides the action input for non-active participants, informed by the turn-order state each participant's client holds. The backend check in step 2 is a safety net, not a substitute for a correct UI.
- **After step 9**, a lightweight turn-order notification fires on the separate SSE channel, telling the next participant it is their turn — re-enabling their action input and disabling the previous actor's.
- The **five-turn batch flush** to `POST /v1/memory/ingest` counts across the whole session, not per participant. Every fifth turn across all participants triggers the batch, regardless of which participant acted.

## Data Models & Schema

### Key Decisions

1. **Scenario mode is fixed at creation.** A scenario is either newbie or master — not both, and not changeable after creation. The two modes have meaningfully different authoring flows and world data structures; allowing mid-lifecycle mode switching would add complexity for no real user benefit.

2. **Discovery metadata is denormalized onto the `Scenario` table.** Genre tags, complexity tier, player count support, estimated playtime, cover image, content tag, and social signals (play count, likes, rating) live as columns directly on `Scenario`, not in a separate metadata table. The discovery feed is the highest-traffic read path — this denormalization eliminates a join on every feed query in exchange for a deliberate write-side trade-off that is acceptable at this scale.

3. **Turn history is a full append-only log, not just current state.** `TurnLog` records every action and narration, sequenced by turn number within a playthrough. This serves two distinct purposes: the player-facing scroll-back feature (a user may want to re-read turns from early in a long campaign), and the memory layer's extraction pipeline, which requires the last ~10 turns as context when processing each batch. The same log serves both without a duplicate system.

### Schema

```
User
  user_id           — primary key
  display_name
  auth_provider_id  — opaque ID from the external auth provider
  created_at

Scenario
  scenario_id       — primary key
  creator_id        — FK → User
  title
  mode              — "newbie" | "master", fixed at creation
  world_data        — jsonb: freeform lore + AI-extracted structure (newbie);
                      structured world graph entities/relationships (master)
  status            — "draft" | "published"
  — Discovery metadata (denormalized for read speed) —
  genre_tags        — array, fixed taxonomy
  complexity_tier   — "newbie" | "intermediate" | "master"
  player_count_support — "solo" | "multiplayer" | "both"
  estimated_playtime
  cover_image_url
  content_tag       — creator-declared, used for lightweight moderation
  play_count
  rating_avg
  — —
  current_version     — integer, incremented on each publish
  created_at
  updated_at

Playthrough
  playthrough_id    — primary key
  scenario_id       — FK → Scenario
  created_by        — FK → User
  state             — jsonb: current narrative position / typed game state;
                      Pydantic-validated before every write (master mode)
  checkpoint        — current progression point, passed to memory layer for
                      visibility-scoped retrieval
  turn_count        — total turns taken so far; used to trigger the ~5-turn
                      memory batch flush
  status            — "active" | "completed" | "abandoned"
  scenario_version   — integer, which version this playthrough was created on
  scenario_snapshot  — jsonb: static copy of narrator_persona, state_schema,
                       end_conditions, checkpoints, and active conditions at
                       creation time. TRS reads this, never Scenario directly.
  created_at
  updated_at

Participant
  participant_id    — primary key
  playthrough_id    — FK → Playthrough
  user_id           — FK → User
  role              — "owner" | "joined"
  turn_order_position — integer; determines turn sequence in multiplayer
  joined_at

PlaythroughShare
  share_token       — unique, unguessable token (the share link key)
  playthrough_id    — FK → Playthrough
  mode              — "spectate" | "join"
  created_at

TurnLog
  turn_id           — primary key
  playthrough_id    — FK → Playthrough
  turn_number       — sequential integer within the playthrough
  participant_id    — FK → Participant (who acted; nullable for system entries)
  action_text       — the player's submitted action
  narration_text    — AI-generated narration, written once streaming completes
  tool_calls        — jsonb: tool invocations and validated results for this turn,
                      if any
  created_at

  INDEX (playthrough_id, turn_number) — supports paginated scroll-back queries
  ("give me turns 80–100") and last-N-turns fetches for the memory layer
  extraction pipeline
```

### Schema Additions (post Scenario Ingestion design)

The following columns are added to `Scenario` and a new table added, as a result of decisions made during the Scenario Ingestion design pass. All internal structures use jsonb to remain flexible during implementation.

```
Scenario — additional columns
  narrator_persona      — text: scenario-specific system prompt / AI narrator
                          personality. Applies to both newbie and master mode.
  setup_schema          — jsonb: array of creator-defined player setup fields,
                          rendered on the play surface before the first turn.
                          Each entry: { field_key, label, type ("text"|"select"),
                          options (array, select only), required (bool), metadata (jsonb) }
                          Character name is always present as a system-level field,
                          not authored here.
  state_schema          — jsonb (master mode only): defines the typed game state
                          fields, their types, and initial values. This is what
                          the TRS state validator (Pydantic) validates
                          Playthrough.state against on every write.
  end_conditions        — jsonb (master mode only): array of win/lose conditions.
                          Each entry uses the same visual expression tree as
                          ScenarioCondition, with an outcome tag ("win" | "lose").
                          Evaluated by TRS after each state write.
  checkpoints           — jsonb (master mode only): ordered list of named
                          progression points the creator defines. TRS advances
                          the current checkpoint; the memory layer uses it for
                          visibility-scoped retrieval.
  rules                 — jsonb: empty placeholder for future custom rules /
                          magic systems. No design now; column exists to avoid
                          a migration later.

ScenarioCondition       — creator-authored persistent active conditions (master mode)
  condition_id          — primary key
  scenario_id           — FK → Scenario
  label                 — creator-facing name (e.g., "Ghost follows player")
  condition_expression  — jsonb: visual expression tree evaluated by TRS every
                          turn against current Playthrough.state.
                          e.g., { field: "player.health", op: "<", value: 5,
                                  AND: { field: "entered_cave", op: "==", value: true } }
  condition_version     — version tag for the expression schema. Allows old
                          expression trees to remain interpretable when the DSL
                          stretch goal is built. Same rationale as
                          extraction_version on Fact in the memory layer.
  narrator_instruction  — text: passed directly to the AI orchestrator on every
                          turn the condition is active. e.g., "A ghost is
                          silently following the player."
  metadata              — jsonb: forward-compatibility field
  created_at
```

**Relationships between entities** are not a separate concept. They are modeled as facts with relational predicates (e.g., `member_of`, `allied_with`). The fact model handles them without a dedicated table or UI surface.

---

## Scenario Ingestion

### The Gap

The turn flow and memory integration were designed assuming relevant world facts already exist in the memory layer when context retrieval runs on turn one. What was never decided: how a scenario's foundational lore and world data get into memory in the first place. Without an answer, the very first turn's context retrieval finds nothing.

### Two Distinct Ingestion Paths

These are fundamentally different operations — not one ingestion pipeline run at different times:

1. **Authoring-time ingestion** — runs once per scenario, at Publish. Establishes the initial world-fact baseline that exists before any player ever takes a turn. Output: a scenario-scoped template memory space.
2. **Runtime ingestion** — runs during active play, batched roughly every five turns. Captures new facts and events that emerge during a specific playthrough. Output: new facts written into the playthrough-scoped memory space. Already designed; unchanged here.

### Authoring-Time Ingestion by Mode

**Master mode — direct write, no LLM extraction.**
The creator has already specified exactly what everything means through the structured editor. Running that input through an LLM extractor would be wasteful and risks the LLM reinterpreting something the creator specified precisely — directly contradicting the core trust guarantee of master mode (the system will not reinterpret your world). Master-mode entities and facts map close to 1:1 onto the memory layer's Entity and Fact schema:

- **Entities**: `canonical_name`, `entity_type`, `aliases`, `description` → memory layer Entity record, direct write.
- **Facts**: `subject` (entity), `predicate`, `object` (entity or literal), `valid_from` (optional, defaults to story start), `when_active` (optional expression, evaluated against game state during retrieval) → memory layer Fact record, direct write. Supersession between pre-authored facts is handled implicitly via `when_active` conditions, not explicit SUPERSEDES links.
- **Active conditions** (`ScenarioCondition` rows): not ingested into the memory layer. Evaluated locally by TRS every turn against `Playthrough.state`. When a condition is active, its `narrator_instruction` is passed directly to the AI orchestrator as guaranteed context, independently of memory retrieval.

**Newbie mode — LLM extraction.**
Creator writes freeform prose (premise + optional lore). The same LLM extractor used for runtime ingestion processes this prose into structured entities and facts, which are then written to the template memory space. No structural authoring required from the creator.

### Template Memory Space — Ingest Once, Clone Per Playthrough

Authoring-time ingestion runs once per scenario into a **scenario-scoped template memory space**. When a player starts a new playthrough, the template is cloned into a fresh **playthrough-scoped memory space**. Dynamic facts from that player's story accumulate there without touching the template or any other player's space.

**Why clone rather than re-ingest per playthrough:** re-running extraction per playthrough would duplicate LLM cost for identical lore and add extraction latency to playthrough start. Ingest-once-clone-many saves both.

**Who triggers the clone:** the Core API, when it creates the `Playthrough` row. By the time the player reaches the play surface, the memory space is already initialized and TRS never has to conditionally check whether memory exists.

### Memory API Contract Change

Pre-authored master-mode facts carry a `when_active` expression evaluated against current game state during retrieval. This requires `POST /v1/memory/query` to accept a game state snapshot alongside the query text — so the memory layer can evaluate `when_active` conditions as part of its retrieval filtering. This is a change to the memory layer API contract from the version specified in the Memory Layer RFC.

### Playthrough Setup Screen

Before the first turn begins, the play surface renders a setup screen:

- **Character name** — always present, system-level, not creator-authored.
- **Creator-defined setup fields** — rendered from `Scenario.setup_schema`. Each field is either `text` (free input) or `select` (dropdown from creator-defined options). Required fields must be filled before proceeding.

On submission, the Core API initializes `Playthrough.state` with the submitted values (seeding the typed game state for master mode, or a minimal starting state for newbie mode), creates the `Participant` row, triggers the memory clone, and returns — all before the player's first action.

## API Specifications

The system exposes two distinct services. All endpoints require an auth token in the request header except where noted.

---

### Core API

Stateless request/response. Handles everything except the live gameplay loop.

#### Auth

**`POST /v1/auth/token`**
Exchange an external auth provider token (e.g., Google Sign-In) for an internal session token. Thin wrapper — delegates to the external auth provider.

---

#### Scenarios

**`POST /v1/scenarios`**
Create a new scenario in draft status. Request includes `title`, `mode` (`newbie` | `master`, fixed at creation), and `narrator_persona`. Returns the created scenario with its `scenario_id`.

**`GET /v1/scenarios/{scenario_id}`**
Fetch full scenario details including all authored content. Creator-only for draft scenarios; public once published.

**`PATCH /v1/scenarios/{scenario_id}`**
Update scenario fields (title, narrator_persona, world_data, setup_schema, state_schema, end_conditions, checkpoints, rules). Allowed on both draft and published scenarios. Active playthroughs are unaffected — they are pinned to their `scenario_snapshot` at creation. Increments `current_version` on the Scenario.

**`DELETE /v1/scenarios/{scenario_id}`**
Delete a draft scenario. Published scenarios cannot be deleted while active playthroughs exist.

**`POST /v1/scenarios/{scenario_id}/publish`**
Trigger the publish flow: runs the lightweight content check against the declared `content_tag`, then triggers authoring-time ingestion into the memory layer (LLM extraction for newbie mode, direct write for master mode), creating the scenario-scoped template memory space. Returns `202 Accepted` — publish is asynchronous. Scenario status moves to `published` on completion.

---

#### Master-Mode Authoring Sub-Resources

These endpoints manage the structured world content for master-mode scenarios. All write directly to the memory layer's Entity/Fact schema shape in Postgres (`world_data`), bypassing LLM extraction.

**`POST /v1/scenarios/{scenario_id}/entities`**
Add an entity. Request: `canonical_name`, `entity_type`, `aliases` (optional), `description`.

**`PATCH /v1/scenarios/{scenario_id}/entities/{entity_id}`**
Update an entity's fields.

**`DELETE /v1/scenarios/{scenario_id}/entities/{entity_id}`**
Remove an entity and any facts that reference it as subject or object.

**`POST /v1/scenarios/{scenario_id}/facts`**
Add a fact. Request: `subject_entity_id`, `predicate`, `object` (entity ID or literal), `valid_from` (optional), `when_active` (optional expression jsonb), `superseded_fact_id` (optional — the fact this one explicitly replaces).

**`PATCH /v1/scenarios/{scenario_id}/facts/{fact_id}`**
Update a fact's fields.

**`DELETE /v1/scenarios/{scenario_id}/facts/{fact_id}`**
Remove a fact.

**`POST /v1/scenarios/{scenario_id}/conditions`**
Add an active condition. Request: `label`, `condition_expression` (jsonb expression tree), `narrator_instruction`.

**`PATCH /v1/scenarios/{scenario_id}/conditions/{condition_id}`**
Update a condition.

**`DELETE /v1/scenarios/{scenario_id}/conditions/{condition_id}`**
Remove a condition.

---

#### Discovery Feed

**`GET /v1/scenarios`**
Returns published scenarios. Supports filtering and sorting via query parameters:
- `genre_tags` — one or more tags from the fixed taxonomy
- `complexity_tier` — `newbie` | `intermediate` | `master`
- `player_count_support` — `solo` | `multiplayer` | `both`
- `estimated_playtime` — range filter (short / medium / long, exact ranges defined at implementation)
- `sort` — `play_count` | `rating_avg` | `created_at` (default: `created_at` descending)
- `cursor` — pagination cursor for infinite scroll

Response: array of scenario summary objects (discovery metadata fields only, not full world data), next cursor.

---

#### Playthroughs

**`POST /v1/playthroughs`**
Create a new playthrough. Request: `scenario_id`, `setup_values` (map of `field_key` → value, covering character name and any creator-defined setup fields). Core API: creates the `Playthrough` and `Participant` rows, initializes `Playthrough.state` from `state_schema` initial values merged with setup input, writes `scenario_snapshot`, triggers the memory layer clone (`POST /v1/memory/playthrough/{id}/init`). Returns the `playthrough_id` and initialized state once clone completes.

**`GET /v1/playthroughs/{playthrough_id}`**
Fetch playthrough info (status, turn count, current participant, participant list). Auth-gated: only participants and valid share-token holders can access.

**`GET /v1/playthroughs/{playthrough_id}/turns`**
Paginated `TurnLog` for a playthrough. Used by: players scrolling back through history, spectators loading past turns before connecting to the live stream. Query params: `page`, `page_size`, `from_turn` (fetch from a specific turn number). Auth-gated: participants and valid spectate-token holders.

**`POST /v1/playthroughs/{playthrough_id}/share`**
Generate a share token. Request: `mode` (`spectate` | `join`). Returns a `share_token` and the full shareable URL. One token per mode per playthrough is sufficient; implementation may return existing token if one already exists.

**`POST /v1/playthroughs/join`**
Join a playthrough as a multiplayer participant via a `join`-mode share token. Request: `share_token`. Creates a new `Participant` row with `role: joined` and assigns a `turn_order_position`. Fails if the scenario's `player_count_support` is `solo`, or if the playthrough is not `active`.

---

#### Ratings

**`POST /v1/scenarios/{scenario_id}/rating`**
Submit or update a rating (integer 1–5). Requires the caller to have at least 10 turns played in any playthrough of this scenario — enforced by checking `Playthrough.turn_count >= 10` for the requesting user. Updates `Scenario.rating_avg` as a running average. A user may update their rating; their previous rating is replaced, not added.

---

### Turn Resolution Service

Stateful per turn. Handles the live gameplay loop and streaming.

**`POST /v1/turn`**
Submit a player action. Request body: `playthrough_id`, `participant_id`, `action_text`. Opens the connection that carries the streamed response (`text/event-stream`). The stream emits:
- `narration` events — token-by-token AI narration as it is generated
- `state_update` event — the validated, updated game state, emitted once generation completes
- `mood` event — a lightweight mood tag for background music (stretch, if built)
- `done` event — signals stream end; connection closes

On the 10th turn, also emits a `play_count_update` signal internally (TRS increments `Scenario.play_count` directly in Postgres).

**`GET /v1/session/{playthrough_id}/notifications`**
Multiplayer-only SSE channel. Long-lived connection per participant. Emits:
- `your_turn` — signals the next participant that it is now their turn (sent after the previous actor's turn completes)
- `participant_joined` — when a new participant joins via share link
- `playthrough_ended` — when a win/lose condition is met

Not used for narration content. Solo play does not use this endpoint.

**`GET /v1/session/{playthrough_id}/spectate`**
Live SSE stream for spectators holding a valid `spectate`-mode share token. Emits the same `narration`, `state_update`, and `done` events as `POST /v1/turn`, but read-only. Spectators load turn history separately via `GET /v1/playthroughs/{playthrough_id}/turns` (Core API), then connect here to follow the live session.

## Cross-Cutting Concerns

### Latency & Performance

Turn resolution involves memory retrieval, one or more Gemini calls, optional tool-call round-trips, and a Postgres state write. This takes real, variable time. The mitigation is streaming: narration tokens begin reaching the player as soon as Gemini starts generating, so perceived latency is the time to the first token, not the time to a complete response. The target audience — turn-based AI RPG and roleplay players — is accustomed to "the AI is thinking" pauses; this is a conscious, accepted trade-off, not an oversight.

Per-step latency expectations:
- **Active condition evaluation** (TRS, post state load): cheap and deterministic — a local expression tree evaluation against an in-memory jsonb, no external calls.
- **Memory retrieval** (`POST /v1/memory/query`): target 1–2 seconds. Player-facing and blocking; architecture is designed around this target.
- **Gemini call + tool-call round-trips**: variable. Streaming masks end-to-end duration; the player sees output within seconds of generation starting.
- **Postgres reads** (state loader, TurnLog): fast indexed queries, not a latency concern at hackathon scale.
- **Postgres write** (state writer, post-generation): happens after narration has already streamed; not player-perceived.

### Authentication & Authorization

Auth is required for every endpoint across both services — no anonymous access, including spectators. The exact auth provider is deferred to implementation (e.g., Google Sign-In / Firebase Auth); this RFC treats it as a pluggable external dependency. The auth layer is explicitly lightweight for the hackathon and flagged for replacement with a more robust system post-hackathon.

Authorization rules:
- **Scenario** — draft scenarios are readable/editable by the creator only. Published scenarios are publicly readable (discovery feed, detail view).
- **Playthrough** — readable by participants and valid share-token holders only. Not publicly browsable.
- **Share tokens** — unguessable tokens validated on every request against `PlaythroughShare`. `spectate` tokens grant read-only access to turn history and the live spectate stream. `join` tokens additionally allow creating a `Participant` row.
- **Ratings** — enforced per-user, gated on 10+ turns played in any playthrough of the scenario.
- **Turn submission** — TRS validates that the submitting participant is the active turn holder before processing. Frontend enforces this too (action input disabled for non-active participants), but backend validation is the authoritative check.

### Error Handling & Degradation

**Gemini timeout or failure mid-turn:**
TRS retries the Gemini call. During the retry window, the player receives a visible in-stream message ("taking longer than expected…") rather than a silent wait. If retries are exhausted, the player receives an explicit failure notice and the turn is not committed — `Playthrough.state` and `TurnLog` are not written, the player may resubmit their action.

**Postgres write failure after narration has streamed:**
Narration has already reached the player, but the state write failed. TRS retries the write. If retries fail, the session degrades gracefully: the player is notified that the session state may not have saved correctly, but can continue playing. The next successful state write will reflect the correct state from that point forward. Partial state loss between the failed write and recovery is an accepted trade-off under graceful degradation.

**Memory batch failure:**
The memory layer operates on a best-effort, eventually-consistent basis relative to Postgres. If a `POST /v1/memory/ingest` batch fails, TRS does not fail the turn or block the player — gameplay continues. On the next batch trigger (5 turns later), TRS sends both the current batch and the previously failed turns (up to 10 turns total). If this combined batch also fails, the player receives a low-key, in-fiction-appropriate notice (e.g., "the world may not perfectly remember recent events") rather than a technical error. Play is never blocked by memory write failures. Postgres `TurnLog` remains the durable source of truth; memory staleness is recoverable.

### Content Safety

Content safety at publish time is the only active mechanism. Creators self-declare a content tag at publish; the publish flow runs a lightweight check validating the submitted content against the declared tag. There is no open-ended content classification.

Runtime AI narrator content guardrails during active play are explicitly not built for this project. The narrator inherits its behavioral constraints from the scenario's declared content tag via the system prompt (`narrator_persona`). This is an acknowledged gap, not an oversight, and is flagged for a more robust solution post-hackathon.

### Data Consistency

Postgres is the single source of truth for all product state. The memory layer is an eventually-consistent auxiliary system — it is always derived from or consistent with Postgres data, never ahead of it, and its staleness is bounded by the batch cadence (roughly every 5 turns). Playthrough continuity never depends on memory being current; a stale or temporarily unavailable memory layer degrades retrieval quality but does not break play.

`Playthrough.state` is always Pydantic-validated before write. An invalid proposed mutation (from a Gemini tool call) is rejected before it reaches Postgres; the narrator is expected to recover within the same generation. A state write that fails after validation is retried; if it cannot be persisted, the player is notified but can resubmit.

### Partner Track

The partner track for the hackathon is undecided. The architecture is deliberately partner-agnostic, with pluggable slots at natural boundaries: the memory layer integration, the AI orchestration layer, and the storage tier are all candidates for partner integration without requiring architectural changes. The partner track will be selected and mapped to one of these slots once decided with the team.

## Architecture Decision Records (ADRs)

### ADR-1: Core API and Turn Resolution Service as two separate services

**Context:** The system has two radically different request profiles — simple CRUD and discovery queries, and the complex, stateful, streaming, multi-step gameplay loop.

**Decision:** Split into two services. Core API handles auth, scenario CRUD, publish, discovery, and social signals — stateless, fast, easy to scale horizontally. Turn Resolution Service handles the entire per-turn gameplay loop — stateful for the duration of a turn, long and variable latency, highest complexity and failure surface.

**Alternatives considered:** A single unified API was rejected because it would couple simple discovery queries to the most complex, failure-prone code path, making both harder to deploy, scale, and reason about independently.

**Consequences:** Two services to deploy and monitor. Clean separation of concerns and a presentable "orchestration layer" architectural story. Each service can be scaled and updated independently.

---

### ADR-2: SSE over WebSocket

**Context:** The system requires server-to-client streaming for narration and multiplayer turn-order notifications.

**Decision:** Server-Sent Events (SSE) for both the per-request narration stream and the separate multiplayer notification channel. Player actions travel over standard HTTP POST; streaming is strictly server-to-client.

**Alternatives considered:** WebSocket was rejected because multiplayer is explicitly turn-based, not real-time or simultaneous — WebSocket's bidirectional capability goes entirely unused. SSE has simpler reconnection semantics (built-in browser auto-reconnect), simpler server-side scaling (no sticky-session or pub-sub backplane for a server-to-client-only model), and is consistent with the memory layer's own `GET /v1/memory/stream` precedent.

**Consequences:** No bidirectional persistent connection. Player actions are standard HTTP requests. SSE connections are per-request for narration (open for one turn, then close) and persistent for the multiplayer notification channel.

---

### ADR-3: PostgreSQL as single primary store

**Context:** The system needs durable storage for scenarios, playthroughs, accounts, discovery metadata, and turn history.

**Decision:** PostgreSQL as the sole primary store. `jsonb` columns handle schema-flexible content (world data, game state, scenario snapshots) while keeping core relational structure queryable and indexed. Discovery feed filtering runs as plain indexed Postgres queries — no dedicated search engine needed at hackathon scale.

**Alternatives considered:** A dedicated vector database on the product side was rejected — semantic search over world facts is the memory layer's responsibility, not something to replicate in core storage. A separate search engine (e.g., Elasticsearch) was rejected as unnecessary overhead at hackathon scale.

**Consequences:** Single operational dependency for primary storage. Reduces new-tech overhead given existing team familiarity with Postgres via the memory layer. `jsonb` flexibility trades some query power for schema agility where needed.

---

### ADR-4: Validate-before-apply for AI tool-call state mutations

**Context:** The AI narrator (Gemini) can invoke tools to mutate structured game state in master-mode scenarios. Invalid mutations must be caught.

**Decision:** Pydantic models define the valid game state schema (field names, types, enums, ranges). A proposed mutation from a tool call is validated against the Pydantic model before being applied to `Playthrough.state`. Invalid mutations are rejected and returned to Gemini as a failure result within the same generation; the AI recovers without an extra round-trip.

**Alternatives considered:** Apply-then-rollback was rejected — it wastes tokens and LLM cost on a committed mutation that then has to be undone. Post-hoc validation after streaming completes was rejected — by then narration describing the invalid state has already reached the player.

**Consequences:** Validation is schema/constraint-level only — it catches type violations, out-of-range values, and invalid entity references, but not semantic game-logic errors (e.g., whether a character can physically reach a location). This boundary is stated honestly; the RFC does not overclaim validation coverage.

---

### ADR-5: Batched memory writes — not per-turn, not per-tool-call

**Context:** The memory layer accepts text and extracts facts via an LLM call. Writing after every turn or every tool call would scale cost linearly with gameplay.

**Decision:** Memory writes are batched, triggered roughly every five turns. The exact trigger (fixed N, checkpoint-based, or time-based) is deferred to implementation. Per-turn and per-tool-call immediate writes were explicitly rejected.

**Alternatives considered:** Per-tool-call immediate writes were considered (captures structured changes right away) and rejected — the cost scales with every structured action rather than being bounded and predictable. Per-turn writes were rejected for the same reason.

**Consequences:** A slight staleness window exists between game events and their appearance in memory — acceptable because narration has already reached the player before any batch runs, and nothing player-facing depends on immediate memory durability. Batch failures are handled via a 10-turn catchup on the next trigger, with a low-key player notice if that also fails.

---

### ADR-6: Memory layer treated as an external system

**Context:** mem1 is a large, pre-existing, independently developed service with its own UI, API, and storage. The main product integrates with it headlessly via its API contract.

**Decision:** mem1 is modeled as a peer external system at C4 Level 1 — equivalent in status to Gemini or the auth provider — not folded into the product's own containers. It is explicitly disclosed as a pre-existing, reused component, not built for this hackathon.

**Alternatives considered:** Treating it as an internal container was rejected — it would misrepresent authorship for hackathon judging and bloat Level 2/3 diagrams with another system's internals.

**Consequences:** Clean architectural boundary. The Turn Resolution Service is designed against a stable API contract (`POST /v1/memory/query`, `POST /v1/memory/ingest`), decoupling the product architecture from the memory layer's internal implementation. The underlying implementation (mem1 as-is, the ideal design, or a mixture) remains an open question that does not block the main RFC.

---

### ADR-7: Ingest-once-clone-many for scenario memory template

**Context:** Every playthrough of a published scenario needs its own isolated memory space, pre-populated with the scenario's foundational world facts.

**Decision:** Authoring-time ingestion runs once per scenario at publish, creating a scenario-scoped template memory space. When a player starts a new playthrough, the template is cloned into a fresh playthrough-scoped space. Dynamic facts from that player's story accumulate there independently.

**Alternatives considered:** Re-ingesting per playthrough was rejected — it duplicates LLM extraction cost for identical lore and adds extraction latency to every playthrough start.

**Consequences:** The memory layer requires a distinct clone operation (`POST /v1/memory/playthrough/{id}/init`) separate from ingestion. Playthrough start latency includes the clone operation, handled by Core API before the player reaches the play surface.

---

### ADR-8: Scenario versioning via `scenario_snapshot`, not a version table

**Context:** Creators can edit published scenarios. Active playthroughs must remain on the version they were created on.

**Decision:** At playthrough creation, Core API writes a `scenario_snapshot` jsonb column on `Playthrough` containing all scenario-authored content that TRS reads during turns (`narrator_persona`, `state_schema`, `end_conditions`, `checkpoints`, active conditions). TRS reads only per-playthrough data — it never reads from `Scenario` during active turns. `Scenario` stores only a `current_version` integer for display and audit.

**Alternatives considered:** A `ScenarioVersion` table snapshotting all scenario content on each publish was considered and rejected — the snapshot-on-playthrough-creation approach achieves the same isolation more simply, since TRS only ever needs the data that was current at playthrough creation, and that data is already per-playthrough.

**Consequences:** Playthrough creation is slightly heavier (writes a potentially large snapshot). No old scenario content is stored beyond what live playthroughs reference. Editing a scenario does not affect any in-flight playthrough.

---

### ADR-9: `when_active` on facts and active conditions, instead of trigger-writes-to-memory

**Context:** Master-mode scenarios need to express world states that are conditionally true (e.g., "Sukuna is the strongest, but only after checkpoint 3") and persistent behaviors that must always reach the narrator (e.g., "a ghost follows the player while health < 5").

**Decision:** Two mechanisms replace a trigger-writes-to-memory model. Pre-authored facts carry an optional `when_active` expression evaluated against current game state during retrieval — the fact is always in memory, returned only when its condition is met. Active conditions (`ScenarioCondition`) carry a condition expression evaluated by TRS every turn; when active, their `narrator_instruction` is passed directly to the AI orchestrator as guaranteed context, independently of memory retrieval.

**Alternatives considered:** A trigger mechanism that writes new facts to memory when conditions fire was rejected — it requires a separate write path, adds operational complexity, and for persistent behaviors specifically, is unreliable since memory retrieval is relevance-based and may not surface the fact on every turn. The two-mechanism approach handles both use cases more cleanly.

**Consequences:** `POST /v1/memory/query` must receive a game state snapshot so the memory layer can evaluate `when_active` conditions during retrieval — a change to the memory layer API contract. TRS gains a lightweight condition evaluation step after state loading on every turn.

---

## Open Items

The following are explicitly unresolved and must be decided before or during the build:

**Fork playthroughs (Open-1)**
Whether a player can branch their own copy from a shared playthrough session is still undecided. It was scoped as "build only if cheap given core architecture." Must be resolved with the team once core session architecture is implemented — the `PlaythroughShare` and `Playthrough` data models are designed to accommodate it, but the clone/branch operation and its memory layer implications are not designed.

**Partner track (Open-2)**
The hackathon partner track is undecided. The architecture is deliberately partner-agnostic, with natural integration slots at the memory layer boundary, the AI orchestration layer, and the storage tier. To be decided with the team once the architecture is drafted and reviewed.

**Auth provider specifics (Open-3)**
The exact auth provider and implementation method are deferred to implementation time. The system is designed to treat auth as an external dependency; swapping providers requires no architectural change. Explicitly flagged for replacement with a more robust system post-hackathon.

**Memory batch trigger specifics (Open-4)**
The exact batching trigger — fixed N turns, checkpoint-based, or time-based — is deferred to implementation. Current design uses "roughly every five turns" as a placeholder. Does not affect any other architectural decision.

**Effect C: trigger-driven direct game state mutation (Open-5)**
Active conditions currently instruct the narrator but do not directly mutate `Playthrough.state`. A future extension (Effect C) would allow creator-authored conditions to directly change game state fields when they fire — without waiting for the AI narrator's tool call. Not designed, not built; deferred to a future design pass as it introduces a second state-mutation path alongside the AI narrator's tool calls.
