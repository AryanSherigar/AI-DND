CREATE TABLE journal_steps (
    step_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    context_id TEXT,
    session_id TEXT,
    turn_index INTEGER,
    step_type TEXT NOT NULL,
    call_role TEXT,
    idempotency_key TEXT NOT NULL,
    model_name TEXT,
    request_payload JSONB NOT NULL,
    response_payload JSONB,
    outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'error')),
    error_message TEXT,
    elapsed_ms DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX journal_steps_correlation_idx ON journal_steps (correlation_id, created_at);
CREATE INDEX journal_steps_context_idx ON journal_steps (context_id, session_id, turn_index);
CREATE UNIQUE INDEX journal_steps_idempotency_idx ON journal_steps (step_type, idempotency_key);
