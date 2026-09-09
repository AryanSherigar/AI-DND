"""Direct (no-LLM-extraction) graph writes for master-mode scenario authoring
-- Milestone 3a of the AI-DND bridge.

AI-DND's master mode is fully manual and structured: a creator specifies
Entities and Facts precisely through the Studio editor, and per the RFC's own
stated trust guarantee ("the system will not reinterpret your world"), that
input must map onto mem1's graph directly -- running it through the same LLM
extractor `ExtractionService` uses for newbie-mode prose would risk
reinterpreting something the creator specified exactly.

This reuses the same graph primitives extraction already writes with
(`GraphNode`/`GraphRelationship`/`GraphWritePlan`, `GraphWriter`, the
Postgres-backed `graph_id_registry` allocator) so retrieval (Milestone 1)
sees a direct-authored fact exactly the same shape as an extracted one --
no special-casing needed downstream.

Identifier note (flagged, not hidden): entities here are identified by
`canonical_name`, the same as extraction's `entity:{canonical_name}` logical
key -- not by AI-DND's own opaque `entity_id` primary key. A Fact's subject/
object is looked up by name, so the caller (Core API's direct-authoring
route) is expected to resolve its own `entity_id` to `canonical_name` before
calling this -- it already holds that mapping in its own `world_data`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from context_memory.core.graph import GraphNode, GraphRelationship, GraphWritePlan
from context_memory.ingestion.alias_records import alias_records
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.ports import GraphIdAllocator


class FactMetadataStore(Protocol):
    """Duck-typed to `persistence.postgres.PostgresFactMetadataStore` -- see
    `cloning.template_clone.FactMetadataStore`'s docstring for why this is a
    locally-declared Protocol rather than an import from `persistence`."""

    def put(
        self,
        context_id: str,
        fact_id: int,
        checkpoint: str | None,
        when_active: dict | None,
        visible_to_participant_id: str | None = None,
        hidden: bool = False,
    ) -> None: ...


class ExternalFactIdStore(Protocol):
    """AI-DND memory-layer contract: resolves the CALLER's own opaque
    `fact_id` to the graph identity mem1 actually wrote it under. Needed
    only for `DirectFactInput.superseded_fact_id` -- direct-authored facts
    are otherwise identified purely by a content hash of their own triple
    (`_fact_logical_key`), which the caller never sees or assigns, so
    there's no other way for a later fact to reference an earlier one by
    the id the caller actually holds."""

    def get(self, context_id: str, external_fact_id: str) -> tuple[int, str] | None:
        """Returns `(graph_id, logical_key)`, or `None` if never registered."""
        ...

    def put(
        self, context_id: str, external_fact_id: str, graph_id: int, logical_key: str
    ) -> None: ...

    def get_all_for_context(self, context_id: str) -> list[tuple[str, int, str]]:
        """Every `(external_fact_id, graph_id, logical_key)` row for one
        context -- used by `cloning.template_clone` to remap and copy
        these rows into a cloned playthrough context (NEW-HIGH-01)."""
        ...


class FactProjector(Protocol):
    """Duck-typed to `ingestion.fact_projection.FactProjectionWriter` -- kept
    as a locally-declared Protocol for the same reason `FactMetadataStore`/
    `ExternalFactIdStore` above are: this module depends only on the one
    method shape it needs, not on fact_projection.py's own internals."""

    def project(self, context_id: str, fact_graph_id: int, text: str) -> None: ...


_OPEN_ENDED_VALID_TO = 9999999999
_NO_LOWER_BOUND_VALID_FROM = 0
# Creator-authored facts are ground truth, not an LLM's extraction guess --
# 1.0 is a deliberate default, not a placeholder standing in for a real score.
_DIRECT_AUTHORING_CONFIDENCE = 1.0


@dataclass(frozen=True)
class DirectEntityInput:
    canonical_name: str
    entity_type: str
    aliases: tuple[str, ...] = ()
    description: str | None = None


