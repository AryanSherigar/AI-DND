ALTER TABLE journal_steps ADD COLUMN scenario_id TEXT;
CREATE INDEX journal_steps_scenario_idx ON journal_steps (scenario_id, created_at);
