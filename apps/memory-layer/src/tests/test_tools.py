from __future__ import annotations

import unittest

from context_memory.core.tools import Tool, ToolAnnotations, ToolRegistry


def _echo(args: dict) -> dict:
    return {"echoed": args}


class ToolAnnotationsTests(unittest.TestCase):
    def test_defaults_match_mcp_conservative_posture(self) -> None:
        annotations = ToolAnnotations()
        self.assertFalse(annotations.read_only_hint)
        self.assertTrue(annotations.destructive_hint)
        self.assertFalse(annotations.idempotent_hint)
        self.assertTrue(annotations.open_world_hint)


class ToolRegistryTests(unittest.TestCase):
    def test_register_then_get(self) -> None:
        registry = ToolRegistry()
        tool = Tool(
            name="echo",
            description="Echoes its input.",
            input_schema={"type": "object"},
            handler=_echo,
        )
        registry.register(tool)
        self.assertIs(registry.get("echo"), tool)

    def test_get_unknown_tool_returns_none(self) -> None:
        self.assertIsNone(ToolRegistry().get("nope"))

    def test_list_returns_every_registered_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(
            Tool(name="a", description="", input_schema={}, handler=_echo)
        )
        registry.register(
            Tool(name="b", description="", input_schema={}, handler=_echo)
        )
        self.assertEqual({t.name for t in registry.list()}, {"a", "b"})

    def test_to_openai_tools_renders_the_function_calling_shape(self) -> None:
        registry = ToolRegistry()
        schema = {"type": "object", "properties": {"sides": {"type": "integer"}}}
        registry.register(
            Tool(
                name="roll_dice",
                description="Rolls a die.",
                input_schema=schema,
                handler=_echo,
            )
        )

        rendered = registry.to_openai_tools()

        self.assertEqual(
            rendered,
            [
                {
                    "type": "function",
                    "function": {
                        "name": "roll_dice",
                        "description": "Rolls a die.",
                        "parameters": schema,
                    },
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
