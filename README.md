<div align="center">

# wevr

### *weave your fate*

**An AI-native production studio for interactive fiction — creators author living, playable worlds; Gemini narrates them for audiences, turn by turn.**

[**Live Demo**](https://frontend-877199650658.us-central1.run.app/) · [**Demo Video**](#-demo-video) · [**Repository**](https://github.com/AryanSherigar/AI-DND) · Built for [Agentic Cinema: The Blockbuster Hackathon](https://agentic-cinema.devpost.com/)

</div>

<!-- TODO: hero screenshot/gif of Studio or Play here -->

---

## The Pitch

Every great interactive story needs a production crew: a writer, a set designer, a composer, a director who remembers every promise the story made three acts ago. Most solo creators don't have that crew. **wevr is that crew, run by AI.**

**Studio** is the production side — a creator writes the world, casts its characters and factions, generates cover art and an original score, and defines what winning and losing actually mean. **Play** is the release — an audience steps into that world and a Gemini-powered narrator runs it live, turn by turn, backed by a persistent memory layer so the story stays consistent across hours of play, generating a new scene image and a mood-matched soundtrack shift as it goes.

This isn't a chatbot wrapper. It's a full production pipeline: author once, and Gemini directs, scores, and illustrates the result for every audience that plays it.

## What is wevr

| Surface | Who it's for | What happens |
|---|---|---|
| **Studio** | Creators | Author a world: entities, factions, maps, lore, stakes (win/lose conditions), AI-generated cover art, an AI-composed score, and optional custom minigames. Publish when ready. |
| **Play** | Audiences | Discover published worlds, start a playthrough, and experience it as a turn-by-turn narrated story — spectatable and shareable. |

Every scenario is authored in one of two formats:

- **Newbie mode** — freeform lore; Gemini narrates with creative latitude.
- **Master mode** — fully structured state (stats, factions, entities, facts, invariants, win/lose conditions) that the AI narrator must respect via tool-calling — a *deterministic, multi-step agentic workflow*, not free-association.

## Key Features

### Production tools (Studio)
- **No-code world authoring** — entities, factions, facts, invariants, and end-conditions (win/lose/secret endings), each with a dedicated visual editor backed by real CRUD APIs (`apps/core-api/app/routers/{entities,facts,conditions,invariants,end_conditions}.py`).
- **AERO — an AI co-designer, not just a chatbot** — a built-in assistant (`apps/frontend/src/features/studio/components/AIChatSidebar`) that reads a scenario's live state (its actual entities, facts, conditions, and end-conditions) and proposes structured, reviewable actions — a new entity, a win condition, a tracked value — as inspectable cards a creator applies with one click, individually or all at once. It's a real agentic loop: propose → review → apply, not autocomplete.
- **AI-generated production assets** — per-scenario cover art, and original scenario music generated with **Google Lyria (`lyria-002`)** via Vertex AI (`apps/core-api/app/integrations/music_gen_client.py`), so a creator can score their own story without a composer.
- **Custom minigames, built and hosted on Replit** — a creator builds a minigame in the included [`replit-template/`](./replit-template) starter kit, hosts it on Replit, and wires it into their scenario through Studio's Minigames tab. At runtime, the game is embedded live in a sandboxed iframe and communicates results back over `postMessage` (`ready()` / `reportResult()`), matched exactly by the frontend's `ReplitEmbedMinigame` component and `useReplitHandshake` hook.

### The produced experience (Play)
- **AI Dungeon Master narration** — Google's **`google-genai`** SDK drives `gemini-3.5-flash-lite` as the narrator (`apps/turn-resolution-service/app/integrations/gemini_client.py`), streaming prose token-by-token over SSE, and validating every tool call against the world a creator actually built in Studio.
- **Persistent world memory** — a custom-built long-term memory layer (`apps/memory-layer`, "HydraDB"): PostgreSQL + pgvector alongside a graph store, bitemporal facts, multi-tier entity resolution, and hybrid retrieval, so a story stays consistent across long playthroughs instead of forgetting what happened five turns ago.
- **Live per-turn scene illustration** — `gemini-3.1-flash-image` generates a new image for the scene as each turn resolves (`scene_image_generator.py`), rendered inline in the story feed.
- **Adaptive score during play** — Gemini tags its own narration with a mood (`[MOOD: tension]`, etc.), which the frontend picks up over SSE and crossfades live between mood-matched tracks via Web Audio (`ambient-soundtrack.ts`) — the soundtrack literally follows the story.
- **Minigames as stakes** — a built-in PixiJS dodge minigame ("Ashfall Dodge") ships out of the box, and creator-built Replit minigames slot in the same way — both can be triggered mid-turn and feed their outcome straight back into the story's state.

> **Note for judges:** the Lyria music generation and Gemini image generation calls require live Vertex AI credentials/quota to actually produce output. Both fail gracefully without it (image generation returns `None` without breaking the turn; music generation raises a handled error) — the surrounding pipeline keeps working either way.

## Google Cloud & Partner Integration

Both required integrations are called at runtime, not just referenced in docs:

| Requirement | Where it's called | What it does |
|---|---|---|
| **Google Cloud (`google-genai`)** | `apps/turn-resolution-service/app/integrations/gemini_client.py`, called from the turn pipeline on every player turn | Narrates the story with `gemini-3.5-flash-lite`, tool-calling into Master mode's structured game state |
| **Google Cloud (`google-genai`)** | `apps/turn-resolution-service/app/integrations/image_gen_client.py`, called from `scene_image_generator.py` | Generates a scene image per turn with `gemini-3.1-flash-image` |
| **Google Cloud (Vertex AI)** | `apps/core-api/app/integrations/music_gen_client.py` | Generates original scenario scores with Lyria (`lyria-002`) |
| **Replit (partner track)** | [`replit-template/`](./replit-template) (`minigame-sdk.js`) ↔ `apps/frontend/src/shared/components/minigames/ReplitEmbed/ReplitEmbedMinigame.tsx` + `useReplitHandshake.ts` | Creators build and host custom minigames on Replit; wevr embeds them live in an iframe and exchanges results over `postMessage` at runtime |
| **Replit (hosting)** | Frontend deployment | The frontend is also deployed via Replit |

## Judging Criteria Alignment

- **Technological Implementation** — a real multi-service agentic pipeline (`pipeline.py`'s ordered turn steps: context retrieval → AI orchestration → tool-call validation → state write → memory write → minigame resolution → scene image generation), not a single prompt-response wrapper. Google's Gemini SDK and Replit's runtime embed are both invoked in production code paths, verified end-to-end from router to UI.
- **Design** — a complete product loop, not a tech demo: a creator can author, illustrate, score, and publish a world in Studio, and a stranger can discover, play, and spectate it in Play, with no manual steps in between.
- **Potential Impact** — lowers the floor for making interactive fiction. A solo creator gets a co-writer, illustrator, composer, and game master, instead of needing a team (or none of the above).
- **Quality of Idea** — reframes "AI Dungeon Master" from a chatbot novelty into a production pipeline with real stakes: structured win/lose conditions the AI must respect, a persistent memory layer that holds creators accountable to their own lore, a minigame system that lets outcomes hinge on more than just prose, and AERO, an AI co-designer that proposes rather than dictates — the creator stays the director.

## Architecture Overview

Four services:

| Service | Path | Responsibility |
|---|---|---|
| Frontend | `apps/frontend/` | React + Vite + TypeScript. Studio (authoring) and Play (discovery + gameplay) surfaces. |
| Core API | `apps/core-api/` | Python + FastAPI. Auth, scenario CRUD, Master mode data model, publish flow, discovery, playthroughs, ratings, image/music generation for authoring. Stateless, no AI narration, no streaming. |
| Turn Resolution Service | `apps/turn-resolution-service/` | Python + FastAPI. The only service that calls Gemini for narration and streams via SSE — validates the player's action, loads state, retrieves memory, calls Gemini, validates tool calls, resolves minigames, streams narration, persists state. |
| Memory Layer | `apps/memory-layer/` | A custom long-term memory engine ("HydraDB") backed by PostgreSQL + pgvector and a graph store, giving the narrator durable, queryable world knowledge across turns. |

For the full system design — C4 diagrams, ADRs, data models, and API specifications — see **[`ARCHITECTURE.md`](./ARCHITECTURE.md)**.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite, TypeScript, TanStack React Query, Zustand, PixiJS (minigames), Firebase Auth, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, structlog |
| AI | `google-genai` (Gemini narration + scene image generation), Google Lyria (`lyria-002`, scenario music) |
| Memory | PostgreSQL + pgvector, HydraDB (graph store) |
| Infra | Docker Compose (local), Google Cloud Run (deployed), Replit (frontend hosting + creator-hosted minigames) |

## Getting Started (Run Locally)

```bash
git clone https://github.com/AryanSherigar/AI-DND.git
cd AI-DND
cp .env.example .env   # fill in Gemini/Vertex AI credentials, Firebase config, etc.
docker compose up
```

This brings up the full stack — Postgres, the memory layer (Postgres + HydraDB), Core API, Turn Resolution Service, and the frontend — as defined in [`docker-compose.yml`](./docker-compose.yml). For hot-reload local development, use `docker-compose.dev.yml` instead. Per-service architecture and setup detail lives under `docs/arch/`.

## Project Structure

```
apps/
  frontend/                 # Studio + Play (React/Vite/TS)
  core-api/                 # Auth, scenario CRUD, Master mode data, publish flow
  turn-resolution-service/  # Gemini narration, SSE streaming, turn pipeline
  memory-layer/             # HydraDB long-term memory engine
replit-template/            # Starter kit for creators to build custom minigames on Replit
docs/                       # Architecture docs, ADRs, feature specs
music/                      # Mood-tagged ambient tracks for the adaptive soundtrack
```

## Known Limitations

- There is no pre-seeded demo scenario — judges (or anyone) need to author a scenario in Studio before there's a story to play. "The Hollow Cairn" referenced in some design docs is illustrative reference material, not real, loadable content.
- Lyria music generation and Gemini scene image generation require live Vertex AI credentials/quota to produce output; both degrade gracefully without it, but won't visibly demo without a working key.
- The memory layer (`apps/memory-layer`) documents its own known rough edges in its README — including an unauthenticated SSE debug stream and some direct-authored facts not yet indexed for retrieval — as it's an actively evolving component.
- CI/CD workflow files exist under `.github/workflows/` but are currently empty placeholders; deploys today are manual (`gcloud run deploy` / Cloud Build), not automated.

## License

License: **TBD** — see [`LICENSE`](./LICENSE) once added.

The vendored graph engine inside `apps/memory-layer` (HydraDB) is separately licensed **AGPL-3.0**. It runs as its own independent, networked Docker service (accessed over HTTP, not linked into wevr's own code), so it is not part of — and does not govern the license of — the rest of this repository.

## Team

- **Aryan Sherigar**
- **Parth Dambhare**

## Demo Video

<!-- TODO: embed 3-minute demo video link (YouTube/Vimeo) here before submitting -->

---

<div align="center">

[Live Demo](https://frontend-877199650658.us-central1.run.app/) · [Repository](https://github.com/AryanSherigar/AI-DND) · [Architecture Deep Dive](./ARCHITECTURE.md)

</div>
