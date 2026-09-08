"""Phase 2: HydraDB graph expansion (entity links, path structure) plus
bitemporal + chat-TTL filtering of the seeded candidates.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from context_memory.core.config import Config
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.ports import GraphTransport
from context_memory.retrieval.models import DateRange, ScoredFact

logger = get_logger(__name__)


class GraphExpander:
    def __init__(
        self, pool: object, hydra_client: GraphTransport, config: Config | None = None
    ) -> None:
        self._pool = pool
        self._hydra = hydra_client
        self._config = config or Config()
        # Engine-lifetime, not per-call: a fresh ThreadPoolExecutor per `expand()`
        # call tears its worker threads down when the `with` block exits, which
        # also discards HydraHttpTransport's per-thread keep-alive connection
        # cache (`_connections`, thread-local) -- every request then pays a fresh
        # TCP handshake on every one of its ~60-80 node reads instead of just the
        # first. A single long-lived pool reuses the same worker threads (and so
        # the same cached connections) across every `expand()` call this engine
        # instance ever serves.
        self._fetch_executor = ThreadPoolExecutor(
            max_workers=self._config.retrieval_graph_fetch_workers
        )

    def expand(
        self,
        context_id: str,
        seed_facts: dict[str, ScoredFact],
        temporal_bounds: DateRange,
        query_epoch: datetime,
    ) -> dict[str, dict[str, Any]]:
        if not seed_facts:
            return {}

        with timed_operation(
            logger,
            "retrieval.phase2.graph_expansion",
            {"context_id": context_id, "seed_count": len(seed_facts)},
        ) as ctx:
            graph_data = {}

            # Resolve each fact's integer graph_id from Postgres's own
            # graph_id_registry (the same registry ingestion allocated from —
            # this is its intended read side, not a new mechanism): HydraDB's
            # writes only ever match by `id`, and its UNWIND-batched reads
            # turned out just as narrow after four increasingly specific
            # rejections (labeled node patterns rejected, multi-property
            # patterns rejected, bare-scalar UNWIND rejected, and finally
            # "UNWIND batch read first projection must be the source field" —
            # all confirmed live). Rather than keep chasing an UNWIND-read
            # grammar that looks purpose-built for writes only, this queries
            # per-fact instead, matching the original design (docs/decisions.md
            # ADR-033).
            #
            # mem1 gap #46 fix: a bare-digit fid IS already the fact's own
            # graph_id (ingestion.fact_projection.FactProjectionWriter's
            # identity convention for direct-authored/cloned facts -- see its
            # module docstring) -- resolve those directly, with no registry
            # round trip at all, and only send genuinely candidate_id-shaped
            # fids (extraction's convention, never a bare digit string) to
            # the registry lookup below. `graph_id_by_fact_key` keeps the
            # exact same `"fact:" + fid` key shape either way, so every use
            # of it below this point is unchanged.
            graph_id_by_fact_key: dict[str, int] = {}
            registry_lookup_keys = []
            for fid in seed_facts:
                if fid.isdigit():
                    graph_id_by_fact_key[f"fact:{fid}"] = int(fid)
                else:
                    registry_lookup_keys.append(f"fact:{fid}")

            if registry_lookup_keys:
                try:
                    with self._pool.connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT logical_key, graph_id FROM graph_id_registry WHERE node_kind = 'fact' AND context_id = %s AND logical_key = ANY(%s)",
                                (context_id, registry_lookup_keys),
                            )
                            for logical_key, graph_id in cursor.fetchall():
                                graph_id_by_fact_key[logical_key] = int(graph_id)
                except Exception as e:
                    logger.warning("graph_id_registry lookup error: %s", e)

            # 1. Fetch node bitemporal properties plus any connected entity, one
            # fact at a time. A plain (non-UNWIND) MATCH ... OPTIONAL MATCH ...
            # RETURN is fine — only the UNWIND-prefixed combined form was ever
            # rejected.
            #
            # Fetched concurrently, not one HTTP round trip after another: this
            # is a genuine N+1 (one call per seeded fact -- 60-80+ typical, per
            # the overfetch floor/multiplier) and every call is independent and
            # read-only. HydraHttpTransport holds no mutable per-call state (see
            # its own docstring/implementation -- headers/URL are fixed at
            # construction, each .read() is self-contained), so this has none
            # of the shared-connection hazard that keeps ingestion's writes
            # serial (PostgresGraphManifestStore et al. share one psycopg
            # connection; this is a different transport, a different direction
            # -- reads, not writes -- and has no such constraint).
            raw_nodes = []
            entity_key_by_fact: dict[str, str] = {}
            # Consulted by Milestone 1 (structured `/v1/memory/query`), which
            # needs the raw triple-ish fields a fact node already carries but
            # `retrieve_and_answer`'s prose path never surfaced past this phase.
            predicate_key_by_fact: dict[str, str] = {}
            confidence_by_fact: dict[str, float] = {}
            valid_from_by_fact: dict[str, int] = {}
            valid_to_by_fact: dict[str, int] = {}
            # §9 fix: the real triple components a Fact node may carry --
            # `subject`/`object_literal` written by extraction (graph_plan_builder
            # `_fact_node`) or direct authoring (`direct_authoring.write_fact`),
            # and the RELATES_TO-linked object Entity direct authoring writes
            # when the object is a reference rather than a literal. Any of the
            # three can be absent (older data, unresolved subject, extractor
            # left it blank) -- `_to_retrieved_fact` falls back to the
            # ABOUT-entity/full-text behavior it always had.
            subject_by_fact: dict[str, str] = {}
            object_literal_by_fact: dict[str, str] = {}
            object_entity_by_fact: dict[str, str] = {}
            # §5 fix: turn_number per fact, for as_of_turn filtering
            # (retrieval.engine._fact_is_visible) -- absent for anything
            # ingested before §4/§5 (direct-authored facts, older data),
            # which as_of_turn filtering fails open on rather than hiding.
            turn_number_by_fact: dict[str, int] = {}

            def _fetch_node(
                fact_key: str, graph_id: int
            ) -> tuple[str, Sequence[dict[str, object]] | None]:
                # §5 fix: f.turn_number -- real as_of_turn filtering needs the
                # turn a fact was extracted from (graph_plan_builder._fact_node
                # writes it straight from the chunk's own metadata).
                # §6 fix: f.scope_type AS memory_scope -- ingestion writes this
                # property as `scope_type` (graph_plan_builder._fact_node);
                # reading it back as `f.memory_scope` (a property no Fact node
                # has ever carried) meant `memory_scope` below was always None,
                # and the chat-TTL branch a few lines down never ran.
                #
                # NOTE: these two paragraphs used to live as `-- ...` lines
                # INSIDE the Cypher string below. OpenCypher's comment syntax
                # is `//`, not `--`, so they were never comments to HydraDB's
                # parser -- they were invalid query text, and every node read
                # failed with "OpenCypher parse error: Invalid input '<0xC2>'"
                # (the first byte of the UTF-8 encoding of '§', which the
                # parser couldn't tokenize). 100% reproducible, unrelated to
                # connection reuse or concurrency. Keep future annotations
                # about individual RETURN fields up here, never inside the
                # f-string itself.
                node_cypher = f"""
                MATCH (f {{id: {int(graph_id)}}})
                OPTIONAL MATCH (f)-[:ABOUT]->(e)
                OPTIONAL MATCH (f)-[:RELATES_TO]->(o)
                RETURN
                    f.text AS text,
                    f.speaker AS speaker,
                    f.valid_from AS valid_from,
                    f.valid_to AS valid_to,
                    f.observed_at AS observed_at,
                    f.superseded_at AS superseded_at,
                    f.archived AS archived,
                    f.predicate_key AS predicate_key,
                    f.confidence AS confidence,
                    f.subject AS subject,
                    f.object_literal AS object_literal,
                    f.turn_number AS turn_number,
                    f.scope_type AS memory_scope,
                    e.logical_key AS entity_key,
                    o.canonical_name AS object_entity_name
                """
                try:
                    # graph_id is inlined above (int()-coerced, so not injectable);
                    # no parameters remain to bind.
                    return fact_key, self._hydra.read(node_cypher, {}, None)
                except Exception as e:
                    logger.warning("HydraDB node query error for %s: %s", fact_key, e)
                    return fact_key, None

            # Fail-open bookkeeping: a fact whose node read genuinely errors
            # (network blip, transient HydraDB error) should degrade -- stay
            # in the result set with no graph-derived metadata -- rather than
            # silently vanish. One bad read must never cascade into an empty
            # retrieval; see valid_fact_keys union below.
            failed_fetch_fact_keys: set[str] = set()

            futures = [
                self._fetch_executor.submit(_fetch_node, fact_key, graph_id)
                for fact_key, graph_id in graph_id_by_fact_key.items()
            ]
            for future in as_completed(futures):
                fact_key, rows = future.result()
                if rows is None:
                    failed_fetch_fact_keys.add(fact_key)
                    continue
                for row in rows:
                    raw_nodes.append({**row, "fact_key": fact_key})
                    if row.get("entity_key"):
                        entity_key_by_fact[fact_key] = row["entity_key"]

            # Apply Bitemporal filtering in Python
            valid_fact_keys = set()
            entities = set()
            entity_to_facts = {}

            query_int = int(query_epoch.timestamp())
            chat_ttl_limit = int(
                (
                    query_epoch - timedelta(hours=self._config.retrieval_chat_ttl_hours)
                ).timestamp()
            )
            # §7 fix: `temporal_bounds` (Phase 0's resolved [valid_from,
            # valid_to] for the question, e.g. "between turns 20 and 30") used
            # to be passed in and never read below -- every query got only
            # "valid right now" point-in-time filtering, so "what was active
            # between X and Y" silently degraded to "what's active now."
            #
            # window_start/window_end below express the requested interval
            # (open on either side when `None`): when the resolver found NO
            # anchor at all (`temporal_bounds` has neither bound -- the
            # overwhelming majority of questions), both collapse to
            # `query_int`, exactly reproducing the original point-in-time
            # checks. When only one side resolved (e.g. "since last month"),
            # the other defaults to whichever side keeps that meaning: an
            # unbounded past for a bare upper bound, "now" for a bare lower
            # bound (this system has no way to answer about the future).
            has_temporal_anchor = (
                temporal_bounds.valid_from is not None
                or temporal_bounds.valid_to is not None
            )
            if has_temporal_anchor:
                window_start = (
                    int(temporal_bounds.valid_from.timestamp())
                    if temporal_bounds.valid_from
                    else None
                )
                window_end = (
                    int(temporal_bounds.valid_to.timestamp())
                    if temporal_bounds.valid_to
                    else query_int
                )
            else:
                window_start = query_int
                window_end = query_int
            # `observed_at` is when a fact was SAID, not when its event happened
            # -- "I attended a workshop last Saturday" said at 16:55 gets
            # observed_at=16:55, and a question asked earlier the same calendar
            # day (08:02) was treating that as "future" and discarding it.
            # Measured live: up to 74% of one instance's entire fact store
            # wrongly pruned this way (docs/fixes_and_evaluation_findings.md
            # §21/§24). Day-granularity is standard bitemporal practice for
            # exactly this reason, not a special-case hack -- only facts from a
            # LATER calendar day are genuinely future; same-day intra-day
            # ordering in this data is an artifact of session timestamps, not
            # a meaningful chronological signal. valid_from/valid_to/
            # superseded_at are untouched: those encode explicit, intentional
            # world-validity timing (e.g. "moving to Seattle next month"), not
            # a statement-time artifact, so exact-timestamp comparison stays
            # correct for them.
            query_day_end = datetime.combine(
                query_epoch.date(), datetime.max.time(), tzinfo=query_epoch.tzinfo
            )
            observed_future_cutoff = int(query_day_end.timestamp())

            for row in raw_nodes:
                fact_key = row["fact_key"]
                valid_from = row.get("valid_from")
                valid_to = row.get("valid_to")
                observed_at = row.get("observed_at")
                superseded_at = row.get("superseded_at")
                memory_scope = row.get("memory_scope")

                # Phase 6: a rolled-back fact is archived (see persistence/postgres.py's
                # NODE_MUTABLE_PROPERTIES) rather than deleted -- excluded here the same
                # way every other temporal exclusion below is, not a parallel mechanism.
                if row.get("archived"):
                    continue

                # Temporal logic filtering -- interval overlap against the
                # requested window (§7 fix), not a bare "valid right now"
                # point check: fact.valid_from <= window_end AND
                # fact.valid_to >= window_start, each side skipped when that
                # bound is open (None).
                if (
                    valid_from is not None
                    and window_end is not None
                    and valid_from > window_end
                ):
                    continue
                if (
                    valid_to is not None
                    and window_start is not None
                    and valid_to < window_start
                ):
                    continue
                if observed_at is not None and observed_at > observed_future_cutoff:
                    continue
                # A fact already superseded before the window even starts
                # was never true during it. `window_start` is `None` only
                # when the resolved range is open-ended on the past side
                # (e.g. "before June"), which no supersession predates.
                if (
                    superseded_at is not None
                    and window_start is not None
                    and superseded_at < window_start
                ):
                    continue

                # Chat scope TTL enforcement
                if (
                    memory_scope == "chat"
                    and observed_at is not None
                    and observed_at < chat_ttl_limit
                ):
                    continue

                valid_fact_keys.add(fact_key)

                if row.get("predicate_key"):
                    predicate_key_by_fact[fact_key] = str(row["predicate_key"])
                if row.get("confidence") is not None:
                    try:
                        confidence_by_fact[fact_key] = float(row["confidence"])
                    except (ValueError, TypeError):
                        pass
                if valid_from is not None:
                    valid_from_by_fact[fact_key] = int(valid_from)
                if valid_to is not None:
                    valid_to_by_fact[fact_key] = int(valid_to)
                if row.get("subject"):
                    subject_by_fact[fact_key] = str(row["subject"])
                if row.get("object_literal"):
                    object_literal_by_fact[fact_key] = str(row["object_literal"])
                if row.get("object_entity_name"):
                    object_entity_by_fact[fact_key] = str(row["object_entity_name"])
                if row.get("turn_number") is not None:
                    try:
                        turn_number_by_fact[fact_key] = int(row["turn_number"])
                    except (ValueError, TypeError):
                        pass

                # Populate text, speaker, and observed_at on seed_facts
                fid = fact_key.replace("fact:", "", 1)
                if fid in seed_facts:
                    if row.get("text"):
                        seed_facts[fid].text = str(row["text"])
                    if row.get("speaker"):
                        seed_facts[fid].speaker = str(row["speaker"])
                    if observed_at is not None:
                        try:
                            seed_facts[fid].observed_at = int(observed_at)
                        except (ValueError, TypeError):
                            pass

                entity_key = entity_key_by_fact.get(fact_key)
                if entity_key:
                    entities.add(entity_key)
                    entity_to_facts.setdefault(entity_key, []).append(fact_key)

            # Fail open: a fact whose node read errored has no fetched row to
            # apply bitemporal/chat-TTL/archived filtering against -- keep it
            # rather than treat "we couldn't read this" the same as "this
            # failed temporal validation". graph_data's per-fact dicts below
            # already default every graph-derived field via .get(), so a fact
            # with no fetched row degrades gracefully (no entity linking, no
            # bitemporal window applied) rather than erroring.
            valid_fact_keys |= failed_fetch_fact_keys
            ctx["graph_read_failed_facts"] = len(failed_fetch_fact_keys)

            # Prune seed_facts that failed temporal validation
            pruned_count = 0
            for fid in list(seed_facts.keys()):
                if f"fact:{fid}" not in valid_fact_keys:
                    del seed_facts[fid]
                    pruned_count += 1

            ctx["temporal_pruned_facts"] = pruned_count
            ctx["retained_valid_facts"] = len(seed_facts)

            if not seed_facts:
                return {}

            path_count_by_fact = {}
            hop_count_by_fact = {}

            # 2. Execute algo.MSpaths.
            #
            # Values are inlined rather than parameterized because this HydraDB
            # build rejects a list parameter here outright ("composite parameter
            # $entities is only supported as an UNWIND input", confirmed live),
            # so `$entities` is not an option for this call.
            #
            # Escaping via json.dumps, not a hand-rolled quote-doubler. Doubling
            # only `'` leaves backslashes untouched, and an entity ending in one
            # produces `'ent\'` -- the backslash escapes the closing quote, the
            # literal never terminates, and the rest of the query is swallowed.
            # That input is reachable: entity names come from LLM extraction of
            # user content, and `canonicalize_entity_surface` only NFKC-
            # normalizes, collapses whitespace, and casefolds -- it strips
            # neither backslashes nor quotes. json.dumps emits a correctly
            # escaped double-quoted literal, which Cypher accepts.
            if entities:
                escaped_entities = ", ".join(json.dumps(e) for e in entities)
                path_cypher = f"""
                CALL algo.MSpaths({{
                    sourceLabel: 'Entity',
                    sourceProperty: 'logical_key',
                    sourceValues: [{escaped_entities}],
                    relTypes: ['ABOUT'],
                    maxLen: {int(self._config.retrieval_graph_max_hops)}
                }}) YIELD path
                RETURN path
                """
                try:
                    path_res = self._hydra.read(path_cypher, {}, None)
                    for row in path_res:
                        path = row.get("path", [])
                        if len(path) >= 3:
                            # NOTE: path alternates Entity (even index) / Fact (odd
                            # index) -- odd positions are the Fact hops this path
                            # traverses. A compensated/rolled-back Fact is archived,
                            # not deleted (orchestrator._compensate_plan /
                            # rollback.py), so it can still sit on an ABOUT edge here --
                            # ghost connectivity that would otherwise inflate
                            # path_count/hop_count for OTHER, still-valid facts about
                            # the same two entities. Skip any path that hops through
                            # one, same exclusion already applied to seed facts above
                            # (`if row.get("archived"): continue`).
                            interior_archived = any(
                                isinstance(path[idx], dict)
                                and path[idx].get("archived")
                                for idx in range(1, len(path), 2)
                            )
                            if interior_archived:
                                continue

                            hops = len(path) // 2
                            start_node = path[0]
                            end_node = path[-1]

                            start_key = (
                                start_node.get("logical_key")
                                if isinstance(start_node, dict)
                                else None
                            )
                            end_key = (
                                end_node.get("logical_key")
                                if isinstance(end_node, dict)
                                else None
                            )

                            for entity_key in (start_key, end_key):
                                if entity_key in entity_to_facts:
                                    for fact_key in entity_to_facts[entity_key]:
                                        path_count_by_fact[fact_key] = (
                                            path_count_by_fact.get(fact_key, 0) + 1
                                        )
                                        hop_count_by_fact[fact_key] = min(
                                            hop_count_by_fact.get(fact_key, hops), hops
                                        )
                except Exception as e:
                    logger.debug("algo.MSpaths query skipped: %s", e)

            for f_id in seed_facts:
                fact_key = f"fact:{f_id}"
                entity_key = entity_key_by_fact.get(fact_key)
                entity_fact_count = (
                    len(entity_to_facts.get(entity_key, ())) if entity_key else 0
                )
                graph_data[f_id] = {
                    # Carried through so scoring can apply the entity boost only
                    # to entities the *query* actually mentions, per
                    # FINAL_ARCHITECTURE.md's `if entity in query_entities`.
                    "entity_key": entity_key,
                    "hop_count": hop_count_by_fact.get(fact_key, 1),
                    "path_count": path_count_by_fact.get(fact_key, 0),
                    "entity_fact_count": entity_fact_count,
                    "predicate_key": predicate_key_by_fact.get(fact_key),
                    "confidence": confidence_by_fact.get(fact_key),
                    "valid_from": valid_from_by_fact.get(fact_key),
                    "valid_to": valid_to_by_fact.get(fact_key),
                    "subject": subject_by_fact.get(fact_key),
                    "object_literal": object_literal_by_fact.get(fact_key),
                    "object_entity_name": object_entity_by_fact.get(fact_key),
                    "turn_number": turn_number_by_fact.get(fact_key),
                }

            return graph_data