@dataclass(frozen=True)
class DirectFactInput:
    predicate: str
    subject_canonical_name: str
    object_canonical_name: str | None = None
    object_literal: str | None = None
    valid_from: datetime | None = None
    # ADR-9 (`when_active`) and checkpoint-scoped visibility (Milestones 4-5):
    # carried through here so the caller has one write path.
    when_active: dict | None = None
    checkpoint: str | None = None
    # §5 fix: optional participant-scoped visibility (e.g. a private clue
    # only one player knows) -- None (default) is unrestricted, same as
    # every fact before this field existed.
    visible_to_participant_id: str | None = None
    # AI-DND memory-layer contract: author-marked secret. mem1 never filters
    # on this -- it's returned as-is so the caller's own client-side
    # `revealed_facts` override can act on it (see FactMetadataStore).
    hidden: bool = False
    # AI-DND memory-layer contract: this fact's own caller-assigned id (so a
    # LATER fact's `superseded_fact_id` can reference it), and/or the id of
    # the prior fact THIS one supersedes. Independent of each other --
    # a fact can register an external_fact_id without superseding anything,
    # or supersede a prior fact without other facts ever superseding it in
    # turn.
    external_fact_id: str | None = None
    superseded_fact_id: str | None = None

    def __post_init__(self) -> None:
        if not self.object_canonical_name and self.object_literal is None:
            raise ValueError(
                "DirectFactInput requires object_canonical_name or object_literal"
            )


def write_entity(
    context_id: str,
    entity: DirectEntityInput,
    allocator: GraphIdAllocator,
    graph_writer: GraphWriter,
) -> int:
    """Direct-writes one Entity node (plus, when aliases are given, Alias
    nodes/HAS_ALIAS edges matching the extraction path's own shape -- see
    `alias_records`). Returns its graph_id.

    NEW-HIGH-03 fix: the flat comma-joined `aliases` property on the Entity
    node itself is ALSO still written -- `MemoryEngine.get_entity` reads it
    directly and would otherwise regress -- but it's no longer the only
    place aliases live. `entity_hydration.HydraEntityHydrator` reads only
    HAS_ALIAS edges, which previously didn't exist for direct-authored
    entities at all, silently dropping their aliases on every rehydration."""
    logical_key = f"entity:{entity.canonical_name}"
    graph_id = allocator.allocate_graph_id("entity", context_id, logical_key)
    node = GraphNode(
        graph_id,
        "Entity",
        logical_key,
        _properties(
            context_id,
            logical_key=logical_key,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            description=entity.description,
            aliases=", ".join(entity.aliases) if entity.aliases else None,
        ),
    )
    alias_nodes_and_edges = alias_records(
        context_id, graph_id, entity.aliases, allocator
    )
    nodes = (node,) + tuple(alias_node for alias_node, _ in alias_nodes_and_edges)
    relationships = tuple(has_alias for _, has_alias in alias_nodes_and_edges)
    plan = GraphWritePlan(
        context_id=context_id,
        plan_key=f"plan:direct-entity:{logical_key}",
        nodes=nodes,
        relationships=relationships,
    )
    graph_writer.write(plan)
    return graph_id


