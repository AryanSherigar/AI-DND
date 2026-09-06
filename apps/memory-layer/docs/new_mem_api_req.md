
# Memory Layer API Contract — Handoff for mem1

## 1. Purpose & audience

This document specifies the API contract between the AI-DND product (Core API + Turn Resolution Service, "TRS") and the external memory layer — referred to as **mem1** in this product's own README. It's written for whoever builds/extends mem1 to know exactly what endpoints to expose, with what request/response shapes, and why.

Every claim below is sourced from one of three inputs, and each item says which:

1. **This codebase's contract** — Pydantic models and mock clients already implemented in `apps/turn-resolution-service/` and `apps/core-api/`. Currently the only fully concrete artifact; every call to mem1 today is a mock.
2. **mem1's real tech stack** — supplied by the product owner (noted as "old information, but mem1 is similar to this"): a dual-engine system — PostgreSQL 16 + pgvector (raw text, sha256-hashed chunks, embeddings, full-text search) plus **HydraDB** (an OpenCypher graph store) for `Session`/`Turn`/`Fact`/`Entity`/`Alias` nodes and `HAS_TURN`/`EXTRACTED_FROM`/`ABOUT`/`STATED_BY`/`SUPERSEDES`/`MERGED_INTO` edges. Bitemporal tracking distinguishes Knowledge Time (`observed_at`, `superseded_at`) from World-Validity Time (`valid_from`, `valid_to`). 3-tier entity resolution (exact match → semantic blocking → bounded LLM disambiguation). 4-phase hybrid retrieval (temporal resolution → vector + BM25 → graph expansion → composite scoring with an abstention gate). A bundled live web UI (chat + real-time force-directed graph pane over SSE) that this product does not use. Provider-neutral LLM backend (default Groq).
3. **A separate "Memory Layer RFC"** — also supplied by the product owner, explicitly **not** mem1's real API, but "designed from scratch, independent of any existing implementation, for later comparison against mem1" — the document mem1 was built to resemble. It has its own C4-style architecture, data model, and a concrete API surface section.

**Key finding: this codebase's contract was clearly derived from source (3), not invented independently.** The path names (`POST /v1/memory/query`, `POST /v1/memory/ingest`, `GET /v1/memory/batch/{id}/status`) and the exact `BatchStatus` field set (`batch_id, status, facts_created, error, retryable`) match the RFC verbatim. This substantially de-risks the handoff: the per-turn query/ingest contract is already validated against the RFC target design, not just an internal guess.

The product's own README separately claims mem1's real, already-existing API is named `/v1/chat`, `/v1/memory/search`, `/v1/memory/ingest`, `/v1/memory/stream`. Given mem1's tech stack includes a bundled live web UI (chat interface + real-time graph pane), this almost certainly describes that **generic, UI-facing surface** — not a narrative-specific contract. That surface is very likely the wrong integration point for this product regardless of naming; the RFC-derived contract below is the target.

Items below are marked **Confirmed** (matches the RFC or verified working code), **Proposed** (a new path this document suggests, not sourced from anywhere), or **Open** (a genuine design decision, not yet made anywhere).

---

## 2. System context

- mem1 is a peer external system, called only through `app/integrations/memory_client.py` in each of the two services that need it (`apps/core-api/`, `apps/turn-resolution-service/`) — never from routers, other services, or the frontend directly.
- **The frontend has zero direct coupling to mem1.** Verified by repo-wide search: no file under `apps/frontend/src` references "memory" in any form. All memory-layer traffic is backend-only.
- The gameplay-time contract (query + runtime ingest) is confirmed against the RFC. The authoring-time contract (template ingest + playthrough clone) has no counterpart in the RFC at all — it's a product-specific extension. This asymmetry is why some sections below carry much higher confidence than others.

---

## 3. Data concepts

### Entity and Fact — the core graph primitives

This product models world knowledge as a subject–predicate–object triple store, stored internally in this product's own Postgres tables. **The fields below are specifically what actually crosses the wire to mem1** via the authoring-ingest payloads (`EntityIngestPayload`/`FactIngestPayload`, §4.7) — this product's internal DB tables carry a few additional fields (`Entity.obtainable`, `Entity.attributes_schema`, `Entity.narrator_instruction`, `Fact.metadata_`) that are **not** sent to mem1 and can be ignored for this contract.

- **Entity** (wire shape): `entity_id`, `entity_type` (character | location | item | faction | organization, or a scenario-defined custom type), `canonical_name`, `aliases: list[str]`, `description`.
- **Fact** (wire shape, current): `fact_id`, `subject_entity_id`, `predicate`, exactly one of `object_entity_id` or `object_literal`, `valid_from`, `when_active` (a conditional-visibility expression, evaluated against live game state — see §5, Gap B), `hidden` (author-marked secret, overridable per-playthrough via a `revealed_facts` convention — see below).

