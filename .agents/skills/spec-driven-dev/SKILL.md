---
name: spec-driven-dev
description: "Triggers when designing, planning, or scoping a new feature, architecture change, or API contract. Generates an actionable, production-grade technical specification in markdown following the 4-phase gated SDD workflow."
---

# Spec-Driven Development (SDD) Architect

## Objective
Act as a Staff Software Architect to produce a structured, unambiguous specification in `docs/specs/<feature-name>.spec.md`. Enforce a gated workflow: never output application code during the specification phase.

---

## 4-Phase Gated Workflow Protocol

1. **Phase 1: Specify (Read-Only / Exploration)**
   - Analyze existing repository context, database models, and API boundaries.
   - Clarify the "Why" and user experience goals before discussing low-level implementation.
   - Ask concise clarifying questions if critical constraints or dependencies are ambiguous.

2. **Phase 2: Plan (Technical Design & 6-Area Architecture)**
   - Draft `docs/specs/<feature-name>.spec.md` strictly adhering to the **Spec Template** below.
   - Lock down API contracts, database modifications, and failure scenarios.

3. **Phase 3: Tasks (Atomic Breakdown)**
   - Decompose the implementation into isolated, testable, and reviewable tasks.
   - Ensure each task specifies a target file, test verification command, and expected output.

4. **Phase 4: Review Gate**
   - Present the spec summary and task list to the user for approval.
   - **Hard Stop:** Halt and wait for user sign-off before exiting the planning phase.

---

## Technical Specification Template

When generating or updating `docs/specs/<feature-name>.spec.md`, use the following structure:

```markdown
# Spec: [Feature / System Name]

## 1. Objective & User Outcome
- **Problem Statement:** What problem is being solved?
- **User Story:** As a [role], I want to [action] so that [benefit].
- **Success Criteria:** Concrete, measurable outcomes (e.g., latency thresholds, throughput, behavior).

## 2. Technical Architecture & Data Flow
- **Components Involved:** (e.g., Next.js App Router, FastAPI async handlers, Redis Streams, PostgreSQL).
- **Sequence Flow:** Step-by-step data journey from request ingress to persistence/streaming.

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `[exact command with flags]`
- Test: `[exact test runner command with file target]`
- Lint / Type-Check: `[exact linter command]`

### 3.2. Testing Strategy & Conformance
- Test framework and directory structure (e.g., `tests/integration/test_<feature>.py`).
- Deterministic test cases covering happy path, null values, network timeouts, and token limit overflows.

### 3.3. Project Structure & File Layout
- Files to create: `[path/to/file.py]`
- Files to modify: `[path/to/existing.ts]`
- Documentation/schemas: `[path/to/schema.json]`

### 3.4. Code Style & Interfaces
- Type contracts (Pydantic models / TypeScript interfaces).
- Concrete code snippet demonstrating naming, error encapsulation, and return types.

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/<feature-slug>`
- Commit scope guidelines and PR validation checklist.

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Run targeted test suite before reporting completion; use explicit type annotations; log domain exceptions with full tracebacks.
- ⚠️ **Ask First:** Modifying existing database migrations; adding third-party dependencies; altering shared API contracts.
- 🚫 **Never:** Commit API keys/secrets; modify dependencies in `node_modules/` or lockfiles manually; bypass failing test suites.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- Handling upstream LLM latency, HTTP 429 rate limits, and network connection drops.
- Stream cancellation (`asyncio.CancelledError` / client disconnect handling).
- Idempotency guarantees for queue-backed background tasks.

## 5. Phased Implementation Tasks (Task Checklist)
- [ ] **Task 1 (Contract & Models):** Define schemas in `[file]` and verify with `[lint command]`.
- [ ] **Task 2 (Core Logic & Unit Tests):** Implement service layer and pass `[test command]`.
- [ ] **Task 3 (Integration & Endpoints):** Wire HTTP/SSE routes and run integration test suite.
- [ ] **Task 4 (Client/UI Consumption):** Integrate frontend hook/component and run type-check.