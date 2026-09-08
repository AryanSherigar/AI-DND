"""when_active expression evaluation -- Milestone 4 of the AI-DND bridge."""

from __future__ import annotations

import unittest

from context_memory.retrieval.expression_eval import (
    ExpressionError,
    evaluate_expression,
)


class BasicOperatorTests(unittest.TestCase):
    def test_none_expression_is_always_active(self):
        self.assertTrue(evaluate_expression(None, {}))

    def test_equals(self):
        self.assertTrue(
            evaluate_expression(
                {"field": "entered_cave", "op": "==", "value": True},
                {"entered_cave": True},
            )
        )
        self.assertFalse(
            evaluate_expression(
                {"field": "entered_cave", "op": "==", "value": True},
                {"entered_cave": False},
            )
        )

    def test_not_equals(self):
        self.assertTrue(
            evaluate_expression(
                {"field": "status", "op": "!=", "value": "dead"}, {"status": "alive"}
            )
        )

    def test_less_than(self):
        self.assertTrue(
            evaluate_expression(
                {"field": "player.health", "op": "<", "value": 5},
                {"player": {"health": 3}},
            )
        )
        self.assertFalse(
            evaluate_expression(
                {"field": "player.health", "op": "<", "value": 5},
                {"player": {"health": 10}},
            )
        )

    def test_all_comparison_operators(self):
        state = {"n": 5}
        self.assertTrue(
            evaluate_expression({"field": "n", "op": "<=", "value": 5}, state)
        )
        self.assertTrue(
            evaluate_expression({"field": "n", "op": ">=", "value": 5}, state)
        )
        self.assertTrue(
            evaluate_expression({"field": "n", "op": ">", "value": 4}, state)
        )

    def test_unsupported_op_raises(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression({"field": "n", "op": "~=", "value": 5}, {"n": 5})

    def test_missing_field_or_op_raises(self):
        with self.assertRaises(ExpressionError):
            evaluate_expression({"op": "=="}, {})
        with self.assertRaises(ExpressionError):
            evaluate_expression({"field": "n"}, {})


class DottedPathTests(unittest.TestCase):
    def test_nested_dotted_path(self):
        state = {"player": {"stats": {"health": 42}}}
        self.assertTrue(
            evaluate_expression(
                {"field": "player.stats.health", "op": "==", "value": 42}, state
            )
        )

    def test_missing_field_resolves_false_not_error(self):
        """A creator condition referencing a game_state field the
        playthrough hasn't touched yet is the common case, not malformed."""
        self.assertFalse(
            evaluate_expression({"field": "player.health", "op": "<", "value": 5}, {})
        )

    def test_missing_intermediate_path_segment_resolves_false(self):
        self.assertFalse(
            evaluate_expression(
                {"field": "player.stats.health", "op": "==", "value": 42},
                {"player": {}},
            )
        )

    def test_non_dict_intermediate_segment_resolves_false_not_crash(self):
        self.assertFalse(
            evaluate_expression(
                {"field": "player.health", "op": "==", "value": 5},
                {"player": "not_a_dict"},
            )
        )


class TypeMismatchTests(unittest.TestCase):
    def test_incomparable_types_resolve_false_not_error(self):
        self.assertFalse(
            evaluate_expression({"field": "n", "op": "<", "value": "five"}, {"n": 3})
        )


class AndOrTests(unittest.TestCase):
    def test_and_both_true(self):
        expr = {
            "field": "player.health",
            "op": "<",
            "value": 5,
            "AND": {"field": "entered_cave", "op": "==", "value": True},
        }
        self.assertTrue(
            evaluate_expression(expr, {"player": {"health": 3}, "entered_cave": True})
        )

    def test_and_second_false_short_circuits_to_false(self):
        expr = {
            "field": "player.health",
            "op": "<",
            "value": 5,
            "AND": {"field": "entered_cave", "op": "==", "value": True},
        }
        self.assertFalse(
            evaluate_expression(expr, {"player": {"health": 3}, "entered_cave": False})
        )

    def test_and_first_false_never_evaluates_second(self):
        expr = {
            "field": "player.health",
            "op": "<",
            "value": 5,
            "AND": {"field": "n", "op": "~=", "value": 1},
        }
        # If AND were evaluated despite the first clause being False, the
        # unsupported op in the second clause would raise.
        self.assertFalse(evaluate_expression(expr, {"player": {"health": 99}}))

    def test_or_first_true_short_circuits(self):
        expr = {
            "field": "player.health",
            "op": "<",
            "value": 5,
            "OR": {"field": "n", "op": "~=", "value": 1},
        }
        self.assertTrue(evaluate_expression(expr, {"player": {"health": 3}}))

    def test_or_first_false_falls_through_to_second(self):
        expr = {
            "field": "player.health",
            "op": "<",
            "value": 5,
            "OR": {"field": "entered_cave", "op": "==", "value": True},
        }
        self.assertTrue(
            evaluate_expression(expr, {"player": {"health": 99}, "entered_cave": True})
        )
        self.assertFalse(
            evaluate_expression(expr, {"player": {"health": 99}, "entered_cave": False})
        )


if __name__ == "__main__":
    unittest.main()
