"""Extensible graph vocabulary — the extension point plugins register against.

STATUS: NOT YET WIRED. `core/graph.py` still validates against its own
``NODE_LABELS``/``RELATIONSHIP_TYPES`` frozensets; nothing imports this module
yet. Wiring it is a planned step (see docs/RESTRUCTURE_PLAN.md). Until then the
security property described below is aspirational, not in force.

Why this exists
---------------
`core/graph.py` hardcodes the legal node labels and relationship types as two
module-level frozensets. That makes the graph schema closed: anything built on
top of this engine (a game layer wanting ``KNOWN_BY``/``WITNESSED_BY`` edges and
``Player``/``NPC``/``Faction`` nodes, say) cannot add to the vocabulary without
editing a core domain file. This module is intended to replace the frozensets
with a registry that core seeds and downstream code extends.

Why registration validates identifier shape (do not remove this)
----------------------------------------------------------------
`ingestion/graph_writer.py` builds OpenCypher by **f-string-interpolating** the
label and relationship type directly into the query text::

    f"... MERGE (s)-[r:{relationship_type} {{id: row.id}}]->(d) SET ..."

Nothing escapes those two values. Today that is safe purely because the closed
frozensets acted as an allowlist of five and eight known-good identifiers. The
moment the vocabulary accepts registrations, **this registry becomes the only
thing standing between a caller-supplied string and injected Cypher.** So
registration enforces a strict identifier grammar (letters, digits, underscore;
must start with a letter; bounded length). A name that cannot pass is rejected at
registration time rather than reaching the query builder.

Threading
---------
Registration is expected at import/startup; reads are hot (every `GraphNode` and
`GraphRelationship` validates against it). Writes take a lock, reads are lock-free
against an immutable snapshot that registration swaps in.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from context_memory.core.errors import ContractValidationError

# Core vocabulary, from the Generic Context Ingestion Contract v1. Plugins add to
# this; nothing may remove from it.
CORE_NODE_LABELS: frozenset[str] = frozenset(
    {"Session", "Turn", "Fact", "Entity", "Alias"}
)
CORE_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "HAS_TURN",
        "EXTRACTED_FROM",
        "ABOUT",
        "HAS_ALIAS",
        "SUPERSEDES",
        "RELATES_TO",
        "STATED_BY",
        "MERGED_INTO",
    }
)

_MAX_IDENTIFIER_LENGTH = 64
# Deliberately strict: no whitespace, quotes, backticks, braces, or punctuation of
# any kind can survive this, which is what keeps the f-string interpolation in
# graph_writer safe. See module docstring.
_NODE_LABEL_GRAMMAR = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_RELATIONSHIP_TYPE_GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*$")


class VocabularyError(Exception):
    """Raised when a registration is rejected. Never raised on lookup."""


@dataclass(frozen=True)
class VocabularyEntry:
    """One registered term, with provenance so `describe()` can generate docs and
    so a collision reports who already owns the name."""

    name: str
    owner: str
    description: str = ""


def _validate(name: str, *, grammar: re.Pattern[str], kind: str, expected: str) -> None:
    if not isinstance(name, str) or not name:
        raise VocabularyError(f"{kind} must be a non-empty string, got {name!r}")
    if len(name) > _MAX_IDENTIFIER_LENGTH:
        raise VocabularyError(
            f"{kind} {name!r} exceeds {_MAX_IDENTIFIER_LENGTH} characters"
        )
    if not grammar.match(name):
        raise VocabularyError(
            f"{kind} {name!r} is not a safe graph identifier ({expected}). "
            "This grammar is what prevents the value from injecting Cypher when "
            "graph_writer interpolates it into a query -- see vocabulary.py."
        )


class GraphVocabulary:
    """Mutable-by-registration, read-optimised set of legal graph terms."""

    def __init__(
        self,
        node_labels: frozenset[str] = CORE_NODE_LABELS,
        relationship_types: frozenset[str] = CORE_RELATIONSHIP_TYPES,
    ) -> None:
        self._lock = threading.Lock()
        self._node_entries: dict[str, VocabularyEntry] = {
            name: VocabularyEntry(
                name, owner="core", description="Context Ingestion Contract v1"
            )
            for name in node_labels
        }
        self._relationship_entries: dict[str, VocabularyEntry] = {
            name: VocabularyEntry(
                name, owner="core", description="Context Ingestion Contract v1"
            )
            for name in relationship_types
        }
        self._node_snapshot: frozenset[str] = frozenset(self._node_entries)
        self._relationship_snapshot: frozenset[str] = frozenset(
            self._relationship_entries
        )

    # -- registration ---------------------------------------------------

    def register_node_label(
        self, name: str, *, owner: str, description: str = ""
    ) -> None:
        """Add a node label. Idempotent for the same owner; raises on a
        cross-owner collision so two plugins cannot silently share a term."""
        _validate(
            name,
            grammar=_NODE_LABEL_GRAMMAR,
            kind="node label",
            expected="must start with an uppercase letter, then letters/digits/underscore",
        )
        self._register(self._node_entries, name, owner, description, kind="node label")
        self._node_snapshot = frozenset(self._node_entries)

    def register_relationship_type(
        self, name: str, *, owner: str, description: str = ""
    ) -> None:
        """Add a relationship type. Same idempotency/collision rules as labels."""
        _validate(
            name,
            grammar=_RELATIONSHIP_TYPE_GRAMMAR,
            kind="relationship type",
            expected="must be UPPER_SNAKE_CASE: uppercase letters, digits, underscore",
        )
        self._register(
            self._relationship_entries,
            name,
            owner,
            description,
            kind="relationship type",
        )
        self._relationship_snapshot = frozenset(self._relationship_entries)

    def _register(
        self,
        target: dict[str, VocabularyEntry],
        name: str,
        owner: str,
        description: str,
        *,
        kind: str,
    ) -> None:
        if not owner:
            raise VocabularyError(f"{kind} {name!r} must declare a non-empty owner")
        with self._lock:
            existing = target.get(name)
            if existing is not None:
                if existing.owner == owner:
                    return  # re-import of the same plugin: no-op
                raise VocabularyError(
                    f"{kind} {name!r} is already registered by {existing.owner!r}; "
                    f"{owner!r} cannot claim it. Choose a distinct, prefixed name."
                )
            target[name] = VocabularyEntry(name, owner=owner, description=description)

    # -- lookup (hot path, no lock) -------------------------------------

    def has_node_label(self, name: str) -> bool:
        return name in self._node_snapshot

    def has_relationship_type(self, name: str) -> bool:
        return name in self._relationship_snapshot

    @property
    def node_labels(self) -> frozenset[str]:
        return self._node_snapshot

    @property
    def relationship_types(self) -> frozenset[str]:
        return self._relationship_snapshot

    # -- introspection --------------------------------------------------

    def describe(self) -> dict[str, list[VocabularyEntry]]:
        """Full registry contents grouped by kind, sorted — used to generate the
        integration docs handed to downstream teams, and useful in a debug endpoint."""
        return {
            "node_labels": sorted(
                self._node_entries.values(), key=lambda e: (e.owner != "core", e.name)
            ),
            "relationship_types": sorted(
                self._relationship_entries.values(),
                key=lambda e: (e.owner != "core", e.name),
            ),
        }

    def reset_to_core(self) -> None:
        """Drop every non-core registration. For test isolation only — production
        code should never need to un-register a term."""
        with self._lock:
            self._node_entries = {
                n: e for n, e in self._node_entries.items() if e.owner == "core"
            }
            self._relationship_entries = {
                n: e for n, e in self._relationship_entries.items() if e.owner == "core"
            }
            self._node_snapshot = frozenset(self._node_entries)
            self._relationship_snapshot = frozenset(self._relationship_entries)


# The process-wide vocabulary that `core/graph.py` validates against.
VOCABULARY = GraphVocabulary()


def require_node_label(name: str, field: str) -> None:
    """Validation helper for the graph dataclasses. Raises the same
    ContractValidationError the closed frozensets used to raise, so callers that
    already handle contract violations are unaffected."""
    if not VOCABULARY.has_node_label(name):
        raise ContractValidationError(
            field,
            f"must be a registered node label (got {name!r}; known: {sorted(VOCABULARY.node_labels)})",
        )


def require_relationship_type(name: str, field: str) -> None:
    if not VOCABULARY.has_relationship_type(name):
        raise ContractValidationError(
            field,
            f"must be a registered relationship type (got {name!r}; "
            f"known: {sorted(VOCABULARY.relationship_types)})",
        )
