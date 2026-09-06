-- AI-DND memory-layer contract handoff (docs/new_mem_api_req.md):
--
-- `hidden` -- an author-marked-secret flag on a pre-authored fact (same
-- table/pattern as checkpoint/when_active/visible_to_participant_id
-- already use). Returned on the wire so the caller's own client-side
-- `revealed_facts` override can act on it; mem1 never filters by it.
ALTER TABLE pre_authored_fact_metadata ADD COLUMN hidden BOOLEAN NOT NULL DEFAULT false;

-- `superseded_fact_id` -- lets a direct-authored (master-mode) fact name
-- the prior fact it replaces, using the CALLER's own opaque fact id (mem1
-- otherwise only knows facts by a content-derived graph_id/logical_key,
-- which the caller never sees or assigns). This is the lookup table that
-- makes that resolvable: same role `graph_id_registry` already plays for
-- logical keys, scoped instead to the caller's own external identifiers.
-- `logical_key` is stored alongside `graph_id` (not just the id alone)
-- because updating an already-registered graph node -- to flip
-- is_current/superseded_at/valid_to when it gets superseded -- requires
-- reusing that node's own original logical_key; the manifest store keys
-- its immutable-payload check on (record_kind, context_id, logical_key),
-- not on graph_id alone, and a direct-authored fact's real logical_key
-- (a content hash of its original subject/predicate/object) can't be
-- reconstructed from the external_fact_id alone.
CREATE TABLE external_fact_ids (
    context_id TEXT NOT NULL,
    external_fact_id TEXT NOT NULL,
    graph_id INTEGER NOT NULL,
    logical_key TEXT NOT NULL,
    PRIMARY KEY (context_id, external_fact_id)
);
