# Spec: Docker Local Stack (Docker Compose & Containerization)

## 1. Objective & User Outcome
- **Problem Statement:** The AI-DND monorepo currently lacks Dockerfiles and Docker Compose orchestration to run the full stack locally. Developers need a unified, zero-friction local stack including all three apps (`frontend`, `core-api`, `turn-resolution-service`) and a PostgreSQL database.
- **User Story:**
  - As a developer, I want to run `docker compose up` to launch the production-like stack or `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` to run hot-reloading development environments across all three services and Postgres.
- **Success Criteria:**
  - `apps/core-api/Dockerfile` created using `python:3.11-slim` with automated Alembic migration execution on startup (`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`).
  - `apps/turn-resolution-service/Dockerfile` created using `python:3.11-slim` running uvicorn (`uvicorn app.main:app --host 0.0.0.0 --port 8001`).
  - `apps/frontend/Dockerfile` created using multi-stage Node 20 build -> Nginx alpine static host on port 80.
  - `.env.example` created in the root directory detailing all container environment variables.
  - `docker-compose.yml` created defining services: `postgres`, `core-api`, `turn-resolution-service`, and `frontend` with network bridge `aidnd-net` and volume `postgres_data`.
  - `docker-compose.dev.yml` created supplying hot-reloading overrides (bind mounts for `/app`, host ports `5173`, `8000`, `8001`, `5432`).
  - Full compliance with `AGENTS.md` and monorepo boundaries.

## 2. Technical Architecture & Data Flow
- **Components Involved:**
  - **`postgres` Service:** PostgreSQL 16 image (`postgres:16-alpine`), healthcheck via `pg_isready -U postgres -d aidnd_db`.
  - **`core-api` Service:** FastAPI app on port 8000, connects to `postgres:5432`, depends on `postgres` being healthy. Runs `alembic upgrade head` before entrypoint.
  - **`turn-resolution-service` Service:** FastAPI app on port 8001, connects to `postgres:5432`, depends on `postgres` being healthy.
  - **`frontend` Service:** React Vite SPA. Prod: Nginx on port 80; Dev: Node container on port 5173 with Vite dev server and HMR.
- **Network & Volumes:**
  - Bridge network: `aidnd-net`
  - Named persistent volume: `postgres_data`

## 3. The Six Core Engineering Dimensions

### 3.1. Commands
- **Launch Base / Production Stack:** `docker compose up --build`
- **Launch Development Stack (Hot-Reload):** `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`
- **Stop Stack & Volumes:** `docker compose down -v`
- **Lint / Validation:** Verify syntax via `docker compose config` and check container health with `docker compose ps`

### 3.2. Testing Strategy & Conformance
- Test startup of all containers via `docker compose up -d`.
- Verify PostgreSQL connection and health via `docker exec -it <postgres_container> pg_isready`.
- Verify `core-api` health check endpoint at `http://localhost:8000/health`.
- Verify `turn-resolution-service` health check endpoint at `http://localhost:8001/health`.
- Verify `frontend` loading at `http://localhost:5173` (dev) / `http://localhost:80` (prod).

### 3.3. Project Structure & File Layout
- Files to create:
  - `docs/specs/docker-local-stack.spec.md`
  - `apps/core-api/Dockerfile`
  - `apps/turn-resolution-service/Dockerfile`
  - `apps/frontend/Dockerfile`
  - `apps/frontend/nginx.conf`
  - `.env.example`
- Files to modify:
  - `docker-compose.yml`
  - `docker-compose.dev.yml`

### 3.4. Code Style & Interfaces
- Standard Dockerfile layout (cached layer ordering: `COPY requirements.txt` / `package.json` -> `RUN install` -> `COPY src`).
- Clean YAML indenting (2 spaces), explicit environment keys, healthchecks using standard binaries.

### 3.5. Git & Review Workflow
- Branch: `feat/docker-local-stack`
- PR Checklist:
  - `docker compose config` passes with zero errors.
  - All 4 services (`postgres`, `core-api`, `turn-resolution-service`, `frontend`) start up successfully.
  - Health checks pass for API containers.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use non-root/slim images; pin main software versions (`python:3.11-slim`, `postgres:16-alpine`, `node:20-alpine`); expose explicit port mappings.
- ⚠️ **Ask First:** Adding extra infrastructure containers (Redis, LocalStack, etc.).
- 🚫 **Never:** Commit secret credentials or production keys inside Dockerfiles or compose configs; use `latest` unpinned image tags.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Postgres Startup Delay:** Services use `depends_on` with `condition: service_healthy` so python apps wait for Postgres DB initialization.
- **Alembic Migration Race Condition:** `core-api` executes `alembic upgrade head` synchronously before launching uvicorn.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Core API Dockerfile):** Implement `apps/core-api/Dockerfile`.
- [ ] **Task 2 (Turn Resolution Service Dockerfile):** Implement `apps/turn-resolution-service/Dockerfile`.
- [ ] **Task 3 (Frontend Dockerfile & Nginx Config):** Implement `apps/frontend/Dockerfile` and `apps/frontend/nginx.conf`.
- [ ] **Task 4 (Root Environment Template):** Populate `.env.example`.
- [ ] **Task 5 (Base Compose Configuration):** Implement `docker-compose.yml`.
- [ ] **Task 6 (Dev Compose Overrides):** Implement `docker-compose.dev.yml`.
- [ ] **Task 7 (Verification & Testing):** Run docker compose validation and verify health endpoints.
