# Spec: Authentication System

## 1. Objective & User Outcome
- **Problem Statement:** AI-DND requires a secure, robust authentication system to identify creators and players. It must protect private game states and authoring surfaces, while allowing open discovery of published scenarios.
- **User Story:** As a player or creator, I want to sign in securely using Google so that my created worlds and ongoing playthroughs are tied to my identity and protected from unauthorized access.
- **Success Criteria:**
  - Secure integration with Firebase Auth (Google Sign-In).
  - Implementation of a custom JWT strategy (15-minute in-memory access token, 7-day HttpOnly refresh token).
  - Backend endpoints are protected by robust token validation, with the exception of the discovery feed.
  - Automatic user provisioning upon first login from Google profile data.
  - Local development bypass using the `X-Dev-User-Id` header to eliminate Firebase dependencies during dev.

## 2. Technical Architecture & Data Flow
- **Components Involved:** React/Vite Frontend, FastAPI Core API, FastAPI Turn Resolution Service (TRS), PostgreSQL, Firebase Auth.
- **Sequence Flow:**
  1. Frontend authenticates user with Google via Firebase JS SDK.
  2. Frontend receives Firebase ID Token and POSTs it to `Core API: /v1/auth/token`.
  3. Core API verifies the token using the Firebase Admin SDK.
  4. Core API extracts user info and upserts the `User` record in PostgreSQL.
  5. Core API issues a short-lived Access Token (JWT) in the response body and a long-lived Refresh Token (JWT) in a secure HttpOnly cookie (`SameSite=Lax`, `Path=/v1/auth/refresh`).
  6. Frontend stores the Access Token in memory and attaches it as a `Bearer` token to all subsequent protected API requests.
  7. When the Access Token expires, frontend calls `Core API: /v1/auth/refresh` (cookie sent automatically) to receive a new Access Token.
  8. Protected backend endpoints use FastAPI `Depends()` to validate the Access Token locally. Core API additionally queries the DB to check `token_version` for immediate revocation. TRS only checks JWT signature and expiry to avoid DB latency.
  9. For local development, if `ENVIRONMENT=development` and the `X-Dev-User-Id` header is present, the auth dependency bypasses standard validation and uses the provided UUID.

## 3. The Six Core Engineering Dimensions
### 3.1. Commands
- Build: `docker compose build`
- Test: `pytest tests/services/test_auth_service.py tests/routers/test_auth.py -v`
- Lint / Type-Check: `ruff check . --fix && ruff format .` (Python) / `eslint . --fix && prettier --write .` (TypeScript)

### 3.2. Testing Strategy & Conformance
- **Backend Tests:** Integration tests in `tests/routers/test_auth.py` to cover token exchange, auto-provisioning, refresh logic, and dev bypass. 
- **Mocking:** `unittest.mock.patch` for the Firebase Admin SDK to simulate valid/invalid token verification without real network requests.
- **Cases:** Valid Google token exchange, expired Google token rejection, missing token handling, missing DB records (auto-creation).

### 3.3. Project Structure & File Layout
- **Files to create/modify (Backend - Core API):**
  - `app/db/migrations/versions/001_initial_schema.py` (Add `token_version` to `users` table)
  - `app/db/models/user.py` (Add `token_version` property)
  - `app/routers/auth.py`
  - `app/services/auth_service.py`
  - `app/middleware/auth.py` (Implemented as FastAPI Dependencies)
  - `app/exceptions/auth_exceptions.py`
  - `app/models/auth.py` (Pydantic schemas)
- **Files to create/modify (Backend - TRS):**
  - `app/middleware/auth.py`
  - `app/exceptions/auth_exceptions.py`
- **Files to create/modify (Frontend):**
  - `src/features/auth/api/auth.api.ts`
  - `src/features/auth/hooks/useAuth.ts`
  - `src/features/auth/stores/auth.store.ts`
  - `src/features/auth/providers/AuthProvider.tsx`
  - `src/features/auth/components/LoginButton/LoginButton.tsx`
  - `src/features/auth/components/AuthGuard/AuthGuard.tsx`
  - `src/features/auth/pages/LoginPage.tsx`
  - `src/shared/lib/api-client.ts` (Interceptor logic)

### 3.4. Code Style & Interfaces
- Type Contracts (Pydantic Models):
```python
class TokenExchangeRequest(BaseModel):
    firebase_id_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
```

### 3.5. Git & Review Workflow
- Suggested branch name: `feat/auth-system`
- Commit scope guidelines: Follow structured commits (`feat(core-api): implement auth middleware`).

### 3.6. Boundaries (Three-Tier Model)
- ✅ **Always:** Use custom exceptions (`AuthError`, `InvalidTokenError`), apply Strict types everywhere.
- ⚠️ **Ask First:** Changing the JWT expiration windows, adding rate limits (deferred to future).
- 🚫 **Never:** Leak refresh tokens into JavaScript memory, log JWT contents, commit Firebase secret keys to git.

## 4. Edge Cases, Rate Limits & Graceful Degradation
- **Token Revocation Trade-off:** User tokens can be revoked immediately in the Core API by incrementing a `token_version` on the User row. However, TRS avoids a DB lookup and relies solely on the JWT expiry. A revoked user may retain TRS access for up to 15 minutes.
- **Local Dev Bypass Security:** The dev bypass code path is guarded by `if settings.environment == "development":` and throws exceptions if enabled in production.
- **Refresh Token Failure:** If the refresh token is missing, expired, or invalid, the backend returns 401 Unauthorized, and the frontend automatically redirects to `/login`.

## 5. Phased Implementation Tasks (Task Checklist)
- [x] **Task 1 (Backend Core Auth):** Implement Firebase token verification, User auto-provisioning, custom JWT generation (Access + HttpOnly Refresh), and `POST /v1/auth/token` + `POST /v1/auth/refresh`.
- [x] **Task 2 (Backend Auth Middleware):** Implement the local JWT verification middleware for both Core API and TRS, including the `X-Dev-User-Id` bypass logic. Ensure it applies to all routes except discovery feed and health checks.
- [x] **Task 3 (Frontend Auth Provider & UI):** Setup Firebase JS SDK, `AuthProvider`, `useAuth` hook, and the `LoginPage` component.
- [x] **Task 4 (Frontend API Client Integration):** Update `shared/lib/api-client.ts` to automatically inject the Access Token, handle 401s, silently refresh tokens via cookie, and queue requests during active refreshes.
