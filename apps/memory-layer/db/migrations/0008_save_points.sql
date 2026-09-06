CREATE TABLE save_points (
    save_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    session_id TEXT,
    label TEXT,
    cutoff_observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX save_points_context_idx ON save_points (context_id, created_at DESC);
