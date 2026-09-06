-- §10 fix: `journal_steps` becomes genuinely append-only. The old unique
-- index enforced "one row per (step_type, idempotency_key) ever" -- a real
-- request fingerprint, not an event identity -- so two distinct calls
-- (different correlation_id/request, or the same prompt legitimately
-- retried twice within one request) that happened to hash to the same
-- fingerprint silently lost every occurrence after the first, with no
-- error. `step_id` (the table's actual PRIMARY KEY, a fresh uuid4 per call)
-- is already a real, collision-free event identity -- StepJournal.record
-- now conflicts on that instead. `idempotency_key` stays indexed (non-
-- unique) for finding "calls that were the same request".
DROP INDEX journal_steps_idempotency_idx;
CREATE INDEX journal_steps_idempotency_idx ON journal_steps (step_type, idempotency_key);
