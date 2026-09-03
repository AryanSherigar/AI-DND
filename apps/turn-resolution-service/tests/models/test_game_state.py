"""Unit tests for models/game_state.py's dynamic Pydantic model builder."""

import pytest
from pydantic import ValidationError

from app.models.game_state import get_entity_attribute_model, get_state_model

_STATE_SCHEMA = {
    "player": {
        "type": "object",
        "fields": {
            "health": {"type": "number", "min": 0, "max": 100, "initial": 100},
            "sanity": {"type": "number", "min": 0, "max": 100, "initial": 100},
            "location": {"type": "entity_ref", "initial": "ashfall_village"},
            "inventory": {"type": "list", "item_type": "entity_ref", "initial": []},
        },
    },
    "flags": {
        "type": "object",
        "fields": {"entered_cairn": {"type": "boolean", "initial": False}},
    },
    "warden_awareness": {"type": "number", "derived": True, "initial": 0},
}


def test_get_state_model_accepts_valid_state() -> None:
    model = get_state_model(_STATE_SCHEMA)
    validated = model.model_validate(
        {
            "player": {
                "health": 90,
                "sanity": "85",
                "location": "hollow_cairn",
                "inventory": ["ember_sigil"],
            },
            "flags": {"entered_cairn": True},
            "narrative": {"ignored": "extra keys outside state_schema are ignored"},
        }
    )
    dumped = validated.model_dump()
    assert dumped["player"]["health"] == 90.0
    assert dumped["player"]["sanity"] == 85.0
    assert dumped["flags"]["entered_cairn"] is True


def test_get_state_model_rejects_bad_nested_field_type() -> None:
    model = get_state_model(_STATE_SCHEMA)
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({"player": {"health": "not a number"}})
    assert "player" in str(exc_info.value) or "health" in str(exc_info.value)


def test_get_state_model_enforces_range_constraints() -> None:
    model = get_state_model(_STATE_SCHEMA)
    with pytest.raises(ValidationError):
        model.model_validate({"player": {"health": 500}})


def test_get_state_model_cache_returns_identical_instance_for_same_schema() -> None:
    model_a = get_state_model(_STATE_SCHEMA)
    model_b = get_state_model(_STATE_SCHEMA)
    assert model_a is model_b


def test_get_state_model_cache_returns_different_instance_after_schema_change() -> None:
    model_a = get_state_model(_STATE_SCHEMA)
    changed_schema = {**_STATE_SCHEMA, "flags": {"type": "object", "fields": {}}}
    model_b = get_state_model(changed_schema)
    assert model_a is not model_b


def test_get_entity_attribute_model_validates_one_entitys_attributes() -> None:
    attrs_schema = {
        "health": {"type": "number", "initial": 150, "min": 0, "max": 150},
        "awareness": {"type": "number", "initial": 0},
    }
    model = get_entity_attribute_model(attrs_schema)
    validated = model.model_validate({"health": 120, "awareness": "10"})
    assert validated.model_dump() == {"health": 120.0, "awareness": 10.0}