def write_fact(
    context_id: str,
    fact: DirectFactInput,
    allocator: GraphIdAllocator,
    graph_writer: GraphWriter,
    fact_metadata_store: FactMetadataStore | None = None,
    external_fact_id_store: ExternalFactIdStore | None = None,
    fact_projector: FactProjector | None = None,
) -> int:
    """Direct-writes one Fact node plus its ABOUT edge to the subject entity
    (and a RELATES_TO edge to the object entity, when the object is a
    reference rather than a literal). The intended calling order creates both
    subject and object entities first (`write_entity`), but this function
    does not depend on that order: it also puts a same-`plan` stub Entity
    node (`logical_key`/`canonical_name`/`context_id` only) into `plan.nodes`
    for each reference. `GraphWriter.write()` writes every node bucket before
    any relationship bucket, so the ABOUT/RELATES_TO edge's `MATCH` always
    has an `(Entity {id: ...})` to find -- HIGH-10 fix: without this, a fact
    authored before its entity (or a typo'd `canonical_name`) hit HydraDB's
    `UNWIND ... MATCH ... MERGE` silently producing zero rows for that
    edge, since a failed `MATCH` short-circuits `MERGE` with no error. A
    stub for an entity that was already `write_entity`'d is a harmless
    no-op: `MERGE (n {id: row.id})` matches the existing node by id, and the
    stub's `SET` only ever touches `logical_key`/`canonical_name`/
    `context_id`, never `entity_type`/`description`/`aliases`, so a real
    entity's own fields are never clobbered back to stub values.

    `fact_metadata_store`, when given, persists `fact.when_active`/
    `fact.checkpoint`/`fact.visible_to_participant_id`/`fact.hidden` --
    graph node properties are scalar-only, so none of those ever make it
    into `fact_node` itself.

    `external_fact_id_store`, when given, registers `fact.external_fact_id`
    (so a later fact can supersede this one by the caller's own id) and
    resolves `fact.superseded_fact_id` into a real `SUPERSEDES` edge plus
    the same is_current/superseded_at/valid_to closing extraction's own
    supersession already applies (`graph_plan_builder.py`'s SUPERSEDES
    handling) -- direct authoring never had a path onto that machinery
    before this. An unresolvable `superseded_fact_id` raises rather than
    silently no-op'ing: this module's whole contract is that creator input
    is taken exactly as given, so a reference to a fact that doesn't exist
    is the creator's own bug to surface, not mem1's to quietly absorb.
    """
    fact_key = _fact_logical_key(context_id, fact)
    fact_graph_id = allocator.allocate_graph_id("fact", context_id, fact_key)
    subject_key = f"entity:{fact.subject_canonical_name}"
    subject_graph_id = allocator.allocate_graph_id("entity", context_id, subject_key)

    display_text = f"{fact.subject_canonical_name} {fact.predicate} {fact.object_canonical_name or fact.object_literal}"
    v_from = (
        int(fact.valid_from.timestamp())
        if fact.valid_from
        else _NO_LOWER_BOUND_VALID_FROM
    )

    fact_node = GraphNode(
        fact_graph_id,
        "Fact",
        fact_key,
        _properties(
            context_id,
            logical_key=fact_key,
            text=display_text,
            predicate_key=fact.predicate,
            confidence=_DIRECT_AUTHORING_CONFIDENCE,
            valid_from=v_from,
            valid_to=_OPEN_ENDED_VALID_TO,
            observed_at=v_from,
            superseded_at=_OPEN_ENDED_VALID_TO,
            is_current=True,
            # Explicit rather than left unset: HydraDB's Cypher subset has no
            # coalesce()/IS NULL support, so template_clone's WHERE clause can
            # only compare this property directly against a literal -- a
            # fact with no `archived` property at all would never match
            # `n.archived = false` and would silently drop out of every clone.
            archived=False,
            object_literal=fact.object_literal,
        ),
    )
    about_edge = GraphRelationship(
        allocator.allocate_graph_id("about", context_id, f"about:{fact_key}"),
        "ABOUT",
        f"about:{fact_key}",
        fact_graph_id,
        subject_graph_id,
        "Fact",
        "Entity",
        _properties(context_id),
    )
    nodes = [
        fact_node,
        _stub_entity_node(
            context_id, subject_key, subject_graph_id, fact.subject_canonical_name
        ),
    ]
    relationships = [about_edge]
    if fact.object_canonical_name:
        object_key = f"entity:{fact.object_canonical_name}"
        object_graph_id = allocator.allocate_graph_id("entity", context_id, object_key)
        nodes.append(
            _stub_entity_node(
                context_id, object_key, object_graph_id, fact.object_canonical_name
            )
        )
        relationships.append(
            GraphRelationship(
                allocator.allocate_graph_id(
                    "relates_to", context_id, f"relates_to:{fact_key}"
                ),
                "RELATES_TO",
                f"relates_to:{fact_key}",
                fact_graph_id,
                object_graph_id,
                "Fact",
                "Entity",
                _properties(context_id),
            )
        )

    if fact.superseded_fact_id is not None:
        if external_fact_id_store is None:
            raise ValueError(
                "superseded_fact_id given but no external_fact_id_store configured"
            )
        prior = external_fact_id_store.get(context_id, fact.superseded_fact_id)
        if prior is None:
            raise ValueError(
                f"superseded_fact_id {fact.superseded_fact_id!r} does not resolve to a known fact"
            )
        prior_graph_id, prior_logical_key = prior
        if prior_graph_id == fact_graph_id:
            raise ValueError(
                f"fact {fact_key!r} resolves to same graph_id as the fact it "
                f"supersedes ({fact.superseded_fact_id!r}) -- refusing to self-supersede"
            )
        supersedes_key = f"supersedes:{fact_key}:{prior_graph_id}"
        relationships.append(
            GraphRelationship(
                allocator.allocate_graph_id("supersedes", context_id, supersedes_key),
                "SUPERSEDES",
                supersedes_key,
                fact_graph_id,
                prior_graph_id,
                "Fact",
                "Fact",
                _properties(context_id),
            )
        )
        # Precedence rule from the AI-DND handoff doc: supersession is
        # authoritative over currency -- closing the prior fact's validity
        # at this fact's own valid_from, same as extraction's own
        # supersession closing (graph_plan_builder.py), regardless of
        # whatever `when_active` the prior fact may still carry.
        nodes.append(
            GraphNode(
                prior_graph_id,
                "Fact",
                prior_logical_key,
                _properties(
                    context_id,
                    logical_key=prior_logical_key,
                    is_current=False,
                    superseded_at=v_from,
                    valid_to=v_from,
                ),
            )
        )

    plan = GraphWritePlan(
        context_id=context_id,
        plan_key=f"plan:direct-fact:{fact_key}",
        nodes=tuple(nodes),
        relationships=tuple(relationships),
    )
    graph_writer.write(plan)

    # mem1 gap #46 fix: without this, `fact_node` above is durable in
    # HydraDB but CandidateSeeder.seed() -- which starts retrieval only from
    # memory_embeddings/fact_search_index -- can never find it. See
    # ingestion.fact_projection's module docstring for the identity
    # convention (fact_graph_id, not fact_key) this relies on.
    if fact_projector is not None:
        fact_projector.project(context_id, fact_graph_id, display_text)

    if external_fact_id_store is not None and fact.external_fact_id is not None:
        external_fact_id_store.put(
            context_id, fact.external_fact_id, fact_graph_id, fact_key
        )

    has_metadata = (
        fact.when_active is not None
        or fact.checkpoint is not None
        or fact.visible_to_participant_id is not None
        or fact.hidden
    )
    if fact_metadata_store is not None and has_metadata:
        fact_metadata_store.put(
            context_id,
            fact_graph_id,
            fact.checkpoint,
            fact.when_active,
            fact.visible_to_participant_id,
            fact.hidden,
        )

    return fact_graph_id


