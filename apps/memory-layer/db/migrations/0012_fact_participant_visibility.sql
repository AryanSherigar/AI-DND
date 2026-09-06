-- §5 fix: participant-scoped fact visibility. Same table/pattern
-- `checkpoint`/`when_active` (0010) already established for pre-authored
-- facts -- a fact can optionally be restricted to one participant (e.g. a
-- private clue only one player knows) instead of visible to the whole
-- party. NULL (the default -- unrestricted) behaves exactly as before this
-- column existed.
ALTER TABLE pre_authored_fact_metadata ADD COLUMN visible_to_participant_id TEXT;
