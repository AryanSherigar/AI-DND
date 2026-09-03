"""Dynamic Pydantic model construction for master-mode game state validation.

Builds two kinds of models, both cached by schema shape (not per-playthrough
— Cloud Run scale-to-zero makes a durable per-playthrough cache unrealistic;
this LRU-by-schema-hash is the honest "build once, cache" implementation: a
cold start rebuilds it once, cheaply, and a warm instance reuses it across
every turn that shares the same scenario shape):

- get_state_model(state_schema): Playthrough.state's top-level shape
  (e.g. "player", "flags") — everything NOT under the "entities" bucket.
- get_entity_attribute_model(attributes_schema): one entity's own instance
  attributes (e.g. a specific character's health/awareness).

These are deliberately two separate model families, not one unified schema:
different entities in the same scenario have different attributes_schema
shapes, so there is no single homogeneous type that could describe
Playthrough.state["entities"] as a whole.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from pydantic import BaseModel, Field, create_model

_TYPE_MAP: dict[str, type] = {"string": str, "number": float, "boolean": bool}


def get_state_model(state_schema: dict[str, object]) -> type[BaseModel]:
    """Build (or reuse) the Pydantic model for a scenario's state_schema."""
    return _build_model(_hash(state_schema), json.dumps(state_schema, sort_keys=True))


def get_entity_attribute_model(attributes_schema: dict[str, object]) -> type[BaseModel]:
    """Build (or reuse) the Pydantic model for one entity's attributes_schema."""
    schema_json = json.dumps(attributes_schema, sort_keys=True)
    return _build_model(_hash(attributes_schema), schema_json)


def _hash(schema: dict[str, object]) -> str:
    payload = json.dumps(schema, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@lru_cache(maxsize=256)
def _build_model(schema_hash: str, schema_json: str) -> type[BaseModel]:
    """Build once per distinct schema shape; cached for the life of the
    worker process, keyed by content hash rather than playthrough_id so two
    playthroughs of the same scenario share one compiled model."""
    fields = json.loads(schema_json)
    return _build_model_from_fields(fields, f"GameState_{schema_hash[:8]}")


def _build_model_from_fields(
    fields: dict[str, object], model_name: str
) -> type[BaseModel]:
    model_fields: dict[str, object] = {}
    for name, field_def in fields.items():
        if isinstance(field_def, dict):
            model_fields[name] = _field_to_pydantic_type(
                field_def, f"{model_name}_{name}"
            )
    return create_model(model_name, **model_fields)  # type: ignore[call-overload]


def _field_to_pydantic_type(
    field_def: dict[str, object], nested_model_name: str
) -> tuple[type, object]:
    field_type = field_def.get("type")

    if field_type in _TYPE_MAP:
        return _primitive_field(str(field_type), field_def)
    if field_type in ("enum", "entity_ref"):
        return (str | None, Field(default=field_def.get("initial")))
    if field_type == "list":
        return _list_field(field_def)
    if field_type == "object":
        return _object_field(field_def, nested_model_name)
    # Any unrecognized type: shape placeholder only. Note "derived" is a
    # boolean flag alongside a real type (e.g. {"type": "number", "derived":
    # true}), not a type value of its own — a derived field still validates
    # against its declared type here; state_validator.py is what rejects it
    # as a direct tool-call target.
    return (object | None, Field(default=field_def.get("initial")))


def _primitive_field(
    field_type: str, field_def: dict[str, object]
) -> tuple[type, object]:
    py_type = _TYPE_MAP[field_type]
    constraints: dict[str, object] = {}
    if field_type == "number":
        if field_def.get("min") is not None:
            constraints["ge"] = field_def["min"]
        if field_def.get("max") is not None:
            constraints["le"] = field_def["max"]
    return (py_type | None, Field(default=field_def.get("initial"), **constraints))


def _list_field(field_def: dict[str, object]) -> tuple[type, object]:
    item_type = str(field_def.get("item_type", "string"))
    item_py_type = _TYPE_MAP.get(item_type, str)
    return (list[item_py_type], Field(default_factory=list))  # type: ignore[valid-type]


def _object_field(
    field_def: dict[str, object], nested_model_name: str
) -> tuple[type, object]:
    nested_fields = field_def.get("fields", {})
    sub_model = _build_model_from_fields(
        nested_fields if isinstance(nested_fields, dict) else {}, nested_model_name
    )
    return (sub_model, Field(default_factory=sub_model))