def _fact_logical_key(context_id: str, fact: DirectFactInput) -> str:
    # Deterministic, not caller-supplied -- two authoring calls describing the
    # identical triple collapse onto the same fact instead of duplicating it,
    # the same MERGE-by-logical-key idempotency extraction's facts already get.
    #
    # NOTE: a fact that supersedes a prior one salts the hash with
    # `superseded_fact_id`. Without this, a correction that keeps the same
    # (subject, predicate, object) triple -- only `valid_from`, `checkpoint`,
    # or visibility changed -- would hash to the SAME fact_key/graph_id as
    # the fact it's replacing. That collapses the new SUPERSEDES edge and the
    # prior-fact close-out onto one node: the new fact overwrites itself with
    # `is_current=False` and vanishes from active memory (HIGH-09).
    object_part = fact.object_canonical_name or fact.object_literal
    raw = f"{fact.subject_canonical_name}\x00{fact.predicate}\x00{object_part}"
    if fact.superseded_fact_id is not None:
        raw = f"{raw}\x00supersedes\x00{fact.superseded_fact_id}"
    return f"fact:direct:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _stub_entity_node(
    context_id: str, logical_key: str, graph_id: int, canonical_name: str
) -> GraphNode:
    """HIGH-10 fix: a minimal Entity node so `write_fact`'s ABOUT/RELATES_TO
    edges always have a match target in the same write, even when the real
    `write_entity` call for this name hasn't happened yet (or never will,
    e.g. a typo). Deliberately omits `entity_type`/`description`/`aliases`
    so it never overwrites those fields on an already-authored entity --
    see `write_fact`'s docstring."""
    return GraphNode(
        graph_id,
        "Entity",
        logical_key,
        _properties(context_id, logical_key=logical_key, canonical_name=canonical_name),
    )


def _properties(context_id: str, **fields: object) -> dict[str, object]:
    properties: dict[str, object] = {"context_id": context_id}
    for key, value in fields.items():
        if value is None:
            continue
        properties[key] = value
    return properties
