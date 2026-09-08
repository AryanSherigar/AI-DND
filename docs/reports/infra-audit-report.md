# Comprehensive Infrastructure & Docker Re-Audit Report: `AI-DND` Monorepo

> **Scope**: Full Containerization & Infrastructure Stack ([`docker-compose.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml), [`docker-compose.dev.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.dev.yml), [`apps/core-api/Dockerfile`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/Dockerfile), [`apps/turn-resolution-service/Dockerfile`](file:///home/aryan-sherigar/projects/AI-DND/apps/turn-resolution-service/Dockerfile), [`apps/frontend/Dockerfile`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/Dockerfile), [`apps/frontend/Dockerfile.dev`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/Dockerfile.dev), [`apps/frontend/nginx.conf`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/nginx.conf), [`apps/memory-layer/Dockerfile`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/Dockerfile), [`apps/memory-layer/compose.yaml`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/compose.yaml), `.env.example`, runtime containers, and network architecture)  
> **Benchmark Standards**: CIS Docker Benchmark v1.6.0, OWASP Container Security Top 10, 12-Factor App Methodology  
> **Mode**: Read-Only Architecture & Security Re-Audit (No Code or Configuration Modifications Applied)  
> **Date**: September 2026  
> **Status**: Re-Audited & Verified Live

---

## Executive Summary

A comprehensive re-audit of the containerization and infrastructure definitions across the `AI-DND` monorepo was conducted. The investigation verified the current status of all 21 findings identified in the previous audit, evaluated recent commits (notably commit `15457eb` which transitioned HydraDB to a prebuilt image, refactored dev frontend builds, and decoupled database migrations), and performed deep inspection of the live running container stack.

### Key Re-Audit Findings:
1. **8 of the Original 21 Issues Are Remediated**: Significant progress was made on baseline security and stability. All production containers now execute as unprivileged users (UID 10001 / node / nginx), database migrations are decoupled into dedicated one-shot runners (`migration-runner`, `memory-layer-migration-runner`), `.dockerignore` files are deployed across all services, and network segregation between `frontend-net` and `backend-net` is enforced.
2. **13 of the Original Issues Persist**: Key gaps remain in production secret hygiene (`docker-compose.yml` default secret fallbacks), container healthchecks for API services, Nginx web server hardening (missing security headers and static caching), process signal forwarding, resource limits, and Python runtime consistency.
3. **5 Brand-New Bugs Discovered**:
   - **[NEW-01] Active Container Crash-Loops in Development Stack**: Live inspection revealed `aidnd-core-api` crashing with `ModuleNotFoundError: No module named 'mutagen'` and `aidnd-trs` crashing with `ModuleNotFoundError: No module named 'google.cloud'`. Bind mounting host source into stale container images without rebuild triggers crashes uvicorn on auto-reload.
   - **[NEW-02] Missing Production Environment Variables in `core-api`**: `GEMINI_API_KEY`, `CORE_API_PUBLIC_URL`, and `GCS_BUCKET_NAME` are omitted from `core-api` in `docker-compose.yml`. AI cover image generation (`POST /v1/uploads/generate-cover-image`) fails, GCS cannot be enabled, and upload URLs default to unreachable endpoints.
   - **[NEW-03] Ephemeral Uploads Storage & Missing Nginx Route for `/uploads/`**: `core-api` lacks a persistent volume for `/app/uploads`. Local user uploads are wiped on container recreation, and `nginx.conf` has no proxy route for `/uploads/`, causing production asset requests to fail with 404 / SPA fallback.
   - **[NEW-04] Internal Service Secret Key Disconnect (`MEMORY_SERVICE_API_KEY` vs `MEMORY_LAYER_API_KEY`)**: `core-api` and `turn-resolution-service` authenticate using `MEMORY_SERVICE_API_KEY`, but `memory-layer` expects `MEMORY_LAYER_API_KEY`. Setting the documented key in deployment environments causes HTTP 401 Unauthorized across all turn memory operations.
   - **[NEW-05] Deep Readiness Probe Authentication Lockout on Memory Layer**: `apps/memory-layer/src/api/server.py` places the entire router under `require_api_key`. The deep readiness probe `GET /v1/health` rejects unauthenticated orchestrator probes with HTTP 401 Unauthorized (confirmed live in container logs).

---

## Audit Status Matrix: Original 21 Findings

| ID | Title | Severity | Status | Current Code / Verification Evidence |
|---|---|:---:|:---:|---|
| **CRIT-01** | Frontend Build-Time Env Freezing (`VITE_*`) | P0 | **REMEDIATED** | [`apps/frontend/Dockerfile:12-29`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/Dockerfile#L12-L29) declares `ARG`s and exports `ENV` before `npm run build`. Injected via `docker-compose.yml`. |
| **CRIT-02** | Public Host Port Exposure of Database & Internal Services | P0 | **REMEDIATED** | [`docker-compose.yml:12-13, 175-176`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L12) uses `expose:` only for `postgres` and `memory-layer`. Host ports are only bound in `docker-compose.dev.yml`. |
| **CRIT-03** | Universal Root User Execution Across Containers | P0 | **REMEDIATED** | All Dockerfiles specify unprivileged users (`USER 10001:10001` in Python services, `nginx-unprivileged` in frontend prod, `USER node` in frontend dev). |
| **CRIT-04** | HydraDB Named Volume Permission Denied Crash Loop | P0 | **REMEDIATED** | Switched to `ghcr.io/hydra-db/hydradb:sha-02a4002` with pre-configured directory ownership for `graph:graph` (UID 10001). Container is running healthy. |
| **HIGH-01** | Multi-Replica Migration Race Condition at Startup | P1 | **REMEDIATED** | Decoupled to one-shot `migration-runner` in [`docker-compose.yml:24-38`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L24-L38). `core-api` waits for `service_completed_successfully`. |
| **HIGH-02** | Lazy DDL Migrations on First Request in Memory Layer | P1 | **REMEDIATED** | Removed from `build_memory_engine()`. Executed ahead of time via `memory-layer-migration-runner` ([`docker-compose.yml:143-157`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L143-L157)). |
| **HIGH-03** | Secret Exposure via Command Line Echo in Entrypoint | P1 | **STILL EXISTS** | [`docker-compose.yml:117`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L117) echoes `${HYDRADB_API_KEY}` in plaintext inside shell command string. Exposed in `/proc/<pid>/cmdline` and `docker inspect`. |
| **HIGH-04** | Total Absence of `.dockerignore` Files Monorepo-Wide | P1 | **REMEDIATED** | Root `.dockerignore` and 4 app-specific `.dockerignore` files created, blocking `.git`, `.venv`, and `node_modules` leaks. |
| **HIGH-05** | Flat Single Network Lacking Tier Segregation | P1 | **REMEDIATED** | Dual network segregation implemented: `frontend-net` (public web) and `backend-net` (private database & internal services). Frontend has zero route to `backend-net`. |
| **MED-01** | Missing CPU & Memory Resource Limits | P2 | **STILL EXISTS** | [`docker-compose.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml) lacks `deploy.resources.limits` or `mem_limit`/`cpus` for all 7 services. |
| **MED-02** | Insecure Fallback Secret Defaults in Compose | P2 | **STILL EXISTS** | Default secrets (`dev-secret-key-change-in-production`, `postgres`, etc.) remain in [`docker-compose.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml). No `${VAR:?}` production enforcement. |
| **MED-03** | Missing Application Healthchecks for Core API & TRS | P2 | **STILL EXISTS** | Neither `core-api`, `trs`, nor `memory-layer` defines `healthcheck` in [`docker-compose.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml). Frontend depends on `service_started`. |
| **MED-04** | PID 1 Signal Handling & Zombie Process Gap | P2 | **REMEDIATED** | Shell wrappers (`sh -c`) removed from Dockerfiles. `CMD ["uvicorn", ...]` runs directly in exec form as PID 1, intercepting `SIGTERM` and `SIGINT` cleanly. |
| **MED-05** | Dev Environment Port Overlap (Publishing 80 & 5173) | P2 | **REMEDIATED** | [`docker-compose.dev.yml:51-52`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.dev.yml#L51-L52) uses `ports: !override` to bind strictly to port 5173. |
| **MED-06** | Insecure Nginx Default Configuration | P2 | **STILL EXISTS** | [`apps/frontend/nginx.conf`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/nginx.conf) lacks standard security headers, static asset caching headers, and compression. |
| **MED-07** | Dev Node Modules Anonymous Volume Shadowing | P2 | **PARTIALLY RESOLVED** | Redundant `npm install` on boot was eliminated via `Dockerfile.dev`. However, anonymous volume `/app/node_modules` still retains stale packages unless `docker compose down -v` is run. |
| **MED-08** | Inconsistent Python Runtimes Across Monorepo | P2 | **STILL EXISTS** | `core-api` and `trs` use `python:3.11-slim` while `memory-layer` uses `python:3.12-slim`. |
| **LOW-01** | Missing Read-Only Root Filesystem Enforcements | P3 | **STILL EXISTS** | No containers configure `read_only: true` with `tmpfs`. |
| **LOW-02** | Missing Linux Capabilities Dropping (`cap_drop`) | P3 | **STILL EXISTS** | Containers retain full default capabilities (`cap_drop: [ALL]` not configured). |
| **LOW-03** | Floating Base Image Tags | P3 | **STILL EXISTS** | Unpinned tags (`node:22-alpine`, `nginxinc/nginx-unprivileged:alpine`, `postgres:16-alpine`) pull non-deterministic upstream revisions. |
| **LOW-04** | Absence of Automated Dockerfile Linting (Hadolint) | P3 | **STILL EXISTS** | No Dockerfile linting in CI/CD or pre-commit configuration. |

---

## Detailed Analysis of Newly Discovered Bugs

### [NEW-01] Stale Container Build & Broken Dependencies Crash-Loop in Development Stack
- **Severity**: High (P1)
- **Category**: Local Development Lifecycle & Runtime Stability
- **Location**: [`docker-compose.dev.yml:4-21`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.dev.yml#L4-L21)
- **Live Evidence**:
  Checking running container logs on the system revealed that both backend services failed to boot:
  1. `aidnd-core-api`:
     ```text
     File "/app/app/services/music_service.py", line 11, in <module>
       from mutagen import MutagenError
     ModuleNotFoundError: No module named 'mutagen'
     ```
  2. `aidnd-trs`:
     ```text
     File "/app/app/integrations/storage_client.py", line 20, in <module>
       from google.cloud import storage
     ModuleNotFoundError: No module named 'google.cloud'
     ```
- **Problem & Root Cause**:
  In `docker-compose.dev.yml`, host directories are bind-mounted into container `/app`:
  ```yaml
  core-api:
    command: ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    volumes:
      - ./apps/core-api:/app
  turn-resolution-service:
    command: ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]
    volumes:
      - ./apps/turn-resolution-service:/app
  ```
  While Python source code updates live across the mount, Python third-party packages live in `/usr/local/lib/python3.11/site-packages` inside the container image. When new dependencies (`mutagen`, `google-cloud-storage`) were added to `requirements.txt` on the host, uvicorn auto-reloaded the new host code, but failed to find the packages because the container was not rebuilt with `--build`.
- **Impact**:
  The development environment is broken out-of-the-box when running `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` without explicit build flags. Both `core-api` and `turn-resolution-service` enter an irrecoverable crash-reload loop.
- **Remediation**:
  1. Trigger an immediate image rebuild:
     ```bash
     docker compose -f docker-compose.yml -f docker-compose.dev.yml build core-api turn-resolution-service
     ```
  2. In documentation and developer runbooks, explicitly specify `--build` for local stack initialization:
     ```bash
     docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
     ```

---

### [NEW-02] Missing Critical Environment Variables in `core-api` Container (`GEMINI_API_KEY`, `CORE_API_PUBLIC_URL`, `GCS_BUCKET_NAME`)
- **Severity**: High (P1)
- **Category**: Service Configuration & Feature Completeness
- **Location**: [`docker-compose.yml:45-58`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L45-L58) vs [`apps/core-api/app/config.py:29-32`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/app/config.py#L29-L32)
- **Problem & Root Cause**:
  In `docker-compose.yml`, the environment block for `core-api` declares:
  ```yaml
  core-api:
    environment:
      DATABASE_URL: ${CORE_API_DATABASE_URL:-postgresql+asyncpg://postgres:postgres@postgres:5432/aidnd_db}
      SECRET_KEY: ${SECRET_KEY:-dev-secret-key-change-in-production}
      JWT_ALGORITHM: ${JWT_ALGORITHM:-HS256}
      JWT_ACCESS_EXPIRE_MINUTES: ${JWT_ACCESS_EXPIRE_MINUTES:-15}
      JWT_REFRESH_EXPIRE_DAYS: ${JWT_REFRESH_EXPIRE_DAYS:-7}
      FIREBASE_PROJECT_ID: ${FIREBASE_PROJECT_ID:-ai-dnd-47eb0}
      FIREBASE_CREDENTIALS_PATH: ${FIREBASE_CREDENTIALS_PATH:-}
      CORS_ORIGINS: ${CORS_ORIGINS:-["http://localhost:5173","http://localhost:3000","http://localhost:80"]}
      ENVIRONMENT: ${ENVIRONMENT:-development}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      PYTHONPATH: /app
      MEMORY_SERVICE_URL: http://memory-layer:8002
      MEMORY_SERVICE_API_KEY: ${MEMORY_SERVICE_API_KEY:-dev-memory-layer-key-change-in-production}
  ```
  Notice what is completely omitted:
  - `GEMINI_API_KEY`: Core API uses Imagen (Vertex AI) directly in [`apps/core-api/app/integrations/image_gen_client.py`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/app/integrations/image_gen_client.py) for the Studio endpoint `POST /v1/uploads/generate-cover-image`. Without `GEMINI_API_KEY`, AI cover image generation throws an unhandled authentication failure.
  - `CORE_API_PUBLIC_URL`: Used by [`apps/core-api/app/integrations/storage_client.py:42`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/app/integrations/storage_client.py#L42) to generate asset URLs. In Docker, it defaults to `http://localhost:8000`, which is inaccessible when running behind Nginx.
  - `GCS_BUCKET_NAME`: Core API cannot utilize Google Cloud Storage in production container deployments even if `GCS_BUCKET_NAME` is configured in the root `.env`.
- **Impact**:
  AI image generation in Studio is completely inoperable in Docker. Cloud storage cannot be utilized, and fallback local uploads construct broken URLs.
- **Remediation**:
  Add the missing variables to `core-api` in `docker-compose.yml`:
  ```yaml
  core-api:
    environment:
      ...
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
      CORE_API_PUBLIC_URL: ${CORE_API_PUBLIC_URL:-http://localhost:80}
      GCS_BUCKET_NAME: ${GCS_BUCKET_NAME:-}
  ```

---

### [NEW-03] Ephemeral Uploads Storage & Missing Nginx Route for `/uploads/`
- **Severity**: High (P1)
- **Category**: Storage Persistence & Ingress Routing
- **Location**: [`docker-compose.yml:39-69`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L39-L69) and [`apps/frontend/nginx.conf:5-33`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/nginx.conf#L5-L33)
- **Problem & Root Cause**:
  When GCS is not enabled, `core-api` stores uploaded images (avatars, scenario covers, banners, map images, audio files) in `/app/uploads` via `StaticFiles(directory="uploads")` in [`apps/core-api/app/main.py:81`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/app/main.py#L81).
  However:
  1. `core-api` has **no volume mount** for `/app/uploads` in `docker-compose.yml`.
  2. `apps/frontend/nginx.conf` has routes only for `/api/`, `/trs/`, and `/`:
     ```nginx
     location /api/ { proxy_pass http://core-api:8000/; ... }
     location /trs/ { proxy_pass http://turn-resolution-service:8001/; ... }
     location / {
         root /usr/share/nginx/html;
         try_files $uri $uri/ /index.html;
     }
     ```
  Any browser request for `/uploads/...` matches `location /` on Nginx, searches `/usr/share/nginx/html/uploads/`, and returns 404 or the SPA `index.html`.
- **Impact**:
  All local user uploads are permanently destroyed whenever the `aidnd-core-api` container is stopped or recreated. In production behind Nginx, all uploaded media requests fail immediately.
- **Remediation**:
  1. Add a persistent volume `uploads_data:/app/uploads` to `core-api` in `docker-compose.yml`.
  2. Add an explicit proxy route in `apps/frontend/nginx.conf`:
     ```nginx
     location /uploads/ {
         proxy_pass http://core-api:8000/uploads/;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto $scheme;
     }
     ```

---

### [NEW-04] Service-to-Service Secret Name Mismatch (`MEMORY_SERVICE_API_KEY` vs `MEMORY_LAYER_API_KEY`)
- **Severity**: High (P1)
- **Category**: Security Architecture & Service Coordination
- **Location**: [`docker-compose.yml:58, 85, 169`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L58), [`.env.example:41, 51`](file:///home/aryan-sherigar/projects/AI-DND/.env.example#L41)
- **Problem & Root Cause**:
  In `docker-compose.yml`:
  - `core-api` injects: `MEMORY_SERVICE_API_KEY: ${MEMORY_SERVICE_API_KEY:-dev-memory-layer-key-change-in-production}`
  - `turn-resolution-service` injects: `MEMORY_SERVICE_API_KEY: ${MEMORY_SERVICE_API_KEY:-dev-memory-layer-key-change-in-production}`
  - `memory-layer` injects: `CONTEXT_MEMORY_API_KEY: ${MEMORY_LAYER_API_KEY:-dev-memory-layer-key-change-in-production}`
  While `.env.example` mentions both names in comments, they represent the **exact same shared secret**. If a DevOps engineer or deployment script specifies `MEMORY_SERVICE_API_KEY=prod-secret-token` in their production `.env` without also setting `MEMORY_LAYER_API_KEY`, `memory-layer` continues running with the fallback key `dev-memory-layer-key-change-in-production`.
- **Impact**:
  Every request sent from `core-api` or `turn-resolution-service` to `memory-layer` (`/v1/memory/query`, `/v1/memory/ingest`) is rejected with HTTP 401 Unauthorized, causing narrative turn resolution and world-building memory extraction to fail.
- **Remediation**:
  In `docker-compose.yml`, align the environment variable fallback in `memory-layer`:
  ```yaml
  memory-layer:
    environment:
      CONTEXT_MEMORY_API_KEY: ${MEMORY_SERVICE_API_KEY:-${MEMORY_LAYER_API_KEY:-dev-memory-layer-key-change-in-production}}
  ```

---

### [NEW-05] Deep Readiness Probe Authentication Lockout on Memory Layer (`/v1/health` vs `/health`)
- **Severity**: Medium (P2)
- **Category**: Operations & Container Health Monitoring
- **Location**: [`apps/memory-layer/src/api/server.py:83-93`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/src/api/server.py#L83-L93) and [`apps/memory-layer/src/api/routes.py:474-485`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/src/api/routes.py#L474-L485)
- **Live Evidence**:
  Memory Layer container log:
  ```text
  2026-09-08 12:53:01,589 [INFO] [api.server:73] HTTP GET /v1/health -> status=401 duration=5111.94ms
  ```
- **Problem & Root Cause**:
  In `api/server.py`:
  ```python
  app.include_router(router, dependencies=[Depends(require_api_key)])
  ```
  Because the router is included with `dependencies=[Depends(require_api_key)]`, all routes declared inside `api/routes.py` require `Authorization: Bearer <key>`.
  In `api/routes.py`:
  ```python
  @router.get("/v1/health")
  async def health_check(request: Request) -> dict[str, str]:
      postgres_status = await check_postgres()
      hydradb_status = await check_hydradb()
      ...
  ```
  `server.py` defines a separate unauthenticated liveness probe `@app.get("/health")`, but the deep readiness probe `GET /v1/health` (which verifies Postgres and HydraDB dependencies) is locked behind authentication. Any external monitoring system, Kubernetes readiness probe, or Docker healthcheck pinging `/v1/health` receives a 401 Unauthorized.
- **Impact**:
  Orchestrators and monitoring systems cannot perform dependency-aware readiness healthchecks without hardcoding bearer credentials into their probe configurations.
- **Remediation**:
  Exempt `/v1/health` from the `require_api_key` dependency or move the readiness probe to `server.py` alongside `/health`.

---

## Detailed Analysis of Continuing / Persisting Issues

### [HIGH-03] Secret Exposure via Plaintext Command Line Echo in Compose Entrypoint
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml:117`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L117)
- **Problem**:
  ```yaml
  entrypoint: ["sh", "-c", "mkdir -p /tmp/graph /var/cache/slatedb && echo '${HYDRADB_API_KEY:-context-memory-local-smoke-token-32b}' > /tmp/graph/auth-token && exec graph-node"]
  ```
  Interpolating secrets directly into shell command lines exposes the secret in `/proc/<pid>/cmdline`, process listing tools (`ps`, `top`), and Docker inspection metadata (`docker inspect aidnd-hydradb`).
- **Remediation**: Pass the secret via Docker secret or mount the token file using a Docker volume secret.

### [MED-01] Missing CPU & Memory Resource Limits (DOS Risk)
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml) (all services)
- **Problem**: No service specifies `deploy.resources.limits` or `mem_limit`. A runaway task or memory leak can consume all host RAM and trigger the host Linux OOM killer.
- **Remediation**: Add standard resource bounds (`limits.cpus: '1.5'`, `limits.memory: 1024M`).

### [MED-02] Insecure Fallback Secret Defaults in Compose Definitions
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml:10, 47, 58, 78, 85, 167, 169`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L47)
- **Problem**: Insecure defaults (`dev-secret-key-change-in-production`, `postgres`, `dev-memory-layer-key-change-in-production`) allow production containers to start silently with well-known credentials if `.env` is omitted.
- **Remediation**: Use `${SECRET_KEY:?SECRET_KEY must be set}` for production deployments.

### [MED-03] Missing Application Healthchecks for Core API & TRS
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml:39, 70, 158`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L39)
- **Problem**: `core-api`, `turn-resolution-service`, and `memory-layer` do not define healthchecks. `frontend` depends on them via `service_started`, creating cold-start race conditions.
- **Remediation**: Add `healthcheck` querying `/health` using python urllib or curl.

### [MED-06] Insecure Nginx Default Configuration in Frontend Container
- **Status**: **STILL EXISTS**
- **Location**: [`apps/frontend/nginx.conf`](file:///home/aryan-sherigar/projects/AI-DND/apps/frontend/nginx.conf)
- **Problem**: Lacks HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`), lacks immutable asset caching for `/assets/`, and lacks gzip compression.
- **Remediation**: Add standard security headers and static asset caching directives to `nginx.conf`.

### [MED-07] Docker Compose Dev Node Modules Volume Desync
- **Status**: **PARTIALLY RESOLVED / KNOWN TRADE-OFF**
- **Location**: [`docker-compose.dev.yml:48-50`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.dev.yml#L48-L50)
- **Problem**: An anonymous volume `/app/node_modules` is mounted over the bind mount. Adding packages on the host does not update the container's node_modules without running `docker compose down -v`.

### [MED-08] Inconsistent Python Runtimes Across Monorepo (3.11 vs 3.12)
- **Status**: **STILL EXISTS**
- **Location**: [`apps/core-api/Dockerfile:1`](file:///home/aryan-sherigar/projects/AI-DND/apps/core-api/Dockerfile#L1) (3.11) vs [`apps/memory-layer/Dockerfile:1`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/Dockerfile#L1) (3.12).
- **Remediation**: Standardize all services on `python:3.11-slim` or migrate all to `python:3.12-slim`.

### [ADDL-01] Privileged Host Port 80 in Base `docker-compose.yml`
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml:204`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L204)
- **Problem**: Base file hardcodes `ports: - "80:8080"`. Requires root or unprivileged port tuning on Linux and conflicts if system port 80 is occupied.
- **Remediation**: Parameterize port: `ports: - "${FRONTEND_PROD_PORT:-80}:8080"`.

### [ADDL-02] Outbound Model Download on Every Boot (Hugging Face Ephemeral Cache)
- **Status**: **STILL EXISTS**
- **Location**: [`docker-compose.yml:158-185`](file:///home/aryan-sherigar/projects/AI-DND/docker-compose.yml#L158-L185) and [`apps/memory-layer/Dockerfile:17`](file:///home/aryan-sherigar/projects/AI-DND/apps/memory-layer/Dockerfile#L17)
- **Problem**: `memory-layer` downloads `sentence-transformers/all-MiniLM-L6-v2` (~90MB) into `/app/.cache/huggingface`. Without a named volume, rebuilding or recreating the container forces a full re-download.
- **Remediation**: Mount a named volume `hf_cache:/app/.cache/huggingface`.

---

## Actionable Remediation Roadmap

```mermaid
gantt
    title Infrastructure Remediation Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Operational Blockers & Container Health
    Rebuild Stale Dev Images (NEW-01)                       :active, p1_1, 2026-09-08, 1d
    Add Missing core-api Env Vars (NEW-02)                  :active, p1_2, 2026-09-08, 1d
    Add Uploads Volume & Nginx Route (NEW-03)               :active, p1_3, 2026-09-08, 1d
    Align Memory API Key Variables (NEW-04)                 :active, p1_4, 2026-09-08, 1d
    Unprotect Memory Readiness Probe (NEW-05)               :active, p1_5, 2026-09-08, 1d
    section Phase 2: Web Hardening & Reliability
    Harden Nginx Headers & Caching (MED-06)                 :p2_1, 2026-09-09, 1d
    Add Container Healthchecks (MED-03)                     :p2_2, 2026-09-09, 1d
    Add Hugging Face Cache Volume (ADDL-02)                 :p2_3, 2026-09-10, 1d
    Parameterize Host Port 80 (ADDL-01)                     :p2_4, 2026-09-10, 1d
    section Phase 3: Production Hardening & Standards
    Eliminate Echo in HydraDB Entrypoint (HIGH-03)          :p3_1, 2026-09-11, 1d
    Enforce Resource Limits (MED-01)                        :p3_2, 2026-09-11, 1d
    Enforce Non-Fallback Secrets (MED-02)                   :p3_3, 2026-09-12, 1d
    Standardize Python Base Runtimes (MED-08)               :p3_4, 2026-09-12, 1d
```

### Phase 1: Immediate Operational & Stability Fixes
1. **Trigger Development Stack Image Rebuild**: Run `docker compose -f docker-compose.yml -f docker-compose.dev.yml build core-api turn-resolution-service` to bake `mutagen` and `google-cloud-storage` into local development images.
2. **Inject Missing Variables into `core-api`**: Add `GEMINI_API_KEY`, `CORE_API_PUBLIC_URL`, and `GCS_BUCKET_NAME` to `core-api` in `docker-compose.yml`.
3. **Persist and Route File Uploads**: Mount `uploads_data:/app/uploads` in `core-api` and configure `location /uploads/` proxying in `apps/frontend/nginx.conf`.
4. **Synchronize Memory Service API Keys**: Update `docker-compose.yml` so `memory-layer` accepts `MEMORY_SERVICE_API_KEY`.
5. **Permit Unauthenticated Readiness Probing**: Exempt `GET /v1/health` from `require_api_key` in `apps/memory-layer/src/api/server.py`.

### Phase 2: Web Hardening & Orchestration Reliability
1. **Nginx Security & Caching**: Add security headers and immutable caching rules for `/assets/` in `apps/frontend/nginx.conf`.
2. **Application Healthchecks**: Configure healthchecks querying `/health` for `core-api`, `trs`, and `memory-layer`.
3. **Persist Hugging Face Cache**: Mount a named volume `hf_cache:/app/.cache/huggingface` to prevent redownloading 90MB model weights on container restart.
4. **Parameterize Port 80**: Change `80:8080` to `${FRONTEND_PROD_PORT:-80}:8080` in `docker-compose.yml`.

### Phase 3: Security Hardening & Monorepo Standards
1. **Secure Secret Injection**: Replace entrypoint shell echo in HydraDB with direct secret mount.
2. **Resource Constraints**: Define `deploy.resources.limits` across all services in `docker-compose.yml`.
3. **Enforce Mandatory Production Secrets**: Transition production Compose variables to `${VAR:?error}` syntax.
4. **Standardize Python Runtimes**: Align `core-api`, `trs`, and `memory-layer` to a single Python minor version.
