"""Fixed generic tool set for master-mode Gemini function-calling.

Deliberately generic (not per-scenario dynamic schemas) per the locked
decision — these four tools work against any scenario's state_schema shape.
Discipline against wasteful/trivial calls lives in each description's text,
not a mechanical gate — see docs/specs/master-mode-demo-scenario.md §12 for
a worked example.
"""

from google.genai import types

TOOL_SET_FIELD = types.FunctionDeclaration(
    name="set_field",
    description=(
        "Set a state field to an exact value. Use only when the player's "
        "action would meaningfully and durably change tracked state — never "
        "for flavor/descriptive narration with no lasting effect."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "value": types.Schema(type=types.Type.STRING),
        },
        required=["path", "value"],
    ),
)

TOOL_ADJUST_NUMERIC_FIELD = types.FunctionDeclaration(
    name="adjust_numeric_field",
    description=(
        "Increment or decrement a numeric field by a delta (e.g. damage, "
        "healing, reputation shifts). Use only for a real, consequential "
        "change — not routine flavor. Use a negative delta to decrease."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "delta": types.Schema(type=types.Type.NUMBER),
        },
        required=["path", "delta"],
    ),
)

TOOL_ADD_INVENTORY_ITEM = types.FunctionDeclaration(
    name="add_inventory_item",
    description="Add an obtainable item entity to an inventory list field.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "path": types.Schema(type=types.Type.STRING),
            "entity_id": types.Schema(type=types.Type.STRING),
        },
        required=["path", "entity_id"],
    ),
)

TOOL_ROLL_DICE = types.FunctionDeclaration(
    name="roll_dice",
    description=(
        "Roll dice for a genuinely uncertain, consequential outcome — a real "
        "skill check or contested action. Never for routine or narratively "
        "assured actions."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "sides": types.Schema(type=types.Type.INTEGER),
            "modifier": types.Schema(type=types.Type.INTEGER),
        },
        required=["sides"],
    ),
)

MASTER_MODE_TOOLS = types.Tool(
    function_declarations=[
        TOOL_SET_FIELD,
        TOOL_ADJUST_NUMERIC_FIELD,
        TOOL_ADD_INVENTORY_ITEM,
        TOOL_ROLL_DICE,
    ]
)
