"""Unit tests for end_condition_evaluator.py."""

import uuid

from app.models.turn import LoadedState
from app.turn.steps import end_condition_evaluator

_WARDEN_DEFEATED = {
    "condition_expression": {"field": "the_warden.health", "op": "<=", "value": 0},
    "outcome_tag": "win",
    "outcome_title": "The Ashen Ending",
    "outcome_text": "The Warden kneels, and the cairn exhales for the first time in a "
    "hundred years.",
    "is_secret": False,
}

_PLAYER_FALLS = {
    "condition_expression": {"field": "player.health", "op": "<=", "value": 0},
    "outcome_tag": "lose",
    "outcome_title": "Consumed",
    "outcome_text": "The cairn does not release what it takes.",
    "is_secret": False,
}

_VIGILS_ENDING = {
    "condition_expression": {"field": "flags.made_pact", "op": "==", "value": True},
    "outcome_tag": "win",
    "outcome_title": "The Vigil's Ending",
    "outcome_text": "You do not kill the Warden. You relieve it.",
    "is_secret": True,
}


def _loaded_state(end_conditions: list[dict[str, object]]) -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={"end_conditions": end_conditions},
        state={},
        turn_count=0,
        checkpoint=None,
    )


def test_matches_condition_against_final_state() -> None:
    loaded_state = _loaded_state([_WARDEN_DEFEATED, _PLAYER_FALLS])
    final_state = {"the_warden": {"health": 0}, "player": {"health": 100}}

    matched = end_condition_evaluator.evaluate_end_conditions(loaded_state, final_state)

    assert matched is not None
    assert matched.outcome_tag == "win"
    assert matched.outcome_title == "The Ashen Ending"
    assert matched.outcome_text == _WARDEN_DEFEATED["outcome_text"]


def test_first_match_in_snapshot_order_wins() -> None:
    loaded_state = _loaded_state([_WARDEN_DEFEATED, _VIGILS_ENDING])
    final_state = {
        "the_warden": {"health": 0},
        "flags": {"made_pact": True},
    }

    matched = end_condition_evaluator.evaluate_end_conditions(loaded_state, final_state)

    assert matched is not None
    assert matched.outcome_title == "The Ashen Ending"
    assert "Vigil" not in matched.outcome_title
    assert matched.outcome_text != _VIGILS_ENDING["outcome_text"]


def test_no_match_returns_none() -> None:
    loaded_state = _loaded_state([_WARDEN_DEFEATED, _PLAYER_FALLS, _VIGILS_ENDING])
    final_state = {
        "the_warden": {"health": 40},
        "player": {"health": 60},
        "flags": {"made_pact": False},
    }

    matched = end_condition_evaluator.evaluate_end_conditions(loaded_state, final_state)

    assert matched is None


def test_secret_ending_matches_identically_to_non_secret() -> None:
    loaded_state = _loaded_state([_VIGILS_ENDING])
    final_state = {"flags": {"made_pact": True}}

    matched = end_condition_evaluator.evaluate_end_conditions(loaded_state, final_state)

    assert matched is not None
    assert matched.outcome_title == "The Vigil's Ending"


def test_no_end_conditions_authored_returns_none() -> None:
    loaded_state = _loaded_state([])

    matched = end_condition_evaluator.evaluate_end_conditions(loaded_state, {})

    assert matched is None


def test_malformed_expression_is_treated_as_no_match() -> None:
    """A condition_expression that isn't a dict (data corruption that slipped
    past Studio validation) makes evaluate() raise TypeError — caught and
    logged, never allowed to fail the turn."""
    malformed = {
        "condition_expression": 42,
        "outcome_tag": "lose",
        "outcome_title": "Should Never Fire",
        "outcome_text": "unreachable",
        "is_secret": False,
    }
    loaded_state = _loaded_state([malformed])

    matched = end_condition_evaluator.evaluate_end_conditions(
        loaded_state, {"player": {"health": 0}}
    )

    assert matched is None
