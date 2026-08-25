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
3. **Discover**: other players browse or filter the feed by tag, genre, complexity, player count, and playtime, and see social signals (plays, likes, ratings).
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

A small number of decisions are deliberately deferred past Context & Goals and must be resolved before or during later sections of this RFC:

- **Invalid tool-call / state-validation strategy**: what happens when the AI narrator attempts an invalid state mutation in a structured (master-mode) scenario. To be decided during Component-level design, in discussion with the team.
- **Runtime content guardrails during play**, as distinct from publish-time creator self-tagging.
- **Final decision on playthrough forking** (build vs. defer), pending session architecture.
- **Partner track selection**, deferred until the architecture is drafted partner-agnostically and reviewed with the team.

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


