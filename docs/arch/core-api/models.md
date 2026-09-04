# Core API Architecture — Pydantic Models & Schemas

This document profiles the Pydantic v2 schemas located in `apps/core-api/app/models/`. These models enforce strict boundary typing for HTTP request bodies, query parameters, database serializations, and inter-service payloads.

---

## 1. Overview & Schema Design Rules

In accordance with [CLAUDE.md](file:///home/aryan-sherigar/projects/AI-DND/CLAUDE.md):
- **Pydantic v2 exclusively**: `from pydantic import BaseModel, Field, ConfigDict`.
- **No raw dictionaries crossing service boundaries**: All endpoints consume and return strongly typed models.
- **Python 3.10+ union syntax**: Optional fields are typed as `T | None`, never `Optional[T]`.
- **Never use `Any`**: Dynamic or user-defined schemas are typed as `dict[str, object]`.
- **No duplicate schema definitions**: Common domain types are shared rather than copied.

---

## 2. Model Profiles

### `apps/core-api/app/models/scenario.py`
- **Purpose & Layer:** Request and response schemas for scenario creation, updates, and discovery.
- **Key Models:**
  - `ScenarioCreate`: Ingestion schema with `title`, `description`, `logline`, `system_prompt`, `opening_scene`, `genre_tags: list[str]`, `content_tag: Literal["all-ages", "teen", "mature"]`, `complexity_tier: Literal["newbie", "master"]`, `player_count_support: Literal["solo", "duo", "party"]`, `state_schema: dict[str, object]`.
  - `ScenarioUpdate`: Partial patch model for draft scenarios with all fields optional.
  - `ScenarioResponse`: Serialized output model including `scenario_id: UUID`, `creator_id: UUID`, timestamps, `is_published: bool`, `status`, `play_count: int`, and `rating_score: Decimal`.
  - `ScenarioListResponse`: Paginated envelope containing `items: list[ScenarioResponse]`, `total: int`, `limit: int`, `offset: int`.

### `apps/core-api/app/models/playthrough.py`
- **Purpose & Layer:** Game session creation and status schemas.
- **Key Models:**
  - `PlaythroughCreate`: Ingestion schema specifying `scenario_id: UUID`, optional `character_name`, and initial archetype/attributes.
  - `PlaythroughResponse`: Full session representation including `current_state`, `current_turn`, `status`, `end_outcome`, and participant list.
  - `PlaythroughStatePatch`: Schema for modifying client-side character or inventory values.

### `apps/core-api/app/models/entity.py`
- **Purpose & Layer:** Master Mode actor and asset schemas.
- **Key Models:**
  - `EntityCreate`: Declares `name`, `entity_type: Literal["NPC", "Item", "Location", "Faction"]`, `archetype`, `attributes: dict[str, object]`, `is_dynamic: bool`.
  - `EntityUpdate`: Partial update schema.
  - `EntityResponse`: Serialized representation with UUID and scenario FK.

### `apps/core-api/app/models/scenario_entity_type.py`
- **Purpose & Layer:** Custom entity taxonomy schemas.
- **Key Models:**
  - `ScenarioEntityTypeCreate`: Declares `type_name`, `display_label`, `color_hex`, `attribute_schema: dict[str, object]`.
  - `ScenarioEntityTypeResponse`: Serialized output model.

### `apps/core-api/app/models/fact.py`
- **Purpose & Layer:** Triplet lore knowledge schemas.
- **Key Models:**
  - `FactCreate`: Declares `subject: str`, `predicate: str`, `object_value: str`, `category: str`.
  - `FactResponse`: Serialized fact entity.

### `apps/core-api/app/models/condition.py`
- **Purpose & Layer:** State condition trigger schemas.
- **Key Models:**
  - `ConditionCreate`: Declares `trigger_expression: dict[str, object]`, `effect_description: str`.
  - `ConditionResponse`: Serialized condition model.

### `apps/core-api/app/models/end_condition.py`
- **Purpose & Layer:** Win/loss outcome trigger schemas.
- **Key Models:**
  - `EndConditionCreate`: Declares `trigger_expression: dict[str, object]`, `outcome_type: Literal["victory", "defeat", "neutral"]`, `terminal_prompt: str`.
  - `EndConditionResponse`: Serialized model.

### `apps/core-api/app/models/invariant.py`
- **Purpose & Layer:** State boundary constraint schemas.
- **Key Models:**
  - `InvariantCreate`: Declares `expression: dict[str, object]`, `error_message: str`.
  - `InvariantResponse`: Serialized invariant model.

### `apps/core-api/app/models/map.py`
- **Purpose & Layer:** Interactive map, pin, and connection schemas.
- **Key Models:**
  - `ScenarioMapCreate`, `ScenarioMapResponse`: Map canvas dimensions, image URL, fog-of-war flags.
  - `MapPinCreate`, `MapPinResponse`: Percentile coordinates (`x_percent`, `y_percent`), label, optional `entity_id`.
  - `MapConnectionCreate`, `MapConnectionResponse`: Graph edge between two pin UUIDs, `is_bidirectional: bool`.

### `apps/core-api/app/models/review.py` & `rating.py`
- **Purpose & Layer:** Community review, rating, and public playthrough schemas.
- **Key Models:**
  - `ScenarioReviewCreate`: Ingestion schema with `rating: int = Field(ge=1, le=5)` and `comment: str`.
  - `ScenarioReviewResponse`: Public review output model with author display name and timestamp.
  - `PublicPlaythroughSummary`: Anonymized playthrough preview for scenario showcase.

### `apps/core-api/app/models/auth.py` & `user.py`
- **Purpose & Layer:** User identity, authentication, and profile customization schemas.
- **Key Models:**
  - `TokenPayload`: Decoded Firebase JWT structure (`uid`, `email`, `name`, `picture`).
  - `UserResponse`: Profile representation with bio, preferred genres, and avatar.
  - `UserUpdate`: Mutable profile attributes.

### `apps/core-api/app/models/share.py`
- **Purpose & Layer:** Social share link token models.
- **Key Models:**
  - `ShareCreate`: Target `playthrough_id`, `role: Literal["spectator", "participant"]`, optional `ttl_hours`.
  - `ShareResponse`: Cryptographic share URL token and expiration date.

### `apps/core-api/app/models/upload.py`
- **Purpose & Layer:** Asset upload models.
- **Key Models:**
  - `UploadUrlRequest`: Declares `filename`, `content_type`, and `file_size_bytes`.
  - `UploadUrlResponse`: Signed GCS PUT URL and resulting public asset URL.

### `apps/core-api/app/models/memory.py`
- **Purpose & Layer:** Inter-service memory ingestion contracts.
- **Key Models:**
  - `EntityIngestPayload`, `FactIngestPayload`: Entities and lore facts serialized for the Memory Service.
  - `MemoryTemplateIngestRequest`: Complete scenario knowledge graph payload dispatched during the publish flow.
