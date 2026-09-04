# TRS Architecture — AI & Memory Integrations

This document details the external client modules in `apps/turn-resolution-service/app/integrations/`. In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md), Gemini and Memory Service communications are strictly isolated in these dedicated integration files.

---

## 1. Overview & Vendor Isolation

```mermaid
flowchart LR
    Orchestrator["app/turn/steps/ai_orchestrator.py"] -->|Calls generate_stream()| GeminiClient["app/integrations/gemini_client.py"]
    ContextStep["app/turn/steps/context_retrieval.py"] -->|Calls query_memory()| MemClient["app/integrations/memory_client.py"]
    WriterStep["app/turn/steps/memory_writer.py"] -->|Calls ingest_memory()| MemClient

    GeminiClient -->|google-genai SDK (Vertex AI Express Mode)| VertexAI[("Google Gemini 3.5 Flash Lite")]
    MemClient -->|HTTP JSON REST API| MemorySvc[("External Memory Graph Service")]
```

---

## 2. File Profiles

### `apps/turn-resolution-service/app/integrations/gemini_client.py`
- **Purpose & Layer:** Sole interface to Google Gemini on Vertex AI across the entire codebase.
- **Key Exports & Functions:**
  - `_get_client() -> genai.Client`: Lazy constructor initializing Vertex AI client (`vertexai=True, api_key=settings.gemini_api_key`) to ensure tests and CI run cleanly without requiring eager credentials at import time.
  - `_SAFETY_SETTINGS`: Configured to `BLOCK_ONLY_HIGH` across all 4 harm categories (`HATE_SPEECH`, `DANGEROUS_CONTENT`, `SEXUALLY_EXPLICIT`, `HARASSMENT`) to prevent false-positive blocks during dramatic dark-fantasy roleplay combat narration.
  - `generate_stream(contents, system_instruction, tools=None) -> AsyncIterator[types.GenerateContentResponse]`:
    - Wraps streaming execution with exponential backoff retries on HTTP 429 (Rate Limit).
    - Translates network or SDK exceptions into domain-specific `GeminiUnavailableError`.
    - Yields streaming content chunks with raw text and structured `function_call` objects.
- **Dependencies & Interactions:** Consumed by `ai_orchestrator.py` and `assistant_service.py`.
- **Architecture Rules & Invariants:**
  - **Hard Constraint**: The **only** file in the repository permitted to call Gemini.
  - **Logging Redaction**: Strictly logs call metadata (model name, latency, token count, error status). **Never logs prompts or generated narration text** (enforced by `docs/logging.md`).

### `apps/turn-resolution-service/app/integrations/memory_client.py`
- **Purpose & Layer:** Outbound HTTP client for long-term semantic fact retrieval and ingestion during the turn loop.
- **Key Exports & Functions:**
  - `query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse`: Fetches historical semantic facts relevant to the player's current action and active scenario.
  - `ingest_memory(request: MemoryIngestRequest) -> MemoryIngestResponse`: Submits newly generated narrative facts and state deltas to the graph memory layer.
- **Dependencies & Interactions:** Consumed by `context_retrieval.py` and `memory_writer.py`.
- **Architecture Rules & Invariants:**
  - Decoupled from graph storage internals; honors the Pydantic memory contract from `app/models/memory.py`.
