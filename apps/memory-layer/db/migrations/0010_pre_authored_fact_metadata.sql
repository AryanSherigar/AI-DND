-- Milestones 4-5 of the AI-DND bridge (ADR-9 `when_active`, checkpoint-scoped
-- visibility). Graph node properties are scalar-only (core/graph.py) and
-- can't hold a nested expression tree, so pre-authored facts' `when_active`/
-- `checkpoint` live here instead, keyed by the same integer graph_id
-- fact_search_index already uses as its own fact_id -- same split this
-- codebase already made once (structured/queryable metadata in Postgres,
-- graph traversal in HydraDB).
CREATE TABLE pre_authored_fact_metadata (
    fact_id INTEGER PRIMARY KEY,
    context_id TEXT NOT NULL,
    checkpoint TEXT,
    when_active JSONB
);
CREATE INDEX pre_authored_fact_metadata_context_idx ON pre_authored_fact_metadata (context_id);

-- The ordered checkpoint list a scenario's facts are authored against.
-- Written once at template-ingest time (master mode); a bare `checkpoint`
-- string on a MemoryQueryRequest is otherwise just an opaque label mem1 has
-- no ordering for.
CREATE TABLE scenario_template_checkpoints (
    context_id TEXT PRIMARY KEY,
    checkpoints JSONB NOT NULL
);
