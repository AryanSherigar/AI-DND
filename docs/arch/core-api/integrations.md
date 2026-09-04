# Core API Architecture — External Integrations

This document details the external network clients located in `apps/core-api/app/integrations/`. In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md), direct third-party service communication is strictly isolated inside dedicated integration client files.

---

## 1. Overview & Isolation Rules

- **Strict Boundary**: External service SDKs (Google Cloud Storage, Memory Service HTTP) are never imported or instantiated inside routers, services, or models.
- **Async Thread Execution**: Blocking third-party SDK calls (e.g. synchronous Google Cloud Storage blob uploads) must execute in thread workers via `asyncio.run_in_executor` to avoid blocking the FastAPI event loop.

---

## 2. Integration Client Profiles

### `apps/core-api/app/integrations/memory_client.py`
- **Purpose & Layer:** Outbound HTTP client for the external graph memory service, implementing the authoring and template cloning contracts.
- **Key Operations & Functions:**
  - `ingest_template(request: MemoryTemplateIngestRequest) -> MemoryTemplateIngestResponse`: Ingests scenario world facts and entity attributes upon scenario publication. Supports:
    - *Newbie Mode*: Freeform `world_data` string subjected to asynchronous graph extraction.
    - *Master Mode*: Strongly structured `entities` and `facts` arrays directly written into the knowledge graph without reinterpretation.
  - `clone_template_to_space(request: MemoryTemplateCloneRequest) -> MemoryTemplateCloneResponse`: Clones an immutable published scenario's memory graph into a dedicated, writable memory space for an active playthrough instance.
  - `query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse`: Semantic fact retrieval interface.
- **Dependencies & Interactions:** Consumed by `PublishService` (phase 2 background task) and `PlaythroughService`.
- **Architecture Rules & Invariants:** Honors the memory API schema contract from `app/models/memory.py`.

### `apps/core-api/app/integrations/storage_client.py`
- **Purpose & Layer:** Dedicated client for Google Cloud Storage asset persistence (scenario cover art, custom map tiles).
- **Key Operations & Functions:**
  - `_get_client() -> storage.Client`: Singleton initializer for the GCS SDK client.
  - `_upload_blob_sync(content, content_type, object_key) -> str`: Synchronous worker uploading bytes to `settings.gcs_bucket_name` and making the blob public-read.
  - `upload_image(content: bytes, content_type: str, object_key: str) -> str`: Async facade executing `_upload_blob_sync` in `loop.run_in_executor(None, ...)`.
- **Dependencies & Interactions:** Consumed by `UploadService`.
- **Architecture Rules & Invariants:**
  - Zero direct Google Cloud Storage imports outside of this file.
  - Handles network failures by wrapping vendor exceptions in domain-specific `UploadFailedError`.