**Recommended addition: also send `superseded_fact_id`.** This product's own Postgres `Fact` table already has a `superseded_fact_id` self-referential column (validated by its own service layer — same scenario, no self-supersession), but it's currently **not included** in `FactIngestPayload` — pre-authored supersession is handled purely through `when_active` today. This document recommends adding it to the wire payload, as a complement to `when_active`, not a replacement:

- The common authoring case — "the King is dead, the Queen rules now" — is a simple linear replacement. mem1 already has native `SUPERSEDES` graph edges and bitemporal validity-window closing as core machinery for its own extraction pipeline; reusing that for pre-authored facts is likely cheaper at retrieval time and a simpler authoring primitive than requiring a `when_active` expression keyed off some proxy game-state flag.
- `when_active` remains necessary for facts that don't reduce to a simple A-replaces-B chain — e.g., a fact that becomes relevant via one of several different branching player choices, not tied to any single prior fact.
- **Precedence rule, if both are added to the same fact:** supersession should be authoritative over currency — a fact with a known successor should never be treated as current truth regardless of its own `when_active`. `when_active` remains the separate, orthogonal question of relevance/surfacing for facts that aren't superseded. This precedence rule doesn't exist anywhere today and needs to be agreed with the friend before both fields coexist on the same fact.
- This is a recommendation for this document to carry forward, not yet implemented in `FactIngestPayload`/`publish_service.py` — a follow-up code change, tracked separately from this document.

### Reconciling against mem1's real schema

mem1's bitemporal design (`observed_at`/`superseded_at` knowledge-time vs. `valid_from`/`valid_to` world-validity time) is **richer** than what this product's contract currently expects (`valid_from`/`valid_until` only, no separate knowledge-time fields). **Open item:** confirm mem1's exact real field names for the validity window — specifically whether it's `valid_until` or `valid_to` — before finalizing this product's `Fact` Pydantic model. This product likely only needs world-validity time (`valid_from`/`valid_to`) for "what's true now vs. then" narrative purposes; knowledge-time fields (`observed_at`/`superseded_at`) are probably not needed on the response, but confirm rather than assume.

### Visibility: `hidden`/`revealed_facts` vs. mem1's `FactVisibility`

This product's visibility mechanism is simple: a fact is `hidden: bool`, and a playthrough's `revealed_facts: list[fact_id]` (stored on `Playthrough.state`, a single JSONB blob) overrides visibility for that playthrough. **Verified: this is playthrough-wide, not per-participant** — every participant in a multiplayer playthrough sees the same `revealed_facts` list.

The Memory Layer RFC's own visibility model is richer: a `FactVisibility` table with three scope types (`all_participants`, `specific_participant`, `checkpoint_gated`), explicitly designed for multiplayer participants knowing different things. **This product has no mechanism for per-participant differential knowledge today**, even though `participant_id` is already part of every query request. Don't infer differential-visibility behavior from the presence of `participant_id` in the contract — it's there for attribution/future use, not because it's wired into visibility filtering today. Mapping the two visibility models onto each other is an open item for direct discussion, not resolved here.

---

## 4. Endpoints

### 4.1 `POST /v1/memory/query` — Confirmed

Per-turn retrieval. Called by TRS's `context_retrieval.py`, once per turn, **before** the Gemini call — on the blocking, player-facing path. Path and shape match the RFC's own API surface exactly. The RFC's retrieval pipeline is explicitly LLM-free (embedding lookup, vector + keyword search, graph expansion, scoring — no generative call), which is what makes its own stated 1-2 second latency target realistic.

**Request** (`MemoryQueryRequest`):

```
scenario_id: UUID
playthrough_id: UUID
participant_id: UUID
query_text: str
checkpoint: str              # a marker for current story progression, passed through as-is; not currently used for anything beyond that on this product's side
game_state: dict[str, Any]   # full current state tree, includes a `revealed_facts: list[str]` entry by convention
as_of_turn: int | None
```

**Response** (`MemoryQueryResponse`):

```
facts: list[Fact]            # fact_id, subject, predicate, object, valid_from, valid_until, confidence, hidden
abstained: bool
resolved_time_point: str | None
```

**Latency target:** 1-2 seconds, blocking, player-facing — matches the RFC's own stated target.

### 4.2 `POST /v1/memory/ingest` — Confirmed

