"""Real (non-fake) implementations of the bounded LLM ports (ADR-027).

Both adapters only ever return a value the caller independently re-validates:
`EntityRegistry.resolve` rejects any `selected_graph_id` outside the supplied
candidate set (never trusted here), and `TemporalUpdateClassifier.classify`
only calls `classify_update` after same-subject/predicate/chronology gates
already passed. An adapter cannot widen either boundary; it can only narrow
to `UNRESOLVED`/`None` on invalid or abstaining model output.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel

from context_memory.core.config import Config
from context_memory.core.errors import ExtractionProviderError
from context_memory.core.llm_client import LLMClient, LLMClientError
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.resolution import EntityProfile, FactState, TemporalRelation

logger = get_logger(__name__)


class _EntityResolutionResponse(BaseModel):
    selected_graph_id: int | None


class _TemporalUpdateResponse(BaseModel):
    relation: Literal["correction", "state_change", "no_update", "unresolved"]


class _BatchedTemporalUpdateItem(BaseModel):
    idx: int
    relation: Literal["correction", "state_change", "no_update", "unresolved"]


class _BatchedTemporalUpdateResponse(BaseModel):
    results: list[_BatchedTemporalUpdateItem] = []


class _BatchedEntityResolutionItem(BaseModel):
    idx: int
    selected_graph_id: int | None = None


class _BatchedEntityResolutionResponse(BaseModel):
    results: list[_BatchedEntityResolutionItem] = []


def _format_candidates(candidates: Sequence[EntityProfile]) -> str:
    lines = []
    for profile in candidates:
        aliases = ", ".join(profile.aliases) if profile.aliases else "(none)"
        lines.append(
            f"- graph_id={profile.graph_id}: name={profile.canonical_name!r} "
            f"type={profile.entity_type!r} aliases=[{aliases}]"
        )
    return "\n".join(lines)


class LLMEntityResolutionModel:
    """`ingestion.ports.EntityResolutionModel` backed by a real LLM call."""

    def __init__(self, client: LLMClient, config: Config | None = None) -> None:
        self._client = client
        self._config = config or Config()

    def resolve_entity(
        self, *, context_id: str, surface: str, candidates: Sequence[EntityProfile]
    ) -> int | None:
        if not candidates:
            return None
        with timed_operation(logger, "entity_resolution.disambiguate", {"surface": surface, "candidates_count": len(candidates)}) as ctx:
            user_prompt = (
                f"Surface form to resolve: {surface!r}\n\n"
                f"Candidates (context {context_id!r}):\n{_format_candidates(candidates)}\n\n"
                "Return the graph_id of the matching candidate, or null if none match."
            )
            try:
                result = self._client.structured_completion(
                    self._config.entity_resolution_system_prompt, user_prompt, _EntityResolutionResponse,
                    temperature=self._config.llm_temperature, max_tokens=self._config.entity_resolution_max_tokens,
                    timeout=self._config.entity_resolution_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
                ctx["selected_id"] = result.selected_graph_id
                return result.selected_graph_id
            except Exception as error:
                # Was `except LLMClientError` only, which does not catch
                # openai.APITimeoutError (a different exception hierarchy) --
                # confirmed live: a single slow call propagated straight out of
                # this bounded-decision port, past graph_plan_builder's loop,
                # and aborted the *entire chunk* via orchestrator.run_chunk's
                # generic except, losing every fact in that turn over one
                # resolution timing out. This port's contract is already
                # "return None on any doubt" (EntityRegistry.resolve treats
                # UNRESOLVED as no-forced-link, never invents a candidate); a
                # provider timeout is exactly that kind of doubt.
                logger.warning("Entity resolution model error for surface %r: %s", surface, error)
                return None

    def resolve_entities(
        self, *, context_id: str, mentions: Sequence[tuple[str, Sequence[EntityProfile]]]
    ) -> dict[int, int | None]:
        """One call resolving every mention in `mentions` (each `(surface,
        candidates)`), keyed by index. A missing/invalid index degrades to
        `None` for that mention only, same as a resolve_entity() error --
        never invents an id outside that mention's own candidate list
        (`EntityRegistry.resolve_many` re-validates this boundary regardless,
        same as every other port here)."""
        if not mentions:
            return {}
        blocks = []
        for i, (surface, candidates) in enumerate(mentions):
            blocks.append(
                f"--- Mention {i} ---\nSurface form: {surface!r}\nCandidates:\n{_format_candidates(candidates)}"
            )
        user_prompt = "\n\n".join(blocks) + "\n\nResolve each mention above:"
        max_tokens = self._config.entity_resolution_batch_max_tokens_for(len(mentions))

        with timed_operation(
            logger, "entity_resolution.disambiguate_batch",
            {"mentions": len(mentions), "max_tokens": max_tokens},
        ) as ctx:
            try:
                result = self._client.structured_completion(
                    self._config.batched_entity_resolution_system_prompt, user_prompt, _BatchedEntityResolutionResponse,
                    temperature=self._config.llm_temperature, max_tokens=max_tokens,
                    timeout=self._config.entity_resolution_batch_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as error:
                logger.warning("Batched entity resolution error for %d mentions: %s", len(mentions), error)
                ctx["resolved"] = 0
                return {}

            resolved: dict[int, int | None] = {}
            for item in result.results:
                if 0 <= item.idx < len(mentions):
                    resolved[item.idx] = item.selected_graph_id
            ctx["resolved"] = len(resolved)
            return resolved


class LLMTemporalUpdateModel:
    """`ingestion.ports.TemporalUpdateModel` backed by a real LLM call."""

    def __init__(self, client: LLMClient, config: Config | None = None) -> None:
        self._client = client
        self._config = config or Config()

    def classify_update(self, *, new_fact: FactState, prior_fact: FactState) -> TemporalRelation:
        with timed_operation(logger, "temporal_update.classify", {"predicate": new_fact.predicate_key, "prior_id": prior_fact.fact_id, "new_id": new_fact.fact_id}) as ctx:
            user_prompt = (
                f"Prior fact (observed {prior_fact.observed_at.isoformat()}): {prior_fact.text!r}\n"
                f"New fact (observed {new_fact.observed_at.isoformat()}): {new_fact.text!r}\n\n"
                "Classify the relationship: correction, state_change, no_update, or unresolved."
            )
            try:
                result = self._client.structured_completion(
                    self._config.temporal_update_system_prompt, user_prompt, _TemporalUpdateResponse,
                    temperature=self._config.llm_temperature, max_tokens=self._config.temporal_update_max_tokens,
                    timeout=self._config.temporal_update_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
                ctx["classified_relation"] = result.relation
                return TemporalRelation(result.relation)
            except Exception as error:
                # Was `except LLMClientError` only. Confirmed live during a
                # 30-instance demo run: openai.APITimeoutError from Bedrock
                # propagated straight out of this bounded-decision port and
                # aborted the whole chunk via orchestrator.run_chunk's generic
                # except -- 42 timeouts in one instance, each one losing every
                # fact in that turn (not just the one supersession check) and
                # costing up to timeout x (sdk_max_retries+1) of wall clock
                # before the exception even surfaced. UNRESOLVED is this
                # port's existing "no clear basis to decide" outcome
                # (TemporalUpdateClassifier gates SUPERSEDES on
                # CORRECTION/STATE_CHANGE only), so a provider timeout
                # degrading to it is the contract working as designed, not a
                # new behavior.
                logger.warning("Temporal update classification error: %s", error)
                return TemporalRelation.UNRESOLVED

    def classify_updates(self, *, new_fact: FactState, prior_facts: Sequence[FactState]) -> dict[int, TemporalRelation]:
        """One call classifying `new_fact` against every prior, keyed by prior index.

        Missing/invalid indices degrade to UNRESOLVED for that prior only, which
        `TemporalUpdateClassifier` already treats as "no basis to supersede".
        """
        if not prior_facts:
            return {}
        max_tokens = self._config.temporal_update_batch_max_tokens_for(len(prior_facts))
        with timed_operation(
            logger, "temporal_update.classify_batch",
            {"priors": len(prior_facts), "predicate": new_fact.predicate_key, "new_id": new_fact.fact_id},
        ) as ctx:
            priors_block = "\n".join(
                f"idx={i} (observed {p.observed_at.isoformat()}): {p.text!r}" for i, p in enumerate(prior_facts)
            )
            user_prompt = (
                f"New fact (observed {new_fact.observed_at.isoformat()}): {new_fact.text!r}\n\n"
                f"Prior facts:\n{priors_block}\n\n"
                f"Classify the new fact against each of the {len(prior_facts)} prior facts above."
            )
            try:
                result = self._client.structured_completion(
                    self._config.batched_temporal_update_system_prompt, user_prompt, _BatchedTemporalUpdateResponse,
                    temperature=self._config.llm_temperature, max_tokens=max_tokens,
                    timeout=self._config.temporal_update_batch_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as error:
                logger.warning("Batched temporal update classification error: %s", error)
                ctx["classified"] = 0
                return {}

            relations: dict[int, TemporalRelation] = {}
            for item in result.results:
                if 0 <= item.idx < len(prior_facts):
                    relations[item.idx] = TemporalRelation(item.relation)
            ctx["classified"] = len(relations)
            return relations


class _ExtractedFactItem(BaseModel):
    text: str
    action: Literal["ADD", "UPDATE", "DELETE"] = "ADD"
    predicate_key: str | None = None
    entities: list[str] = []
    confidence: float = 0.95
    exact_quote: str | None = None
    # Real triple components (§9 fix): normalized subject/object, distinct
    # from `text` (the full sentence, kept as evidence regardless). Optional
    # -- a missing/blank value degrades to the pre-existing entity-derived/
    # full-sentence fallback in retrieval, never a hard failure.
    subject: str = ""
    object: str = ""


class _FactExtractionResponse(BaseModel):
    facts: list[_ExtractedFactItem] = []


class _BatchedTurnFacts(BaseModel):
    turn_index: int
    facts: list[_ExtractedFactItem] = []


class _BatchedFactExtractionResponse(BaseModel):
    turns: list[_BatchedTurnFacts] = []


class LLMExtractor:
    """`ingestion.ports.Extractor` backed by structured LLM fact distillation."""

    extractor_name = "llm-extractor"
    extractor_version = "v1"

    def __init__(self, client: LLMClient, config: Config | None = None) -> None:
        self._client = client
        self._config = config or Config()

    @staticmethod
    def _build_drafts(content: str, items: Sequence[_ExtractedFactItem]) -> list[Any]:
        """Shared by `extract()` and `extract_batch()`: turns parsed fact items
        plus the ONE turn's own content string into `ExtractionDraft`s, computing
        source_span offsets against that content. Kept as one place so the batched
        path can never drift from the unbatched path's attribution logic.
        """
        import uuid
        from context_memory.core.enums import MemoryScope, MemoryType
        from context_memory.core.models import EntityCandidate, ExtractionDraft

        drafts: list[ExtractionDraft] = []
        for item in items:
            if not item.text or not item.text.strip():
                continue
            # Calculate source span offsets
            quote = item.exact_quote or item.text
            start = content.find(quote)
            if start == -1:
                start = 0
                end = len(content)
            else:
                end = start + len(quote)

            if end <= start:
                end = max(len(content), start + 1)

            entities = tuple(EntityCandidate(surface=e.strip(), entity_type=None) for e in item.entities if e.strip())
            draft = ExtractionDraft(
                candidate_id=f"cand-{uuid.uuid4().hex[:12]}",
                text=item.text.strip(),
                source_start=start,
                source_end=end,
                confidence=max(0.0, min(1.0, float(item.confidence))),
                memory_type=MemoryType.SEMANTIC,
                scope_type=MemoryScope.USER,
                scope_id="user",
                entities=entities,
                action=item.action,
                predicate_key=item.predicate_key,
                subject=item.subject.strip() or None,
                object=item.object.strip() or None,
            )
            drafts.append(draft)
        return drafts

    def extract(self, record: ContextRecord) -> Sequence[ExtractionDraft]:
        content = record.content
        if not content or not content.strip():
            return ()

        # Multi-stage max_tokens gateway (Config.extraction_max_tokens_for)
        # instead of one flat ceiling for every call -- picks the smallest
        # tier that still covers this turn's length, so a typical short turn
        # no longer pays the same allocation as the rare, genuinely long one,
        # while the long tail gets more headroom than the old flat cap gave
        # it (see config.py's field comment for the measured percentiles and
        # docs/fixes_and_evaluation_findings.md §3 for the reasoning).
        max_tokens = self._config.extraction_max_tokens_for(len(content))
        with timed_operation(logger, "extractor.extract", {"record_id": record.record_id, "content_len": len(content), "max_tokens": max_tokens}) as ctx:
            user_prompt = f"Speaker: {record.actor_role}\nContent: {content}\n\nExtract atomic facts:"
            try:
                res = self._client.structured_completion(
                    self._config.fact_extraction_system_prompt, user_prompt, _FactExtractionResponse,
                    temperature=self._config.llm_temperature, max_tokens=max_tokens,
                    timeout=self._config.extractor_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as e:
                logger.error("LLMExtractor failed structured extraction for record %s: %s", record.record_id, e)
                # §2 fix: was `return ()` -- indistinguishable downstream from
                # "the model looked and genuinely found nothing," so the
                # chunk sailed through to COMPLETED with zero facts and no
                # trace the extractor call itself never succeeded. Raising
                # lets `ExtractionService.extract()` propagate this
                # uncaught, same as any other extraction-stage exception --
                # orchestrator's own classification (not one of
                # `_TERMINAL_ERROR_TYPES`) already turns an unclassified
                # exception into RETRYABLE_FAILED, exactly the outcome a
                # transient provider failure should get.
                raise ExtractionProviderError(
                    f"extraction call failed for record {record.record_id}: {e}"
                ) from e

            drafts = self._build_drafts(content, res.facts)
            ctx["extracted_drafts"] = len(drafts)
            return tuple(drafts)

    def extract_batch(self, records: Sequence[ContextRecord]) -> dict[str, Sequence[ExtractionDraft]]:
        """Batched sibling of `extract()`: packs multiple turns into ONE LLM call
        instead of one call per turn, cutting REQUEST count under concurrency (a
        provider's RPM/TPM ceiling presses on request count, not just per-call
        latency -- see docs/fixes_and_evaluation_findings.md §7).

        Deliberately NOT the default extraction path -- `Config.extraction_batch_size`
        must be explicitly set above 1 for `PrefetchingExtractor` to call this instead
        of `extract()`. Packing turns into one prompt/response risks the model
        attributing a fact to the wrong turn or inventing one not actually present in
        that turn's own content; each turn's facts are still built into `ExtractionDraft`s
        by the SAME `_build_drafts()` helper `extract()` uses, against that turn's OWN
        content string only, so a misattributed turn_index is the only new failure mode
        this path introduces (a missing/garbled turn_index entry degrades gracefully to
        zero facts for that one turn, not a whole-batch failure).

        Returns a dict keyed by `record_id` covering every record passed in (records
        with empty content, or a turn_index the model never returned, map to `()`).
        """
        results: dict[str, Sequence[ExtractionDraft]] = {record.record_id: () for record in records}
        non_empty = [(i, r) for i, r in enumerate(records) if r.content and r.content.strip()]
        if not non_empty:
            return results

        prompt_parts = [
            f"--- Turn {local_idx} ---\nSpeaker: {record.actor_role}\nContent: {record.content}"
            for local_idx, (_, record) in enumerate(non_empty)
        ]
        user_prompt = "\n\n".join(prompt_parts) + "\n\nExtract atomic facts for each turn above, grouped by turn_index:"
        max_tokens = self._config.extraction_batch_max_tokens_for([len(record.content) for _, record in non_empty])

        with timed_operation(
            logger, "extractor.extract_batch",
            {"batch_size": len(non_empty), "content_len": sum(len(r.content) for _, r in non_empty), "max_tokens": max_tokens},
        ) as ctx:
            try:
                res = self._client.structured_completion(
                    self._config.batched_fact_extraction_system_prompt, user_prompt, _BatchedFactExtractionResponse,
                    temperature=self._config.llm_temperature, max_tokens=max_tokens,
                    timeout=self._config.extractor_batch_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as e:
                logger.error("LLMExtractor failed batched extraction for %d records: %s", len(non_empty), e)
                ctx["extracted_drafts"] = 0
                # §2 fix: was `return results` with every record defaulted to
                # `()` -- one failed call silently erased facts for every
                # turn in the batch with no distinction from "none of these
                # turns had durable facts." Raising here means the batch
                # path fails as loudly as the single-record path now does;
                # `PrefetchingExtractor` (evaluation/benchmark_runner.py) is
                # the only caller that ever sees this synchronously outside
                # `run_chunk`'s own try/except, and it's been updated to
                # propagate rather than swallow it too.
                raise ExtractionProviderError(
                    f"batched extraction call failed for {len(non_empty)} records: {e}"
                ) from e

            by_turn: dict[int, list[_ExtractedFactItem]] = {}
            for turn in res.turns:
                by_turn.setdefault(turn.turn_index, []).extend(turn.facts)

            total_drafts = 0
            for local_idx, (_, record) in enumerate(non_empty):
                drafts = self._build_drafts(record.content, by_turn.get(local_idx, []))
                results[record.record_id] = tuple(drafts)
                total_drafts += len(drafts)
            ctx["extracted_drafts"] = total_drafts
            return results
