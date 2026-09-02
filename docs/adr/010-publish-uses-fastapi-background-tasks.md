# ADR-10: Scenario publish uses in-process FastAPI `BackgroundTasks`, not a task queue

**Status:** Accepted (hackathon scope) — revisit post-hackathon.

## Context

`POST /v1/scenarios/{id}/publish` must run two real-latency steps — a content-tag check and authoring-time memory-layer ingestion (LLM extraction for newbie-mode scenarios) — without blocking the request. The endpoint returns `202 Accepted` immediately and the client polls `GET /v1/scenarios/{id}` for completion (see `docs/specs/scenario-publish-flow.spec.md`).

Core API's stack today (`apps/core-api/requirements.txt`) has no task-queue infrastructure: no Celery, no Redis, no arq. Adding one is a real infra decision (a broker to run and operate, new deployment surface on Cloud Run) that wasn't warranted just to unblock this endpoint at hackathon scale.

## Decision

Run the publish job with FastAPI's built-in `BackgroundTasks`, scheduled from the router after the synchronous "flip to `publishing`" phase (`PublishService.start_publish`) completes. The background phase (`PublishService.run_publish_job`) opens its own DB session via an injectable `get_session_factory` dependency (`app/db/connection.py`) rather than reusing the request-scoped session, since the latter closes around the response lifecycle.

No new dependency, no new deployable, no new operational surface — the job runs in the same process and worker that handled the request.

## A sharp edge this surfaced

`BackgroundTasks` in this FastAPI version run **before** a `yield`-based dependency's post-yield cleanup code — including `get_db_session`'s own `await session.commit()`. This is easy to assume is the other way around (cleanup-then-background), and getting it wrong causes a real deadlock, not just stale data: the request handler's own session flips the scenario to `status='publishing'` and holds that row's write lock until *its* session commits, but that commit was scheduled to run only after the background task — which immediately tries to `UPDATE` the same row and blocks waiting for a lock that will never release in time. Confirmed by direct reproduction (`asyncio`/`FastAPI` in isolation) and by watching `pg_stat_activity` catch the two backends stuck in exactly this cycle (`idle in transaction` blocking `active` / `Lock: transactionid`).

The fix: `PublishService.start_publish` commits its own session explicitly (`await self.scenario_repo.session.commit()`) before returning, rather than relying on `get_db_session`'s deferred end-of-request commit. Any future endpoint that both (a) mutates a row via a `yield`-dependency session and (b) schedules a `BackgroundTask` that touches the same row must do the same — commit explicitly before scheduling the task, don't assume dependency cleanup runs first.

## Consequences

- **Not durable across process restarts.** `BackgroundTasks` run in-memory, in the same worker process. If the Core API instance is killed or recycled (e.g. Cloud Run scaling the instance down) while a publish job is mid-flight, the task is lost silently and the scenario is left stuck in `status = 'publishing'` indefinitely, with no automatic recovery.
- **No reconciliation sweep exists.** This ADR deliberately does not add a startup job to detect and reset scenarios stuck in `publishing`. A creator who hits this has no self-service recovery path today beyond manual DB intervention.
- **Single-instance assumption.** Nothing here coordinates across multiple Core API instances; this is fine at hackathon scale (single instance) but would need rethinking before horizontal scaling.

## Required before this can be trusted past the hackathon

- **Move execution to a real task queue** (Celery + Redis, or arq + Redis, or Cloud Tasks/Cloud Run Jobs given the existing GCP deployment target) so publish jobs survive process restarts and can run on a separate worker pool from request handling.
- **Add a reconciliation/recovery mechanism** — either a startup sweep that resets scenarios stuck in `publishing` past some timeout back to a retryable state, or (once on a real queue) rely on the queue's own retry/dead-letter semantics.
- Re-evaluate the `get_session_factory` seam introduced for this ADR — it exists specifically to let background work open its own DB session; a real task-queue worker would need the equivalent (its own session per job) regardless of the queue chosen, so this part of the design should carry forward.

## Alternatives considered

- **Celery/Redis/arq now:** rejected for this pass — adds a broker dependency and a new deployable to operate for a hackathon-scope feature; the ADR above documents this as required, not skipped.
- **`asyncio.create_task` instead of `BackgroundTasks`:** rejected — decouples the task from the request/response lifecycle for no benefit here, and `BackgroundTasks` is the more idiomatic FastAPI primitive for "run after the response is sent."
