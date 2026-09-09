# wevr — System Architecture

| | |
|---|---|
| **Authors** | Aryan Sherigar, Parth Dambhare |
| **Status** | Living document — describes the system as actually built and deployed |
| **Last updated** | 10 September 2026 |

This document replaces the original pre-build RFC. That RFC proposed a design before any code existed; a lot has changed since — scene images, mood-based music, minigames, master-mode maps, and Cloud Run deployment all moved from "stretch goal" or "undecided" to shipped, working features, and several early design assumptions (SSE transport, the memory layer's real name and mechanics, the exact turn pipeline) turned out differently once built. Where the two documents would disagree, this one is correct: every claim here was traced against the actual code, not reproposed from the original design.

---

## Table of Contents

1. [Overview](#overview)
2. [Key Product Decisions & Trade-offs](#key-product-decisions--trade-offs)
3. [Non-Goals](#non-goals)
4. [Technology Stack](#technology-stack)
5. [Deployment](#deployment)
6. [Monorepo File Structure](#monorepo-file-structure)
   - [Frontend](#frontend-appsfrontend)
   - [Core API](#core-api-appscore-api)
   - [Turn Resolution Service](#turn-resolution-service-appsturn-resolution-service)
   - [Memory Layer (HydraDB)](#memory-layer-appsmemory-layer)
7. [System Architecture — C4 Level 1: Context](#system-architecture--c4-level-1-context)
8. [System Architecture — C4 Level 2: Containers](#system-architecture--c4-level-2-containers)
9. [System Architecture — C4 Level 3: Components](#system-architecture--c4-level-3-components)
10. [Data Flow & Sequence](#data-flow--sequence)
    - [Transport Model](#transport-model)
    - [The Turn Resolution Pipeline](#the-turn-resolution-pipeline)
    - [Multiplayer Delta](#multiplayer-delta)
    - [Minigame Flow](#minigame-flow)
    - [Scene Image Flow](#scene-image-flow)
11. [Data Models & Schema](#data-models--schema)
12. [Scenario & Memory Ingestion](#scenario--memory-ingestion)
13. [API Specifications](#api-specifications)
    - [Core API](#core-api-endpoints)
    - [Turn Resolution Service](#turn-resolution-service-endpoints)
    - [Memory Layer (internal)](#memory-layer-internal-endpoints)
14. [Cross-Cutting Concerns](#cross-cutting-concerns)
15. [Architecture Decision Records (ADRs)](#architecture-decision-records-adrs)
16. [Known Limitations & Deferred Work](#known-limitations--deferred-work)

---

## Overview

wevr is an engine and platform for creating and playing text-based AI-driven games, spanning two authoring modes on one shared scenario model:

- **Newbie mode** — a creator writes lore and a premise; the AI narrates freely on top of it, no rules authoring required.
- **Master mode** — a creator defines structured game state (stats, factions, entities, facts, invariants, win/lose conditions, minigames) that the AI narrator must respect, enforced through validated tool-calling rather than free-form generation.

**Core product loop:** a creator authors a scenario in Studio (from a short premise to a fully structured world, with AI-generated cover art, an AI-composed score, and optional maps and minigames) → publishes it, which ingests its foundational lore into a graph-based memory layer → other players discover it through a filterable feed → a player starts an independent playthrough, and a Gemini-powered narrator drives it turn by turn, streaming narration live and retrieving grounded world facts from memory for consistency → any playthrough is shareable via link for spectating or turn-based multiplayer.

**Target persona:** AI gaming enthusiasts, D&D and tabletop roleplay fans, and interactive fiction readers who want either a quick, low-effort story to play, or the tools to build and share a large-scale, rules-governed world, without needing to be a programmer.

**Four services, one repository:**

| Service | Path | Purpose |
|---|---|---|
| Frontend | `apps/frontend/` | React + Vite + TypeScript. Studio (authoring) and Play (discovery + gameplay) surfaces. |
| Core API | `apps/core-api/` | Python + FastAPI. Auth, scenario CRUD, publish flow, discovery, playthroughs, ratings/reviews, uploads. Stateless request/response only — no AI calls (with two narrow, documented exceptions, see below), no streaming. |
| Turn Resolution Service (TRS) | `apps/turn-resolution-service/` | Python + FastAPI. Orchestrates the per-turn gameplay loop: validates action → loads state → retrieves memory → calls Gemini → validates tool calls → streams narration → persists state. The only service with narration/tool-calling AI calls and SSE streaming. |
| Memory Layer (HydraDB) | `apps/memory-layer/` | Python + FastAPI + a vendored Rust graph engine. Provenance-preserving, bitemporal long-term memory: turns conversation and authored lore into a durable graph with hybrid vector/graph retrieval. Developed as part of this project, not a third-party product, but architecturally treated as an external system (see [ADR-6](#adr-6-memory-layer-treated-as-an-external-system)) because the rest of the monorepo integrates with it purely over HTTP. |

**A documented exception to "no AI calls outside TRS":** `apps/core-api/app/integrations/image_gen_client.py` and `music_gen_client.py` call Vertex AI directly for AI-generated scenario cover art and AI-composed music tracks. Both are synchronous, Studio-only authoring actions (not part of the live gameplay loop), and both are explicitly called out in code as an approved, narrow exception to the "Gemini calls only from TRS" rule — not an accidental violation of it.

---

## Key Product Decisions & Trade-offs

- **Dual-mode engine, one schema.** Newbie and master mode share a single `scenarios` table and world model rather than being separate products — complexity is a dial creators opt into, not a fork in the product.
- **Turn-based, not real-time, multiplayer.** One participant acts at a time; the AI narrates between turns. Avoids real-time synchronization complexity entirely.
- **Streaming to absorb AI latency.** Turn resolution can involve memory retrieval, one or more Gemini tool-call round-trips, and a Postgres write — real, variable time. Narration streams to the player as it's generated rather than waiting for a complete response.
- **Lightweight, creator-declared content safety.** Creators self-tag a scenario's content level at publish; the publish flow validates against the declared tag rather than running open-ended content classification. There is still no runtime content moderation during active play — see [Known Limitations](#known-limitations--deferred-work).
- **Lightweight-but-real auth.** Firebase Auth (Google Sign-In) issues identity; both Core API and TRS independently issue and verify their own short-lived JWTs on top of it, with refresh-token rotation. See [Authentication & Authorization](#authentication--authorization).
- **Real scale, not simulated scale.** The memory layer is a genuine hybrid vector+graph retrieval system (Postgres/pgvector + a native graph engine with multi-hop traversal), not a keyword-search stand-in — built to actually support large, structured worlds.

---

## Non-Goals

Still explicitly not built:

- **Real-time multiplayer voice chat.**
- **Full audio narration** — the engine does not read the full story aloud.
- **Real-time or simultaneous multiplayer** — turn-based only.
- **Monetization or creator economy** — no payments, subscriptions, or revenue-sharing.
- **Character-line text-to-speech** and **PNG-tuber style character avatars** — not built.
- **Voice input (speech-to-text)** — not built.
- **Playthrough forking** — a player branching their own copy from a shared session. Still undecided; the `playthrough_shares` table would accommodate it, but the clone/branch operation and its memory-layer implications are not designed.

**Shipped since the original RFC** (these were "conditional stretch goals" or open questions at RFC time — they are now real, built features, not aspirations): AI-generated scene images (Gemini, per-turn, "see" action mode only), mood-based background music (both a curated default track library per mood and Vertex AI Lyria-002 generation), and master-mode minigames via a Replit partnership (a curated built-in dodge/survival game, plus a "bring your own" Replit-embed path with a starter SDK in `replit-template/`).

---

## Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| **Frontend language** | TypeScript, strict mode | |
| **Frontend framework** | React 18 + Vite | React Router v6 (`createBrowserRouter`); Studio/Play/Spectator routes lazy-loaded. |
| **Frontend server state** | TanStack React Query | ~40+ hooks across features; single shared `QueryClient`. |
| **Frontend client state** | Zustand | Exactly three stores: `auth.store.ts`, `studio.store.ts`, `play.store.ts` (the last owns turn-submission/SSE lifecycle). |
| **Frontend UI kit** | Tailwind CSS + a small owned shadcn-style component set, plus an `aceternity/`-style motion component set | No inline styles. |
| **Core API** | Python + FastAPI, async throughout | `asyncpg`/SQLAlchemy async engine. |
| **Turn Resolution Service** | Python + FastAPI | SSE via `StreamingResponse` / `sse-starlette`. |
| **Memory Layer** | Python + FastAPI, plus a vendored Rust graph engine (HydraDB, `SlateDB`-backed) | Own React+Vite chat/graph-visualization UI, not used by the product — integrated headlessly over HTTP. |
| **Primary database** | PostgreSQL 16 via Cloud SQL | Two logical databases: `aidnd_db` (Core API + TRS, shared schema) and `context_memory` (memory layer, separate instance database, includes pgvector). |
| **Object storage** | Google Cloud Storage | Cover images, scene images, map images, generated audio. Falls back to local disk automatically outside production (see [ADR-14](#adr-14-storage-client-abstracts-gcs-vs-local-disk-by-environment)). |
| **Auth provider** | Firebase Auth (Google Sign-In) | Both backend services independently verify Firebase tokens and issue their own app JWTs (access + refresh) on top. |
| **AI narrator** | Gemini on Vertex AI, **Express Mode** (API-key auth via `google-genai`, not full ADC/service-account auth) | Narration + master-mode tool-calling model: `gemini-3.5-flash-lite`. Same auth pattern reused for every other Vertex AI call in the system — see [ADR-12](#adr-12-vertex-ai-accessed-via-express-mode-api-key-everywhere). |
| **Image generation** | Gemini on Vertex AI, `gemini-3.1-flash-image`, via `generate_content` | Not the Imagen API — this project's Vertex AI access does not include an Imagen model, so images are extracted from `inline_data` parts of a `generate_content` response instead. Used for scene images (TRS) and scenario cover art (Core API). |
| **Music generation** | Vertex AI Lyria-002, via a raw `predict` REST call | The `google-genai` SDK has no dedicated Lyria endpoint, so `music_gen_client.py` calls the publisher-model `predict` endpoint directly through the SDK's underlying API client. Produces one fixed-length (~32.8s) loopable track per mood. |
| **Memory-layer embeddings** | Vertex AI `text-embedding-005` via `google-genai` | Replaced an earlier local `sentence-transformers`/`torch` model — embeddings now require a live Google Cloud call, no local model weights. |
| **Deployment platform** | Google Cloud Run (Frontend, Core API, TRS, Memory Layer) + a standalone GCE VM (HydraDB's own graph engine) | See [Deployment](#deployment). |

---

## Deployment

All four Cloud-Run-hosted services (`frontend`, `core-api`, `turn-resolution-service`, `memory-layer`) deploy independently to **Cloud Run**, region `us-central1`, project `wevr-507318`. Deploys are currently **manual** — there is no CI/CD pipeline in the repository (`.github/workflows/` does not exist); each service is rebuilt with `gcloud builds submit` and redeployed with `gcloud run deploy`.

**Why HydraDB's graph engine is not on Cloud Run:** it's a stateful process (`SlateDB`-backed), so it runs on a dedicated GCE VM instead, reached over HTTPS with a bearer token — a deliberate speed-over-hardening trade-off for now (no VPC connector; the firewall rule is scoped to the token, not the network). The `memory-layer` FastAPI service itself (the Python side, which talks to both Postgres and the HydraDB VM) does run on Cloud Run like the other three services.

**Data stores:**
- **Cloud SQL** (Postgres 16, single instance, two databases): `aidnd_db` for Core API + TRS (shared schema, TRS never runs migrations, only reads/writes what Core API's Alembic migrations define), `context_memory` for the memory layer (separate migration runner, `scripts/run_migrations.py`).
- **Google Cloud Storage** — one bucket for all generated/uploaded media (cover images, scene images, map images, audio).

**Identity:** each Cloud Run service has its own service account (least-privilege: Cloud SQL client + Secret Manager accessor for all; Core API and TRS additionally get object-admin scoped to the uploads bucket). Firebase Auth is a separate Google Cloud project from the one hosting Cloud Run — cross-project Firebase token verification needs no IAM link, but any new frontend origin must be added to Firebase's Authorized Domains list or sign-in breaks.

**Secrets** are stored in Secret Manager and mounted as environment variables at deploy time (JWT signing key, Gemini/Vertex API key, memory-layer API key, HydraDB bearer token, database URLs).

**CORS:** Core API and TRS both read an explicit `CORS_ORIGINS` allow-list from configuration — every deployed frontend origin (the Cloud Run frontend URL, and any additional deployment such as a Replit mirror) must be added there explicitly, or browser requests from that origin are rejected regardless of auth validity.

---

## Monorepo File Structure

```
AI-DND/
├── apps/
│   ├── frontend/
│   ├── core-api/
│   ├── turn-resolution-service/
│   └── memory-layer/
├── replit-template/           # Starter kit + minigame-sdk.js for creator-hosted Replit minigames
├── docs/                      # Architecture docs, ADRs, feature specs
├── music/                     # Mood-tagged ambient tracks (curated default soundtrack library)
├── docker-compose.yml         # Full local stack (all services + Postgres)
├── ARCHITECTURE.md            # This document
├── PRODUCT.md                 # Product/brand schema
├── CLAUDE.md                  # Engineering guidelines enforced on every file
└── README.md
```

Every file has a single, precise responsibility — no file mixes concerns (enforced by `CLAUDE.md`'s layering rules). This is what actually keeps files small and legible, not just an aspiration.

### Frontend (`apps/frontend/`)

Feature-based. Six feature directories now exist — the original design anticipated only three (`studio/`, `play/`, `auth/`); `profile/`, `landing/`, and `misc/` were added as the product grew.

```
apps/frontend/src/
├── features/
│   ├── studio/            # Authoring surface — by far the largest feature
│   │   ├── pages/          # StudioPage, NewScenarioPage, EditScenarioPage
│   │   ├── hooks/          # ~26 hooks, one per authoring domain (entities, facts,
│   │   │                   #  conditions, invariants, end_conditions, maps, minigames,
│   │   │                   #  music, uploads, publish, playtest, AI assistant chat, ...)
│   │   ├── stores/         # studio.store.ts (Zustand)
│   │   ├── api/            # One *.api.ts per domain
│   │   ├── types/          # Mirrors api/
│   │   └── components/     # 28 subdirs, incl. EntityEditor, FactEditor, ConditionEditor
│   │       (+ ExpressionBuilder), InvariantEditor, EndConditionsEditor, MapEditor,
│   │       MinigameEditor, MusicSlotEditor, CoverImageUploader, AIChatSidebar,
│   │       NarratorPersonaEditor, RulesEditor, StateSchemaEditor, SetupSchemaEditor,
│   │       ScenarioMetaForm, ScenarioDashboard, OpeningSceneEditor, ActionChipsEditor,
│   │       NarrationFontPicker, MarkdownEditor, NewbieWizard (guided flow),
│   │       MasterModeCreateFlow, PublishFlow, PlaytestButton, Layout/ (its own
│   │       tabbed master-mode studio shell + nav)
│   │
│   ├── play/               # Discovery + gameplay surface
│   │   ├── pages/          # DiscoveryPage, ScenarioFocusPage, JoinPage, SetupPage,
│   │   │                   #  PlayPage, SpectatorPage
│   │   ├── hooks/          # useDiscovery, useSetup, useTurns, + SSE-driven:
│   │   │                   #  useTurnStream, useNotifications, useSpectator,
│   │   │                   #  useMinigameResult
│   │   ├── stores/         # play.store.ts — turn submission/SSE lifecycle, minigame
│   │   │                   #  result reconciliation, ebook chapter state
│   │   ├── api/
│   │   └── components/     # PlayScreen/ (splits into MasterPlayScreen /
│   │       NewbiePlayScreen + EBook/), MinigameOverlay/, SpectatorView/,
│   │       DiscoveryFeed/, ScenarioFocus/, SetupScreen/, MapViewer/
│   │
│   ├── auth/                # LoginPage, useAuth, AuthProvider (Firebase), auth.store,
│   │                         #  AuthGuard, GoogleSignInButton, JudgeSignInButton (demo path)
│   ├── profile/              # ProfilePage + Bookmarks/Campaigns/Creations/Reviews tabs
│   ├── landing/               # LandingPage
│   └── misc/                  # NotFoundPage, TermsPage, PrivacyPage
│
├── shared/                    # Cross-feature code only — features never import each other
│   ├── components/
│   │   ├── ui/                # Owned shadcn-style kit + ui/aceternity/ motion components
│   │   ├── layout/             # AppShell, AppNav, Header, Footer, Sidebar
│   │   ├── feedback/            # ErrorBoundary, Loader, Toast
│   │   └── minigames/            # DodgeMinigame/ (full canvas game engine) and
│   │                              #  ReplitEmbed/ — the two minigame delivery mechanisms
│   ├── hooks/
│   │   └── useSSE.ts             # The ONLY React lifecycle wrapper around SSE (see below)
│   ├── lib/
│   │   ├── api-client.ts          # Shared axios instance: auth header injection,
│   │   │                          #  401-refresh-queue interceptor
│   │   ├── sse-client.ts           # Custom fetch-based SSE transport (see ADR-11) —
│   │   │                           #  raw browser EventSource is used NOWHERE in this app
│   │   └── firebase.ts              # Firebase SDK init
│   ├── constants/
│   └── types/
└── app/
    ├── App.tsx
    ├── router.tsx                   # React Router v6 route table
    └── main.tsx
```

### Core API (`apps/core-api/`)

Strict layering: `Router → Service → Repository → Database`. One router/service/repository per domain; ORM models live under `db/models/`, distinct from the Pydantic request/response schemas in `models/`.

```
apps/core-api/app/
├── routers/          # 17 files: auth, scenarios, entities, facts, conditions,
│                     #  invariants, end_conditions, scenario_entity_types, maps,
│                     #  minigames, scenario_music, music_defaults, playthroughs,
│                     #  share, logs, uploads, users
│                     #  (ratings.py exists but is empty/unregistered — dead file,
│                     #   see Known Limitations)
├── services/         # One per domain, plus publish_service.py (publish flow
│                     #  orchestration) and default_music.py
├── repositories/     # All SQL lives here — nowhere else
├── db/
│   ├── models/        # SQLAlchemy ORM — the real schema source of truth (21 tables)
│   └── migrations/versions/001_initial_schema.py   # squashed from 14 original files
├── models/            # Pydantic request/response schemas (not ORM)
├── integrations/
│   ├── memory_client.py       # The only file permitted to call the memory layer
│   ├── image_gen_client.py    # AI cover-art generation (approved AI-call exception)
│   ├── music_gen_client.py    # AI music generation (approved AI-call exception)
│   └── storage_client.py      # The only file that talks to GCS / local disk
├── exceptions/        # One file per domain, all inherit app/exceptions/base.py
├── middleware/         # auth.py (Firebase + app-JWT verification), error_handler.py,
│                        #  request_context.py
├── config.py            # All env vars read here, nowhere else
└── main.py
```

### Turn Resolution Service (`apps/turn-resolution-service/`)

`turn/pipeline.py` is the only file that knows step order — steps in `turn/steps/` never call each other directly.

```
apps/turn-resolution-service/app/
├── routers/
│   ├── turn.py         # POST /v1/turn — the gameplay loop entry point
│   ├── session.py       # Spectate + multiplayer notification SSE
│   └── assistant.py      # Studio AI co-writer chat (a second, distinct AI surface)
├── turn/
│   ├── pipeline.py         # Sequences every step below, in order
│   ├── tool_definitions.py  # Fixed Gemini function-calling schema (master mode)
│   ├── expression_evaluator.py, mood.py, state_paths.py, turn_order.py
│   └── steps/                # One file, one job — see Data Flow below for the real order
│       ├── request_receiver.py, state_loader.py, minigame_result_resolver.py,
│       ├── condition_evaluator.py, context_retrieval.py, ai_orchestrator.py,
│       ├── tool_handler.py, state_validator.py, map_state_sync.py,
│       ├── minigame_trigger_evaluator.py, scene_image_generator.py, state_writer.py,
│       ├── end_condition_evaluator.py, turn_summary_builder.py, memory_writer.py,
│       └── response_streamer.py
├── session/
│   ├── notification_manager.py    # In-process pub/sub — multiplayer "your turn" signal
│   ├── spectator_manager.py        # In-process pub/sub — live spectator relay
│   └── access.py                    # Share-token / participant auth for session routes
├── integrations/
│   ├── gemini_client.py       # Narration + tool-calling — the primary AI call site
│   ├── image_gen_client.py     # Scene-image generation (its own copy of the client;
│   │                            #  intentional duplication, documented exception)
│   ├── memory_client.py         # Query (per turn) + batched ingest
│   └── storage_client.py         # Scene-image upload
├── db/models/          # Read-only mirror of Core API's ORM models — TRS never migrates
├── exceptions/, middleware/, models/
├── config.py
└── main.py
```

### Memory Layer (`apps/memory-layer/`)

Not a router/service/repository layering — a pipeline-stage module layout, with `context_memory/engine.py` as a single facade and `context_memory/composition.py` as the one dependency-injection wiring point (enforced by import-layering lint rules).

```
apps/memory-layer/
├── db/migrations/           # 14 forward-only SQL migrations → context_memory database
├── hydradb/                  # Vendored Rust graph engine (AGPL-3.0, separately licensed;
│                              #  runs as its own networked process, never statically linked)
├── frontend/                  # HydraDB's own React+Vite chat/graph UI — not used by wevr
├── scripts/                    # run_migrations.py, benchmark/eval/backfill scripts
└── src/
    ├── api/                     # routes.py, server.py, stream.py — the FastAPI boundary
    ├── chat/                     # CLI REPL for interactive testing
    ├── evaluation/                 # LongMemEval-style benchmark runner
    └── context_memory/             # The actual engine
        ├── engine.py                # MemoryEngine facade — everything routes through it
        ├── composition.py            # Single DI wiring point
        ├── core/                      # config, LLMClient, journal/tracing/tools harness
        ├── ingestion/                  # orchestrator, extraction, entity_registry,
        │                               #  temporal_update, graph_plan_builder, graph_writer,
        │                               #  direct_authoring, embedding.py, rollback
        ├── retrieval/                   # One module per hybrid-retrieval phase — see
        │                                #  Data Models & Schema below
        ├── persistence/                   # Postgres store implementations
        ├── client/hydradb_http.py          # Custom HTTP/OpenCypher transport to the
        │                                    #  graph engine (not Bolt — see below)
        └── cloning/template_clone.py         # Per-playthrough memory space cloning
```

**Why HTTP instead of the standard Bolt protocol:** the graph engine's own README states plainly that the Neo4j Bolt driver is incompatible with HydraDB's handshake, so all graph reads/writes go through a custom JSON-over-HTTP OpenCypher transport instead — batched `UNWIND $rows` writes, causal-bookmark reads.

---

## System Architecture — C4 Level 1: Context

**Actors:**
- **Creator** — authors scenarios and publishes them.
- **Player** — discovers, plays (solo or turn-based multiplayer), shares playthroughs, rates/reviews scenarios.
- *(Creator and Player are roles on the same account, not separate user types.)*

**External systems:**
- **Gemini on Vertex AI** — narration, master-mode tool-calling, scene-image generation, cover-art generation, and the Studio AI co-writer chat. Reached via Express Mode (API key), not full ADC.
- **Vertex AI Lyria-002** — mood-based music generation.
- **Firebase Auth** — Google Sign-In token issuance. Both Core API and TRS validate Firebase tokens and additionally issue/verify their own app-level JWTs.
- **Replit** — the platform partner integration: creators either use a curated built-in minigame or host their own minigame on Replit and embed it via a sandboxed iframe at play time.

**Developed-but-externally-integrated system:**
- **HydraDB (the memory layer)** — provenance-preserving, bitemporal graph memory with hybrid vector/graph retrieval. Built as part of this project, but every other service reaches it purely over its HTTP API (`apps/memory-layer`), never through shared code or a shared database connection — architecturally equivalent in status to a genuinely external system. See [ADR-6](#adr-6-memory-layer-treated-as-an-external-system).

---

## System Architecture — C4 Level 2: Containers

**Frontend** — single web app, five in-app-chrome surfaces plus two "outside the app shell" surfaces:
- *In the standard app layout*: Landing, Discovery, Scenario detail, Studio (authoring), Profile.
- *Deliberately outside the standard chrome* (siblings of the main layout route, not children): Play, Setup, Spectate, Join, Login — the immersive gameplay surfaces render without shared header/nav.

**Backend services:**
- **Core API** — stateless CRUD, auth, publish, discovery, uploads, ratings/reviews. No streaming.
- **Turn Resolution Service** — the live gameplay loop: action validation, memory retrieval, Gemini orchestration (narration + tool-calling), streamed response, state persistence, batched memory writes, multiplayer turn-order and spectator fan-out.
- **Memory Layer (HydraDB)** — ingestion (authoring-time and runtime), 4-phase hybrid retrieval, template-to-playthrough cloning, rollback/save-points.

**Storage:**
- **PostgreSQL (`aidnd_db`)** — single durable store for scenarios, playthroughs, accounts, discovery metadata, turn history. Shared by Core API (owns migrations) and TRS (read/write, no migrations).
- **PostgreSQL (`context_memory`)** — the memory layer's own database (with pgvector), plus the vendored HydraDB graph engine for graph-native storage/traversal.
- **Google Cloud Storage** — cover images, scene images, map images, audio.

**External systems** *(unchanged from Level 1)*: Gemini/Vertex AI, Lyria, Firebase Auth, Replit.

---

## System Architecture — C4 Level 3: Components

**Turn Resolution Service** is the most complex container — see [The Turn Resolution Pipeline](#the-turn-resolution-pipeline) below for its full, real component breakdown; that section *is* its Level 3 view.

**Core API** is intentionally simple relative to TRS: standard stateless request/response handling for auth, scenario CRUD (both newbie freeform and master structured authoring writes across 21 tables), the publish flow (content-tag check + authoring-time memory ingestion), discovery (filtered/sorted Postgres queries), uploads (including the two AI-generation exceptions), and ratings/reviews. No AI orchestration in the live-play sense, no streaming — every endpoint is a conventional request-in, response-out call against Postgres, GCS, or the memory layer's authoring endpoints.

**Memory Layer** breaks into two component groups, both fronted by `engine.py`:
- **Ingestion** — orchestrator, extraction (LLM-based, for newbie-mode lore and runtime turn batches), entity resolution (3-tier: exact/alias match → embedding-based blocking → bounded LLM disambiguation), direct authoring (master-mode entities/facts, no LLM), graph-plan building and writing, rollback.
- **Retrieval** — a 4-phase hybrid pipeline: Phase 0 (temporal resolution, query rewriting), Phase 1 (vector cosine search + Postgres full-text search, seeded top-60), Phase 2 (real graph traversal via HydraDB's native `algo.MSpaths` multi-hop path algorithm, bitemporal filtering), Phase 3 (Reciprocal Rank Fusion across 4 channels, LLM reranking, a strict low-evidence Abstention Gate, optional LLM answer synthesis).

---

## Data Flow & Sequence

### Transport Model

Turn responses use **per-request SSE**, not a persistent long-lived connection: each player action is one `POST /v1/turn`, and the response streams back over that same connection until it closes. Session continuity comes from server-side Postgres state, not a kept-open channel.

**A real deviation from the original design:** the frontend does not use the browser's native `EventSource` anywhere in the codebase. `EventSource` cannot send an `Authorization` header, and this app's auth is JWT-bearer (not cookie-based), so `shared/lib/sse-client.ts` implements its own fetch-based streaming reader instead — `createGetSSEConnection` for the persistent multiplayer-notification/spectator channels, `createPostSSEConnection` for the one-shot POST-then-stream turn and assistant-chat channels. See [ADR-11](#adr-11-fetch-based-sse-transport-instead-of-native-eventsource).

For **multiplayer only**, a separate persistent SSE channel (`GET /v1/session/{id}/notifications`) exists solely for turn-order signaling — a `your_turn` event with no narration payload. Solo play never opens this channel.

### The Turn Resolution Pipeline

`pipeline.py` sequences these steps, in this order, for every `POST /v1/turn`. Steps marked *(master only)* are skipped entirely for newbie-mode scenarios.

| # | Step | What it actually does |
|---|---|---|
| 1 | `request_receiver` | Validates the playthrough is active, checks participant ownership and turn order, and — the one piece of gating logic here that has no RFC precedent — rejects the action outright if a minigame is pending and the submitted `action_kind` isn't `minigame_result` (or its `minigame_id`/`attempt_id` don't match the pending one). |
| 2 | `state_loader` | Loads `scenario_snapshot` + a deep copy of `Playthrough.state`. Never reads `Scenario` directly — always the per-playthrough snapshot (ADR-8). |
| 3 | `minigame_result_resolver` *(master only, when `action_kind == "minigame_result"`)* | Resolves the pending minigame's outcome into a state mutation + narrator instruction, clears the pending marker. |
| 4 | `condition_evaluator` *(master only)* | Evaluates active `scenario_conditions`, applies any Effect-C state mutations, before Gemini is called. |
| 5 | `context_retrieval` | Queries the memory layer for grounded facts. Degrades to an empty/abstained context on any failure — never blocks the turn. |
| 6 | `ai_orchestrator` | The only step permitted to call `gemini_client`. Newbie mode: single streamed call. Master mode: a native function-calling round-trip loop, validating each proposed tool call (`tool_handler` + `state_validator`, Pydantic, before it's applied — ADR-4) inside the same generation, capped at a configured max round-trips. |
| 7 | `map_state_sync` *(master only)* | Deterministic, non-AI: appends to `discovered_location_ids` when `current_location_id` changed. |
| 8 | `minigame_trigger_evaluator` *(master only, solo playthroughs only)* | Evaluates `scenario_minigames` in priority order against the final working state; on first match, stamps a pending-minigame marker and (for Replit-embed minigames) fires a best-effort, SSRF-guarded pre-warm ping to the embed URL. |
| 9 | `scene_image_generator` *(only when the request's `action_mode == "see"`)* | Generates a location-grounded scene image via Gemini. Failure is swallowed — never degrades the turn. |
| 10 | `state_writer` | Persists the `TurnLog` row and updated `Playthrough.state`, with optimistic-lock retry. Commits explicitly inside the SSE generator, since dependency-injection cleanup would otherwise run before the generator body does. |
| 11 | `end_condition_evaluator` *(master only, and skipped if a minigame trigger just fired this turn — minigame wins over a same-turn end-condition match)* | Checks `end_conditions` against the persisted final state; on match, marks the playthrough ended and notifies participants. |
| 12 | `memory_writer` | Best-effort batched ingest to the memory layer, every N turns (configurable). Failures are swallowed and logged, never fail the turn. |
| 13 | `turn_summary_builder` *(master only)* | Builds the `turn_summary` SSE payload (stat changes, inventory changes, dice rolls, active conditions) from this turn's tool calls. |
| 14 | `response_streamer` | Formats and streams every SSE event above as it becomes available; not a discrete pipeline stage but the terminal streaming layer wrapping the whole generator. |

**Two independent discriminators on every turn request**, easy to conflate but distinct:
- `action_kind: "narrative" | "minigame_result"` — whether this submission is a normal player action or a minigame outcome being reported back.
- `action_mode: "say" | "do" | "story" | "see"` — narration style; `"see"` is the one that additionally triggers scene-image generation.

**SSE events actually emitted** by `POST /v1/turn`: `narration` (streamed chunks), `mood` (scene mood tag), `scene_image` (only for `action_mode: "see"`, on success), `turn_summary` (master mode only), `minigame` (only when a trigger matched this turn), `playthrough_ended` (only on an end-condition match), `done` (terminal success), `degraded` (terminal failure-but-graceful, e.g. an optimistic-lock or state-write error, with a user-facing message).

### Multiplayer Delta

Steps 1–14 are identical for multiplayer; the differences:
- **Step 1 is not a no-op.** `request_receiver` verifies it's actually this participant's turn and rejects otherwise — a backend defense-in-depth check; the frontend is required to disable the action input for non-active participants too.
- **After step 10 (state write)**, if `participant_count > 1`, `notification_manager.notify_next_turn` pushes a `your_turn` event to whichever participant is expected to act next.
- **`minigame_trigger_evaluator` never fires in multiplayer** — minigames are solo-only by design (v1 scope).
- **Spectators** get the same event stream as the acting player, relayed live by `spectator_manager` (an in-process pub/sub `publish()` call from within the pipeline itself), independent of the notification channel.

Both `notification_manager` and `spectator_manager` are **in-process, single-container pub/sub** — a documented, deliberate scope limit, not multi-instance safe. See [ADR-13](#adr-13-in-process-pub-sub-for-spectator--multiplayer-notification-fan-out).

### Minigame Flow

1. On a matching turn, `minigame_trigger_evaluator` stamps `_pending_minigame` (an internal, non-schema key inside `Playthrough.state`) and the `minigame` SSE event carries the client-safe config (never the server-only outcome-mutation fields — `win_mutation`, `lose_mutation`, `tiered_outcomes`, `timeout_mutation`, and `narrator_instruction_template` all stay server-side).
2. The frontend renders a full-screen overlay entirely outside the AI narration loop — either the built-in canvas game (`shared/components/minigames/DodgeMinigame/`) or a sandboxed Replit iframe (`ReplitEmbed/`), which reports its outcome back via `postMessage`.
3. The result is submitted as the *next* turn, with `action_kind: "minigame_result"` and a matching `minigame_id`/`attempt_id` — re-entering the exact same pipeline, resolved by `minigame_result_resolver` before Gemini is called, then narrated normally.

No new `Playthrough.status` value, no new Gemini tools, and no separate endpoint were introduced for this — the entire feature rides the existing `POST /v1/turn` contract via one discriminator field (ADR-10).

### Scene Image Flow

Scene images are not automatic on every turn — they're generated only when the player explicitly chooses the `"see"` action mode, keeping AI image-generation cost and latency off the default narration path. Generation happens after the narration loop completes but before persistence, and a generation failure never fails or degrades the turn — the `scene_image` event is simply omitted.

---

## Data Models & Schema

`aidnd_db` (Core API + TRS), 21 tables, defined in `apps/core-api/app/db/models/`. All primary keys are `gen_random_uuid()` UUIDs unless noted.

```
User / auth
  users
    user_id, display_name, auth_provider_id (unique), token_version,
    current_refresh_jti, bio, avatar_url, banner_url, created_at

Core scenario
  scenarios
    scenario_id, creator_id → users, title, logline, mode ("newbie"|"master"),
    world_data (jsonb), status ("draft"|"publishing"|"published"|"publish_failed"|"archived"),
    genre_tags (text[], GIN indexed), complexity_tier, player_count_support,
    estimated_playtime, cover_image_url, content_tag, publish_error, published_at,
    play_count, rating_avg, narrator_persona, setup_schema (jsonb),
    state_schema (jsonb), end_conditions (jsonb — legacy inline copy; the
    authoritative, queryable end conditions live in their own table below),
    checkpoints (jsonb), rules (jsonb), current_version, opening_scene,
    narration_font, action_chips (text[]), setup_archetypes (jsonb),
    created_at, updated_at

Master-mode authoring
  entities
    entity_id, scenario_id → scenarios, entity_type, canonical_name, aliases (text[]),
    description, obtainable, attributes_schema (jsonb), narrator_instruction,
    is_player, timestamps
  facts
    fact_id, scenario_id → scenarios, subject_entity_id → entities, predicate,
    object_entity_id → entities (nullable) XOR object_literal (nullable) — exactly
    one of the two is set, enforced by a CHECK constraint, valid_from, when_active
    (jsonb), hidden, superseded_fact_id → facts (self-referential), metadata (jsonb),
    created_at
  scenario_conditions
    condition_id, scenario_id → scenarios, label, condition_expression (jsonb),
    condition_version, narrator_instruction, metadata (jsonb),
    state_mutation (jsonb — Effect C: pre-turn mutation applied when true), created_at
  rule_invariants
    invariant_id, scenario_id → scenarios, label, invariant_expression (jsonb),
    applies_to, narrator_text, created_at
  end_conditions
    end_condition_id, scenario_id → scenarios, condition_expression (jsonb),
    outcome_tag ("win"|"lose"), outcome_title, outcome_text, is_secret,
    priority (indexed with scenario_id — first-match-wins evaluation order),
    created_at
  scenario_entity_types
    scenario_entity_type_id, scenario_id → scenarios, type_key, display_label,
    attributes_schema (jsonb), unique(scenario_id, type_key), timestamps
  scenario_minigames
    minigame_id, scenario_id → scenarios, label, minigame_type,
    trigger_condition_expression (jsonb), priority, outcome_mode,
    win_mutation / lose_mutation / timeout_mutation (jsonb, nullable),
    tiered_outcomes (jsonb), narrator_instruction_template, dodge_config (jsonb),
    replit_embed_url, timestamps

Maps
  scenario_maps
    map_id, scenario_id → scenarios, name, image_url, display_order, timestamps
  map_pins
    pin_id, map_id → scenario_maps, scenario_id → scenarios, entity_id → entities,
    x, y, is_start_location (unique partial index — one start location per
    scenario), created_at
  map_connections
    connection_id, scenario_id → scenarios, entity_id_a / entity_id_b → entities
    (CHECK entity_id_a < entity_id_b — always a sorted pair; unique per scenario),
    label, created_at

Music
  scenario_music
    scenario_music_id, scenario_id → scenarios, mood (6 fixed values: peaceful,
    mystery, tension, combat, melancholy, triumph), source ("upload"|"generated"|
    "default"), track_url, generation_prompt, key, bpm, duration_seconds,
    unique(scenario_id, mood), timestamps
  music_generation_jobs
    job_id, scenario_id → scenarios, creator_id → users, mood, status ("pending"|
    "running"|"succeeded"|"failed"), prompt, preview_url, key, bpm,
    duration_seconds, error_message, timestamps
    — persisted, not in-memory, because Core API is stateless/multi-instance
  music_generation_log
    log_id, scenario_id → scenarios, creator_id → users, created_at
    — append-only; generation quota is COUNT(*) over this table, not a mutable
    counter, specifically to avoid a race condition on concurrent requests

Playthrough / session
  playthroughs
    playthrough_id, scenario_id → scenarios, created_by → users, state (jsonb),
    checkpoint, turn_count, status ("active"|"completed"|"abandoned"),
    scenario_version, scenario_snapshot (jsonb — see ADR-8), ended_outcome_tag
    ("win"|"lose", nullable), ended_outcome_title, ended_outcome_text, is_playtest,
    timestamps
  participants
    participant_id, playthrough_id → playthroughs, user_id → users,
    role ("owner"|"joined"), turn_order_position,
    unique(playthrough_id, user_id) and unique(playthrough_id, turn_order_position),
    joined_at
  turn_logs
    turn_id, playthrough_id → playthroughs, turn_number, participant_id →
    participants (nullable), action_text, narration_text, tool_calls (jsonb),
    image_url, location_id, scene_image_prompt, unique(playthrough_id, turn_number),
    created_at
  playthrough_shares
    share_id, share_token (unique, indexed), playthrough_id → playthroughs,
    mode ("spectate"|"join"), created_at

Bookmarks / reviews
  bookmarks
    bookmark_id, user_id → users, scenario_id → scenarios,
    unique(user_id, scenario_id), created_at
  scenario_reviews
    review_id, scenario_id → scenarios, user_id → users, rating (1–5, CHECK),
    comment, unique(user_id, scenario_id), created_at
```

**Entity relationships are not a separate concept** — they're modeled as facts with relational predicates (e.g. `member_of`, `allied_with`), same as the original design intended.

### `context_memory` (memory layer's own database)

Separate database, separate migration history (14 migrations). Key tables: `evidence_chunks` (immutable raw text + content hash), `graph_id_registry` (logical key → HydraDB graph-node ID), `ingestion_jobs` (per-chunk pipeline state machine), `memory_embeddings` (versioned pgvector rows, untyped dimension — currently 768-dim via `text-embedding-005`), `extraction_attempts` / `extracted_memory_candidates` / `rejected_extraction_candidates` (extraction audit trail), `graph_write_manifests` (idempotent write log, dedupe key), `fact_search_index` (Postgres full-text mirror for keyword scoring), `journal_steps` (append-only LLM call journal), `save_points` (rollback cutoffs), `pre_authored_fact_metadata` (`checkpoint`, `when_active`, `visible_to_participant_id`, `hidden` for direct-authored/template facts — needed because graph node properties are scalar-only), `scenario_template_checkpoints`, `ingestion_batches` / `ingestion_batch_chunks` (durable batch tracking, survives restart), `external_fact_ids` (maps a caller-assigned ID to the internal graph ID, so `superseded_fact_id` can resolve from Core API's/TRS's own IDs).

The graph engine itself stores `Session`, `Turn`, `Fact`, `Entity`, `Alias` nodes and `HAS_TURN`, `EXTRACTED_FROM`, `ABOUT`, `STATED_BY`, `SUPERSEDES`, `HAS_ALIAS`, `RELATES_TO` edges — this is where the multi-hop graph traversal in retrieval Phase 2 actually runs.

---

## Scenario & Memory Ingestion

This was an open design gap in the original RFC ("the very first turn's context retrieval finds nothing, and nothing decided how lore gets into memory in the first place"). It is now fully implemented, with two distinct, real ingestion paths:

**1. Authoring-time ingestion — runs once per scenario, at publish** (`publish_service.py` → `memory_client.ingest_scenario_template()` → memory layer's `POST /v1/memory/template/ingest`):
- **Master mode — direct write, no LLM extraction.** Entities and facts the creator already specified precisely map close to 1:1 onto the memory layer's Entity/Fact schema and are written directly — running them through an LLM extractor would risk the LLM reinterpreting something the creator specified exactly, contradicting master mode's core trust guarantee.
- **Newbie mode — LLM extraction.** Freeform lore text is processed by the same extractor used for runtime ingestion, into structured entities and facts.

Output either way: a scenario-scoped **template memory space**.

**2. Runtime ingestion — batched during active play** (`memory_writer` step → memory layer's `POST /v1/memory/ingest`, every N turns, configurable — not a fixed count baked into the design, unlike the original RFC's placeholder "roughly every five turns"). Captures new facts and events as they emerge during a specific playthrough.

**Ingest-once-clone-many:** when a player starts a playthrough, Core API's `playthrough_service.py` calls `memory_client.clone_template_memory_space()` (memory layer's `POST /v1/memory/playthrough/{id}/init`), cloning the scenario's template into a fresh, isolated playthrough-scoped memory space before the player reaches the play surface — avoiding re-running LLM extraction per playthrough (ADR-7).

**Known, documented gap:** direct-authored/cloned facts (the master-mode and template-clone path above) are not currently projected into the memory layer's retrieval indexes (embedding + full-text) — they exist in the graph but are invisible to retrieval Phase 1 seeding until this is fixed. This is called out explicitly in the memory layer's own README as a current limitation, not something this document is glossing over.

---

## API Specifications

All endpoints require an auth token except where noted (share-token-gated spectator/join routes, and a couple of explicitly public discovery/health endpoints).

### Core API Endpoints

| Router | Endpoints |
|---|---|
| `auth.py` (`/v1/auth`) | `POST /token` (exchange Firebase token) · `POST /refresh` (rotate, cookie-based) · `POST /logout` |
| `scenarios.py` (`/v1/scenarios`) | `POST /` · `GET /` (discovery/list — filters: `genre_tags`, `complexity_tier`, `player_count_support`, `sort`, `mine`/`saved`/`played`) · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` · `POST /{id}/publish` · `POST /{id}/playtest` · `POST /{id}/duplicate` · `POST /{id}/bookmark` · `GET`/`POST /{id}/reviews` · `GET /{id}/playthroughs` |
| `entities.py` | Full CRUD under `/v1/scenarios/{id}/entities`, plus `POST /{entity_id}/type-change-preview` |
| `facts.py` | Full CRUD under `/v1/scenarios/{id}/facts` |
| `conditions.py` | Full CRUD under `/v1/scenarios/{id}/conditions` |
| `invariants.py` | Full CRUD under `/v1/scenarios/{id}/invariants` |
| `end_conditions.py` | Full CRUD under `/v1/scenarios/{id}/end_conditions`, plus `POST /reorder` (priority order) |
| `scenario_entity_types.py` | Create/list/update/delete under `/v1/scenarios/{id}/entity-types` |
| `maps.py` | Full CRUD for maps, pins, and connections under `/v1/scenarios/{id}/maps*` and `/map-connections` |
| `minigames.py` | Full CRUD under `/v1/scenarios/{id}/minigames`, plus `POST /reorder` |
| `scenario_music.py` | `GET /v1/scenarios/{id}/music` · `POST /{mood}/upload` · `POST /{mood}/default` · `POST /generate` (202) · `GET /jobs/{job_id}` · `POST /jobs/{job_id}/confirm` · `DELETE /jobs/{job_id}` · `GET /quota` |
| `music_defaults.py` | `GET /v1/music/defaults` — public, the 6 built-in default tracks by mood |
| `playthroughs.py` (`/v1/playthroughs`) | `POST /` · `POST /join` · `PATCH /{id}/character` · `GET /{id}` · `POST /{id}/abandon` · `GET /{id}/turns` |
| `share.py` | `POST /v1/playthroughs/{id}/share` |
| `logs.py` | `POST /v1/logs` — client-side log ingestion batch (202) |
| `uploads.py` (`/v1/uploads`) | `POST /scenario-cover-image` · `POST /avatar` · `POST /banner` · `POST /scenario-map-image` · `POST /scenario-audio` · `POST /generate-cover-image` (AI-generated) |
| `users.py` (`/v1/users`) | `GET`/`PATCH /me` · `GET /me/playthroughs` · `GET /{id}` (public profile) · `GET /{id}/reviews` |

### Turn Resolution Service Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/turn` | Submit a player action; opens the connection that streams the response (see [The Turn Resolution Pipeline](#the-turn-resolution-pipeline) for the full event list). |
| `GET` | `/v1/session/{playthrough_id}/spectate` | Share-token gated, no auth token required — live SSE relay for spectators. |
| `GET` | `/v1/session/{playthrough_id}/notifications` | JWT-authed, participant-scoped — multiplayer turn-order signal (`your_turn`, `playthrough_ended`). |
| `POST` | `/v1/studio/assistant` | Studio AI co-writer chat — a second, independent AI surface from the gameplay narrator, also SSE-streamed. |
| `GET` | `/health` | Liveness. |

### Memory Layer (internal) Endpoints

Not customer/browser-facing — called only by Core API's and TRS's respective `memory_client.py` files.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/memory/template/ingest` | Authoring-time ingestion at publish (Core API). |
| `POST` | `/v1/memory/playthrough/{id}/init` | Clone a scenario template into a fresh playthrough-scoped memory space (Core API). |
| `POST` | `/v1/memory/query` | Structured, ranked fact retrieval for a turn — accepts a game-state snapshot so `when_active` conditions can be evaluated during retrieval (TRS). |
| `POST` | `/v1/memory/ingest` | Batched turn ingestion (TRS), async — returns a `batch_id`. |
| `GET` | `/v1/memory/batch/{batch_id}/status` / `POST /retry` | Poll or retry a batch. |
| `POST` | `/v1/memory/search` | Free-text hybrid retrieval with LLM-synthesized prose answer (used by the memory layer's own chat/demo surfaces, not by the product's gameplay path). |
| `POST` | `/v1/memory/{context_id}/save-point`, `POST /v1/memory/rollback/{save_id}` | Rollback support — not currently called by product code. |
| `GET` | `/v1/memory/stream` | SSE stream of live graph writes, for the memory layer's own visualization UI. Auth-gated and scoped to a required `context_id`/`playthrough_id` query param (fixed from an earlier, broader-scoped version — see [Known Limitations](#known-limitations--deferred-work)). |
| `GET` | `/v1/health` | Liveness — pings both Postgres and the HydraDB graph engine; always returns HTTP 200, caller must inspect the body for `ok`/`degraded`. |

---

## Cross-Cutting Concerns

### Latency & Performance

Turn resolution involves memory retrieval, one or more Gemini calls, optional tool-call round-trips, and a Postgres write — real, variable time, mitigated by streaming (perceived latency is time-to-first-token, not time-to-complete-response). Configured timeouts: Gemini calls, 30s (`gemini_timeout_seconds`), with up to 2 retries via `tenacity`, retrying only on classified-transient errors (timeout, server error, or a 429). Memory-layer calls have their own per-operation timeouts (query, ingest, template-ingest, and clone each configured separately — clone and template-ingest run longer, since they can trigger LLM extraction and are less latency-sensitive than an in-turn query).

### Authentication & Authorization

Firebase Auth (Google Sign-In) issues the initial identity token. Both Core API and TRS then issue their **own** short-lived JWT access tokens plus a longer-lived refresh token (rotated on use, tracked via `current_refresh_jti` on `users` to detect reuse), rather than passing the Firebase token through directly on every request. A development-only header bypass (`X-Dev-User-Id`) exists, gated by `environment != "production"`.

Authorization rules, matching the real schema:
- **Scenarios** — draft scenarios readable/editable by their creator only; published scenarios are publicly readable.
- **Playthroughs** — readable by participants and valid share-token holders only.
- **Share tokens** — unguessable, validated against `playthrough_shares` on every request; `spectate` mode grants read-only turn-history and live-stream access, `join` mode additionally allows creating a `Participant` row.
- **Reviews** — one review per user per scenario (`unique(user_id, scenario_id)` on `scenario_reviews`), enforced at the database level, not just application logic.
- **Turn submission** — TRS validates the submitting participant is the active turn-holder before processing; the frontend also disables the action input client-side, but the backend check is authoritative.

### Error Handling & Degradation

**Gemini failure mid-turn:** retried (see Latency above); if retries are exhausted, the turn ends with a `degraded` SSE event carrying a user-facing message — `Playthrough.state` and `TurnLog` are not written, so the player can resubmit cleanly.

**Postgres write failure after narration has streamed:** `state_writer` retries with optimistic-lock handling; narration has already reached the player regardless, so a failure here degrades gracefully rather than silently corrupting the session.

**Memory batch failure:** swallowed and logged — gameplay is never blocked by it. `Postgres.turn_logs` remains the durable source of truth; memory staleness is always recoverable on the next successful batch.

**Scene image / minigame pre-warm failure:** both are explicitly best-effort and swallowed — they never affect turn success.

### Content Safety

Unchanged from the original design: creators self-declare a content tag at publish, validated by a lightweight check. There is still no runtime content-moderation layer during active play — the narrator's behavioral constraints come entirely from the scenario's `narrator_persona` system prompt. This remains an acknowledged, not accidental, gap.

### Data Consistency

Postgres (`aidnd_db`) is the single source of truth for all product state. The memory layer is eventually consistent relative to it, bounded by the configured batch interval — playthrough continuity never depends on memory being current. `Playthrough.state` is always Pydantic-validated before write (ADR-4); an invalid tool-call mutation is rejected before it reaches Postgres, and the narrator recovers within the same generation.

---

## Architecture Decision Records (ADRs)

### ADR-1: Core API and Turn Resolution Service as two separate services

**Decision:** Split by request profile — Core API for simple CRUD/discovery, TRS for the complex, stateful, streaming gameplay loop. **Confirmed as-built**: the two remain cleanly separate, with TRS holding its own read-only mirror of the shared ORM models rather than importing Core API's.

### ADR-2: SSE over WebSocket

**Decision:** Server-Sent Events for both the per-request narration stream and the multiplayer notification channel — multiplayer's turn-based nature never needs WebSocket's bidirectional capability. **Confirmed as-built, with one refinement**: the actual transport is not the browser's native `EventSource` (see [ADR-11](#adr-11-fetch-based-sse-transport-instead-of-native-eventsource)).

### ADR-3: PostgreSQL as single primary store

**Decision:** Postgres as sole primary store, `jsonb` for schema-flexible content. **Confirmed as-built**, and extended: the memory layer independently made the same call for its own domain (`context_memory`, with pgvector added for embeddings) rather than introducing a separate vector database into the product's core storage.

### ADR-4: Validate-before-apply for AI tool-call state mutations

**Decision:** Pydantic-validate every proposed tool-call mutation before applying it; invalid mutations are rejected and returned to Gemini as a failure result within the same generation. **Confirmed as-built** — this is `state_validator.py`, called from inside `ai_orchestrator.py`'s tool-calling loop (not a separate top-level pipeline step, a detail the original RFC's step list didn't capture).

### ADR-5: Batched memory writes — not per-turn, not per-tool-call

**Decision:** Batch memory writes on a configurable turn interval rather than writing per-turn or per-tool-call. **Confirmed as-built** — the interval is a real config value (`memory_batch_turn_interval`), not hardcoded to five as the original placeholder suggested.

### ADR-6: Memory layer treated as an external system

**Decision:** Model the memory layer as a peer external system at C4 Level 1, not folded into the product's own containers, even though — unlike the original RFC's assumption that it was a wholly separate pre-existing product ("mem1") — it was actually built as part of this project. **Updated rationale**: the architectural boundary is preserved anyway, because every integration point is a stable HTTP contract (`apps/*/integrations/memory_client.py`), which keeps the product's architecture decoupled from the memory layer's internal implementation regardless of who built it.

### ADR-7: Ingest-once-clone-many for scenario memory template

**Decision:** Ingest once per scenario at publish; clone into a fresh space per playthrough. **Confirmed as-built** — `POST /v1/memory/playthrough/{id}/init`, called from `playthrough_service.py`.

### ADR-8: Scenario versioning via `scenario_snapshot`, not a version table

**Decision:** Snapshot scenario content onto `Playthrough.scenario_snapshot` at creation time rather than a separate version table; TRS reads only per-playthrough data. **Confirmed as-built** — `state_loader.py` never queries `scenarios` directly.

### ADR-9: `when_active` on facts and active conditions, instead of trigger-writes-to-memory

**Decision:** Conditionally-true facts carry a `when_active` expression evaluated at retrieval time; persistent behaviors are handled by `scenario_conditions`, evaluated by TRS every turn and injected directly as narrator context. **Confirmed as-built.**

### ADR-10: Minigames as an interstitial handoff, not a new pause/resume state machine

**Decision:** No new `Playthrough.status`, no new endpoint — a minigame trigger rides the existing turn pipeline via one `action_kind` discriminator (`"narrative"` vs `"minigame_result"`). **Confirmed as-built, with real specifics the original design didn't have yet**: `minigame_trigger_evaluator.py` is solo-only and priority-ordered against `scenario_minigames`; a matched trigger explicitly suppresses `end_condition_evaluator` on the same turn ("minigame wins"); result submission is validated against both `minigame_id` and `attempt_id` to reject a stale overlay resolving a newer encounter; Replit-embed minigames get a best-effort, SSRF-guarded pre-warm ping (https-only, hostname-allowlisted, resolved-IP public-only check) before the client even opens the iframe.

### ADR-11: Fetch-based SSE transport instead of native EventSource

**Context:** The browser's native `EventSource` API cannot attach custom headers, and this app's auth is JWT-bearer, carried in an `Authorization` header — not a cookie `EventSource` could ride along automatically.

**Decision:** `shared/lib/sse-client.ts` implements its own fetch-based SSE reader (`createGetSSEConnection` for persistent GET channels, `createPostSSEConnection` for one-shot POST-then-stream channels), and it is — by explicit in-code convention — the only file besides `shared/hooks/useSSE.ts` allowed to know a streamed connection exists. `grep "new EventSource"` across the frontend returns zero hits.

**Consequences:** More code than reaching for the browser primitive, but auth stays consistent with every other request in the app (same bearer-token pattern, same interceptor logic mirrored manually since SSE requests bypass axios entirely). `play.store.ts` and the Studio assistant-chat hook call `createPostSSEConnection` directly rather than going through `useSSE`, because they need to trigger/retry a stream from outside a React component's lifecycle (e.g. a "retry last turn" store action).

### ADR-12: Vertex AI accessed via Express Mode API key everywhere

**Context:** Every AI integration in the system (TRS's narration/tool-calling and scene-image clients, Core API's cover-art and music clients, the memory layer's embedding client) needs to call a Vertex AI model.

**Decision:** All of them use the same pattern — `genai.Client(vertexai=True, api_key=...)`, Vertex AI **Express Mode**, not full ADC/service-account-based Vertex auth.

**Consequences:** Simpler to provision (one API key secret per service, no per-service IAM role wiring for model access specifically), but the API key must genuinely be a Vertex AI Express Mode key with access to every specific model in use (`gemini-3.5-flash-lite`, `gemini-3.1-flash-image`, Lyria-002, `text-embedding-005`) — a real, previously-hit source of confusing failures when a key or model access doesn't line up (e.g. Imagen access was unavailable on this project, which is why image generation goes through `generate_content`'s `inline_data` extraction instead of the dedicated Imagen API).

### ADR-13: In-process pub/sub for spectator & multiplayer notification fan-out

**Context:** Spectators and the next-turn multiplayer participant both need a live push signal when a turn completes.

**Decision:** `session/spectator_manager.py` and `session/notification_manager.py` are plain in-process `dict`-backed pub/sub (`playthrough_id → list[Queue]`), not backed by Redis or any cross-instance broker.

**Consequences:** Explicitly documented in-code as scoped to this stack's single-container Cloud Run deployment — it would silently stop working correctly (a spectator connected to one instance would never see events published from another) if TRS were ever scaled to multiple concurrent instances. Both are best-effort/no-op if the target has no open connection; the frontend does not depend solely on push for correctness. Flagged in [Known Limitations](#known-limitations--deferred-work), not something to scale past without fixing first.

### ADR-14: Storage client abstracts GCS vs local disk by environment

**Context:** Uploaded/generated media (cover images, scene images, map images, audio) needs somewhere durable to live in production, but requiring real GCS credentials for every local dev run is friction with no benefit.

**Decision:** A single `storage_client.py` (one per service that needs it) branches on `environment`: GCS in production, local disk (served via a mounted static-files path) otherwise — callers never know or care which backend is active.

**Consequences:** One code path to test either way. The trade-off is environment-based, not feature-based — if `GCS_BUCKET_NAME` is ever left unset in a production deployment by mistake, storage silently falls back to local disk, which is ephemeral per Cloud Run instance and would produce broken URLs after any instance restart. Worth an explicit startup check if this ever bites in practice.

---

## Known Limitations & Deferred Work

Real, current gaps — not aspirational "open items" from a pre-build design, but things actually true of the system today:

- **No CI/CD.** `.github/workflows/` does not exist in the repository. Every deploy is a manual `gcloud builds submit` + `gcloud run deploy` sequence, run by hand.
- **Memory-layer retrieval gap.** Direct-authored and template-cloned facts are not yet projected into the memory layer's retrieval indexes (embedding + full-text) — they exist in the graph but won't surface via Phase 1 seeding until this is fixed. Documented in the memory layer's own README, not a hidden bug.
- **In-process SSE fan-out is single-instance only.** See [ADR-13](#adr-13-in-process-pub-sub-for-spectator--multiplayer-notification-fan-out) — would need a shared broker before TRS could safely run more than one Cloud Run instance concurrently.
- **No runtime content moderation during active play.** Only publish-time, creator-declared content tagging exists; the narrator's behavior is bounded only by its system prompt.
- **Playthrough forking is undecided and unbuilt.** The `playthrough_shares` schema would accommodate it, but the clone/branch mechanics and their memory-layer implications are not designed.
- **A few dead files remain in the codebase**, worth cleaning up: `apps/core-api/app/routers/ratings.py` (empty, unregistered — reviews/ratings actually live on `scenarios.py` and `users.py`) and `apps/turn-resolution-service/app/session/turn_counter.py` (empty, unreferenced — turn-order logic actually lives in `app/turn/turn_order.py`).
- **HydraDB's own harness capabilities are pre-production**, per its own README: journal payloads lack a production redaction/retention policy, and its Gemini environment/test migration is incomplete. (Its previously-flagged unauthenticated `/v1/memory/stream` issue has since been fixed — the route now sits behind the same API-key dependency as the rest of the router and requires a scoping `context_id`/`playthrough_id`; the README's warning text on this specific point is itself now slightly stale.)
- **HydraDB's graph engine runs on a bare GCE VM**, reachable over HTTPS protected only by a bearer token — no VPC connector. A deliberate speed-over-hardening trade-off, flagged for revisit before any real production traffic.
