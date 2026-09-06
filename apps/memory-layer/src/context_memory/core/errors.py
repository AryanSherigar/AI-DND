"""Typed errors exposed by the deterministic domain boundary."""


class ContractValidationError(ValueError):
    """Raised when data violates Generic Context Ingestion Contract v1."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


class ImmutableRecordConflictError(ValueError):
    """Raised when one logical record/chunk is replayed with new content."""


class GraphPayloadConflictError(ValueError):
    """Raised when one logical graph record is replayed with changed payload."""


class IllegalJobTransitionError(ValueError):
    """Raised when a job-state transition is not permitted by the M8 state contract."""


class BatchNotFoundError(ValueError):
    """§3 fix: raised for a batch_id no durable `ingestion_batches` row
    exists for -- distinct from a batch that exists but hasn't finished yet
    ("pending" is a real, meaningful status only once the batch is known).
    Routes this into a 404, not an indefinite "pending". Subclasses
    `ValueError`, same as `retry_batch`'s pre-existing unknown-batch_id
    error, so `api/routes.py`'s one `except ValueError -> 404` mapping
    already covers both."""


class ExtractionProviderError(RuntimeError):
    """§2 fix: raised when the extractor's underlying model call itself
    failed (provider timeout, transport error, or a structured response that
    never validated after the client's own retries) -- distinct from a
    genuine "the model looked and found nothing" empty result, which stays a
    normal `()` return, never this.

    Deliberately NOT one of `orchestrator._TERMINAL_ERROR_TYPES`: an
    unclassified exception there already defaults to `RETRYABLE_FAILED`
    (see `orchestrator._record_failure`), which is exactly the right
    classification for a call that may simply succeed on retry -- so this
    type needs no special-casing there, only to actually be raised instead
    of swallowed into `()` at the extractor boundary."""
