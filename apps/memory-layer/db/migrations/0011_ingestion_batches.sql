-- §3 fix: durable batch tracking (Milestone 2 of the AI-DND bridge was only
-- ever tracked in MemoryEngine's in-process `_batches` dict -- gone on
-- restart, and `retry_batch`/`get_batch_status` had no way to reconstruct a
-- submitted batch or even know it had ever existed. Per-chunk state already
-- lives durably in `ingestion_jobs` (Milestone 8); this is the missing
-- batch-level layer on top: which chunk_ids belong to which batch_id, and
-- enough of the original submitted payload to replay a retry after a
-- process restart.
CREATE TABLE ingestion_batches (
    batch_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    -- The exact payload needed to reconstruct the submitted `ContextBatch`
    -- (ingestion_id, context_id, source, records) -- see
    -- PostgresBatchStore.get_context_batch.
    submitted_payload JSONB NOT NULL,
    -- Set only when the background run itself raised before producing any
    -- per-chunk results (e.g. the whole orchestrator call blew up) --
    -- per-chunk failures are read from `ingestion_jobs` instead, joined via
    -- `ingestion_batch_chunks`.
    run_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX ingestion_batches_context_idx ON ingestion_batches (context_id);

CREATE TABLE ingestion_batch_chunks (
    batch_id TEXT NOT NULL REFERENCES ingestion_batches (batch_id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    turn_number INTEGER,
    PRIMARY KEY (batch_id, chunk_id)
);
CREATE INDEX ingestion_batch_chunks_batch_idx ON ingestion_batch_chunks (batch_id);