Batched runtime writes. Called by TRS's `memory_writer.py`, roughly every 5 turns (`memory_batch_turn_interval`), off the blocking path. Path and async 202-response shape match the RFC exactly (its ADR-3, matching this product's own ADR-5 nearly word-for-word: batched rather than per-turn or per-tool-call, since most turns produce no durable new facts).

**Request** (`MemoryIngestRequest`):

```
scenario_id: UUID
playthrough_id: UUID
turns_batch: list[{turn_number: int, text: str, participant_id: UUID}]
recent_context_turns: list[same shape]   # currently always sent empty by this product — see note below
```

**Response** (`MemoryIngestResponse`): `{batch_id: UUID}`, `202 Accepted`.

**Idempotency note:** mem1's real design already does sha256 content-hashing on raw text chunks, which plausibly gives free deduplication if the same turn text is ever resent. Confirm this explicitly rather than assume it covers every resend scenario.

**Verified gap in this product's own implementation (disclosed for accuracy, not something mem1 needs to solve):** this product's README documents a "10-turn catch-up" behavior on ingest failure — a failed batch's turns get resent combined with the next batch, up to 10 turns total. This is **not actually implemented**: `memory_writer.py` unconditionally sends only the last 5 turns every time, tracks no failure state, and never calls the batch-status or retry endpoints below. A failed batch today is simply logged and dropped. Build `GET .../status` and `POST .../retry` to the contract shape regardless (below) — they're cheap, match the RFC, and this product will very likely start calling them correctly in the future — but know they're currently unexercised by any real caller.

### 4.3 `GET /v1/memory/batch/{batch_id}/status` — Confirmed

Poll an ingest batch's status. Path and shape lifted directly from the RFC's API surface.

**Response** (`BatchStatus`):

```
batch_id: UUID
status: "pending" | "succeeded" | "failed" | "partial"
facts_created: int
error: str | None
retryable: bool
```

### 4.4 `POST /v1/memory/batch/{batch_id}/retry` — Confirmed

Explicitly re-trigger a failed/partial batch. No request body. Response reuses `MemoryIngestResponse` (`{batch_id}`). Path matches the RFC's own "reliability decisions" section verbatim: retries are caller-driven, not silent/automatic on mem1's side — the calling game engine needs visibility into failures so it can eventually surface an honest, low-key in-fiction notice rather than silently losing facts.

### 4.5 `GET /v1/memory/entity/{entity_id}` — Required for launch

Fetch a specific entity's current known state. Not called by any code in this product today, but present in the RFC as a debugging and future-tool-calling hook. Cheap to add alongside the rest; requested for launch since it's already part of the target design.

### 4.6 `GET /v1/health` — Required for launch

Standard operational health check. Present in the RFC, absent from this product's current mock contract entirely. Required baseline regardless of anything else in this document.

### 4.7 Authoring-time template ingest — Proposed path, confirmed internal requirement

**Proposed path:** `POST /v1/memory/scenario/{scenario_id}/template`. Not sourced from the RFC or mem1's tech summary — those don't model an authoring-time bulk-ingest flow at all (see Gap A, §5). This path name is this document's proposal, open for the friend to accept, rename, or push back on.

Called once per scenario, by Core API's `publish_service.py`, when a creator publishes a scenario.

**Request** (`MemoryTemplateIngestRequest`) — populates **exactly one** of two mutually exclusive shapes depending on `mode`:

```
scenario_id: UUID
mode: "newbie" | "master"
world_data: dict[str, Any]              # newbie mode only
entities: list[EntityIngestPayload]     # master mode only
facts: list[FactIngestPayload]          # master mode only — see §3 for a recommended
                                         # addition (superseded_fact_id) not yet in this shape
```

**Response**: `{template_space_id: UUID}`.

**Confirmed requirement — two distinct internal code paths in mem1, not one uniform pipeline:**

- **Newbie mode:** `world_data` is freeform creator prose. Route it through mem1's normal extraction pipeline (LLM extraction → 3-tier entity resolution → write) — the same machinery used for runtime batch ingest.
- **Master mode:** `entities`/`facts` are already fully structured and disambiguated by the creator through a structured editor — `subject_entity_id`/`object_entity_id`/`predicate` are exact, real IDs, never fuzzy mentions needing resolution. This is a deliberate trust guarantee in this product ("the system will not reinterpret your world"). **mem1 must skip the extraction LLM and the 3-tier entity-resolution pipeline entirely** for this path and write the given Entity/Fact records directly — while still doing the mechanical work every fact needs regardless of origin: generating embeddings for vector search, and creating the corresponding graph nodes/edges.

