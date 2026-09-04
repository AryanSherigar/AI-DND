# Turn Resolution Service — Architecture & System Overview

This document provides the high-level architecture overview for `apps/turn-resolution-service` (TRS), the stateful execution engine and AI narrator for the AI-DND platform built with Python 3.11, FastAPI, SQLAlchemy, and Google Vertex AI Gemini.

---

## 1. System Role & Responsibilities

TRS is the only service in the AI-DND platform that:
1. **Communicates with Gemini**: All LLM calls and streaming generation are isolated inside TRS.
2. **Streams Server-Sent Events (SSE)**: Streams narration tokens in real-time directly to client browsers.
3. **Executes the Master Mode Turn Resolution Pipeline**: Evaluates dynamic conditions, executes AI tool calls, enforces invariants, persists state mutations, and synchronizes knowledge facts to the Memory Layer.
4. **Manages Real-time Sessions**: Handles live spectator broadcasting, turn counter tracking, and participant notifications.

```mermaid
flowchart TD
    Client["Frontend Play Surface (Browser)"] -->|POST /v1/turn (SSE Request)| TurnRouter["app/routers/turn.py"]
    TurnRouter --> Pipeline["app/turn/pipeline.py<br/>(Master Turn Pipeline)"]

    subgraph TurnExecution["12-Step Turn Pipeline Execution"]
        Pipeline --> Step1["1. request_receiver"]
        Step1 --> Step2["2. state_loader"]
        Step2 --> Step3["3. condition_evaluator (Master Mode)"]
        Step3 --> Step4["4. context_retrieval (Memory Layer)"]
        Step4 --> Step5["5. ai_orchestrator (Gemini)"]
        Step5 --> Step6["6. tool_handler (Tool Calls)"]
        Step6 --> Step7["7. state_validator (Invariants)"]
        Step7 --> Step8["8. map_state_sync (Spatial)"]
        Step8 --> Step9["9. state_writer (Cloud SQL)"]
        Step9 --> Step10["10. end_condition_evaluator"]
        Step10 --> Step11["11. memory_writer (Fact Sync)"]
        Step11 --> Step12["12. response_streamer (SSE [DONE])"]
    end

    Step4 -.->|Query| MemorySvc[("Memory Layer Client")]
    Step5 -.->|Stream| Gemini[("Vertex AI / Gemini")]
    Step9 -.->|Write| DB[("PostgreSQL")]
    Step11 -.->|Ingest| MemorySvc
```

---

## 2. Strict Architectural Boundaries

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **Sole Caller of Gemini**: Only `app/integrations/gemini_client.py` touches the Gemini SDK. No other service or file may invoke Gemini.
- **Immediate Streaming**: SSE responses must stream immediately. Never buffer the full Gemini narration before sending chunks to the client. A buffered SSE response is treated as a critical defect.
- **Step Order Isolation**: `pipeline.py` is the **only file** that knows step order. Steps in `app/turn/steps/` never call each other directly.
- **Scenario Immutability**: TRS is strictly read-only on `Scenario` entities, with one single exception: incrementing `Scenario.play_count` when a playthrough reaches turn 10.
- **Mirrored Database Schema**: TRS maintains its own lightweight SQLAlchemy models in `app/db/models/` without relationship joins, querying Postgres directly for minimal turn latency.

---

## 3. Directory Layout

```
apps/turn-resolution-service/
├── Dockerfile                   # Python 3.11 container manifest
├── pyproject.toml               # Service config and dependencies
├── requirements.txt             # Service dependencies (FastAPI, sse-starlette, google-genai)
├── app/
│   ├── main.py                  # FastAPI entrypoint, lifespan, CORS, and routers
│   ├── config.py                # Hyperparameters, timeouts, Gemini keys
│   ├── logging_config.py        # Structured JSON GCP logger & field redaction
│   ├── db/                      # Mirrored database models, connection engine
│   ├── exceptions/              # Turn and session domain exceptions
│   ├── integrations/            # Gemini Vertex AI client and Memory client
│   ├── middleware/              # Auth, RequestContext, and Error Handlers
│   ├── models/                  # Pydantic schemas (game_state, tool_call, turn, assistant)
│   ├── repositories/            # Data access repositories (participant, playthrough, scenario, etc.)
│   ├── routers/                 # Endpoints (/turn, /session, /assistant)
│   ├── services/                # Assistant service logic
│   ├── session/                 # Spectator fan-out, notifications, turn counters
│   └── turn/                    # Pipeline orchestrator, 12 steps, expression evaluators
└── tests/                       # Respx mock tests, pipeline integration tests
```

---

## 4. Testing Architecture

- **`tests/turn/test_pipeline.py` & `test_pipeline_end_conditions.py`**: Full turn pipeline integration tests executing against real test database fixtures.
- **`tests/integrations/test_gemini_client.py`**: Mock transport tests verifying streaming token chunking, retry backoff, and error translation.
- **`tests/integrations/test_memory_client.py`**: Validates prompt context retrieval and fact ingestion requests.
- **`tests/session/`**: Validates spectator SSE fan-out queues and notification delivery.