**This direct-write bypass applies only to authoring-time template ingest, never to runtime batch ingest.** Turn narration text is always freeform prose in both modes (master-mode structured state mutations live in this product's own Postgres, never in mem1), so every runtime batch — regardless of scenario mode — always goes through full extraction. Don't assume master mode skips extraction everywhere.

**Critical finding — `template_space_id` is not tracked anywhere in this product.** The value returned by this endpoint is currently discarded by the calling code and never persisted. The clone endpoint below is only ever called with `scenario_id` + `playthrough_id` — never a `template_space_id`. Two direct consequences for mem1's implementation:

1. **Re-ingesting a scenario's template (on republish) must behave as an upsert keyed by `scenario_id`**, replacing/updating whatever template existed before — not accumulating a new, unreferenceable space on every republish, since nothing in this product can ever address an old `template_space_id` again once a newer one exists.
2. If mem1 wants to internally keep multiple historical template versions per scenario, that's fine — but the clone endpoint (below) must always resolve to the *latest* one given only `scenario_id`, since that's all it will ever receive.

### 4.8 Playthrough clone — Confirmed as a concept, mechanism recommended (see Gap A, §5)

**Path:** `POST /v1/memory/playthrough/{playthrough_id}/init` (this product's own README already names this exact path).

Called by Core API's `playthrough_service.py`, before the `Playthrough` database row is committed — the memory clone must succeed first.

**Request** (`MemoryTemplateCloneRequest`): `{scenario_id: UUID, playthrough_id: UUID}`.

**Response** (`MemoryTemplateCloneResponse`): `{playthrough_space_id: UUID}`.

**Reliability note:** unlike the per-turn query/ingest calls, this call is on a **hard-failure path today** — a failed clone blocks playthrough creation entirely (raised as an explicit error, not swallowed). Real uptime matters here, not best-effort.

---

## 5. Headline open design questions

These are genuine, previously-invisible gaps found by comparing this product's contract against both mem1's tech summary and the Memory Layer RFC — not naming mismatches, and not silently resolved here.

### Gap A — template/clone mechanism

Neither mem1's tech summary nor the Memory Layer RFC has any concept of a scenario-level "template" space distinct from a playthrough space — the RFC's tenancy model is a flat `scenario_id` + `playthrough_id` tag pair on every record, and its actor list explicitly excludes authoring-time flows as non-core. This entire mechanic is a product-specific extension that needs a real decision.

**Recommendation: explicit physical clone**, matching this product's current mock/README assumption (§4.8 above). `POST /v1/memory/playthrough/{id}/init` physically duplicates a scenario's template records into a new playthrough-tagged copy at playthrough creation. Every later query then filters by one exact `playthrough_id`, everywhere — no cross-store filter discipline required.

**Alternative considered and not recommended:** tag-based virtual composition — scenario-level facts tagged with a null/sentinel `playthrough_id`, unioned with playthrough-specific facts at query time, with no physical copy at all. This was set aside because it requires the widened tenancy filter (`playthrough_id ∈ {this playthrough, template-sentinel}`) to be applied correctly across *every* one of mem1's storage layers (the Postgres row filter, the vector-DB metadata filter, and the HydraDB graph traversal scope) on every single query, forever — miss it in even one layer and a scenario-level fact silently disappears from some retrieval paths. That ongoing correctness burden outweighs the one-time cost of a physical clone. Worth revisiting only if clone latency or storage cost becomes a real problem at scale.

**Remaining open sub-question:** whether the clone itself should be a full deep copy or a cheap internal reference — this product's own README leaves that explicitly undecided. Now that the mechanism (clone, not tag-union) is settled, this is purely mem1's internal performance decision.

### Gap B — `when_active` evaluation

This product's README (ADR-9) assumes mem1 evaluates a `when_active` boolean expression against an arbitrary `game_state` snapshot sent with every query. Neither mem1's tech summary nor the RFC's actual visibility mechanism (`FactVisibility`'s three fixed scope types) supports evaluating arbitrary state-tree expressions — this is real uncovered scope, not a naming issue.

**Two verified facts materially lower the risk here:**

1. **`when_active` has no authoring UI today.** This product's fact-creation form only captures subject/predicate/object/hidden — there is no control for `when_active` or `valid_from` anywhere in it, even though the underlying API types already declare both fields. No fact created through the current UI will ever carry a `when_active` value. This is real scope to design correctly, but nothing currently depends on it working.
2. **A real, tested, reusable expression grammar already exists in this product** for an analogous purpose (`ScenarioCondition.condition_expression`, evaluated locally, never sent to mem1): a chained field/operator/value tree — e.g. `{"field": "player.health", "op": "<=", "value": 5, "AND": {...}}` — supporting `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `contains`, `matches`, with `AND`/`OR`/`NOT` nesting and cross-field references. It has a matching authoring UI already built and shipped for that other use case.

**Recommendation: `when_active` should adopt this exact same grammar**, and this product should evaluate it **client-side, after retrieval**, reusing its own existing, already-tested evaluator function rather than writing new evaluation logic — consistent with how `hidden`/`revealed_facts` filtering already works today (also client-side, after retrieval). Under this recommendation, **mem1 only needs to return `when_active`-tagged facts** (filtered by whatever native visibility scoping it has) — it does not need to build a generic expression evaluator itself. This is a meaningfully smaller ask than the original ADR-9 framing implied.

**Trade-off, stated honestly:** this means mem1 returns some facts that get discarded client-side (whose `when_active` condition isn't currently met) — more payload per query than a fully server-side-filtered design. Acceptable given the RFC's retrieval pipeline is already fast and mechanical, and per-query payloads are small.

---

## 6. Non-functional requirements

- **Latency:** 1-2 seconds for `/v1/memory/query`, blocking and player-facing. Ingest and the authoring-time endpoints are not on the per-turn critical path (though clone *is* on the playthrough-creation critical path — see reliability note below).
- **Reliability differs sharply by endpoint — verified directly against code:**
  - `/v1/memory/playthrough/{id}/init` (clone) and `/v1/memory/scenario/{id}/template` (authoring ingest) are on a **hard-failure path today**: a failed clone blocks playthrough creation outright; a failed template ingest blocks a scenario from successfully publishing (visibly, with an error state — not a silent partial success). mem1 needs real uptime for these two calls.
  - `/v1/memory/ingest` (runtime batch) is correctly best-effort today — failures are caught and only logged, never surfaced to the player.
  - Consistency model: mem1 is expected to be eventually consistent relative to this product's own Postgres, which remains the single source of truth. Staleness bounded by the ~5-turn batch cadence is acceptable; playthrough continuity should never depend on mem1 being perfectly current.
- **Auth: completely unspecified.** No API key, token, or auth header scheme for calling mem1 appears anywhere — not in this product's code, its README, mem1's tech summary, or the Memory Layer RFC. This blocks building a real (non-mocked) client and needs a decision before integration work starts.
- **Config:** a `MEMORY_SERVICE_URL` environment variable placeholder already exists in this product's env files but is not yet read by any config — wiring it up is this product's own follow-up work once a real base URL exists.
- mem1's provider-neutral LLM backend (Groq default, OpenAI-compatible) is purely internal to mem1 — no action needed on this product's side.

---

## 7. Consolidated checklist for the handoff conversation

1. **Gap A** — confirm the explicit-clone recommendation (§5), or discuss the tag-based alternative if mem1's storage internals make it materially cheaper than assumed here.
2. **Gap B** — confirm client-side `when_active` evaluation (§5); if accepted, mem1's only obligation is returning `when_active`-tagged facts, not evaluating them.
3. Exact real field names for `Fact`'s validity window (`valid_until` vs. `valid_to`) and whether knowledge-time fields (`observed_at`/`superseded_at`) should be exposed to this product at all.
4. How mem1's native visibility model maps onto this product's simpler `hidden`/`revealed_facts` convention.
5. **Auth mechanism** — currently undefined anywhere; needs a decision before any real (non-mocked) integration.
6. Confirm the two new endpoints (`GET /v1/memory/entity/{id}`, `GET /v1/health`) are being built.
7. `template_space_id` must be resolved internally by mem1, keyed by `scenario_id` — this product will never round-trip it (§4.7).
8. Republish of a scenario's template must be an upsert, not an accumulation of orphaned template spaces (§4.7).
9. `participant_id` is present in every query for attribution/future use — this product does not currently do per-participant differential visibility, despite the RFC's `FactVisibility` model supporting it.
10. Minor internal inconsistency, disclosed for completeness rather than something mem1 needs to act on: this product's own `Fact` response model has a `hidden: bool` field on the Turn Resolution Service side but not on the Core API side (identical model name, different fields). Currently low-impact — Core API's own `query_memory` is defined but never actually called by any of its routers or services today.
11. **Recommended change, not yet implemented:** add `superseded_fact_id` to `FactIngestPayload` alongside `when_active` (§3) — complementary mechanisms, not either/or. Requires agreeing the precedence rule (supersession beats currency) with the friend before both fields can safely coexist on the same fact. Tracked as a follow-up code change on this product's side, separate from this document.
