"""Wire schemas and the scoring record shared across retrieval stages.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


@dataclass
class ScoredFact:
    fact_id: str
    text: str
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    structural_score: float = 0.0
    entity_boost: float = 0.0
    composite_score: float = 0.0
    speaker: str | None = None
    observed_at: int | None = None
    # 1-indexed rank within each channel's own result list -- None means the
    # fact did not appear in that channel at all. Captured at seeding time
    # (the SQL already returns rows in rank order) so Phase 3 can fuse by
    # Reciprocal Rank Fusion instead of summing raw, differently-scaled scores.
    semantic_rank: int | None = None
    keyword_rank: int | None = None


@dataclass
class RetrievedFact:
    """Structured retrieval output for `HybridRetrievalEngine.retrieve_facts` --
    the AI-DND memory contract's `Fact` shape (subject/predicate/object), built
    from fields the graph already stores per fact (Milestone 1 of the AI-DND
    bridge). `subject`/`object` are the normalized triple components written
    by extraction (`model_adapters.LLMExtractor`) or direct authoring
    (§9 fix) -- short, comparable values, not a restatement of the sentence.
    When a fact predates this (or the extractor left one blank), `subject`
    falls back to the fact's linked ABOUT entity and `object` falls back to
    the full extracted sentence -- still the previous, pragmatic behavior,
    now the exception rather than the rule."""
    fact_id: str
    subject: str
    predicate: str
    object: str
    valid_from: str | None
    valid_until: str | None
    confidence: float
    # AI-DND memory-layer contract: `hidden` is an author-marked secret,
    # returned as-is -- mem1 never filters on it (the caller applies its
    # own revealed_facts override). `when_active` is returned instead of
    # evaluated (Gap B, accepted): the caller evaluates it client-side with
    # its own expression grammar rather than mem1 filtering server-side.
    when_active: dict | None = None
    hidden: bool = False


@dataclass
class RetrievedFacts:
    facts: list[RetrievedFact]
    abstained: bool
    resolved_time_point: str | None = None


class DateRange(BaseModel):
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class QueryRewriterOutput(BaseModel):
    decomposed_queries: list[str]
    synonyms: list[str]


class RerankSelection(BaseModel):
    selected: list[int] = []


class DurationAnswer(BaseModel):
    """§26: 'arithmetic requires a deterministic procedure; when an LLM adds two
    numbers it is generating tokens that look like the result, not computing'
    (well-established finding). Rather than a second reasoning call (which
    §11.1 measured as harmful), the model reports its own operands ALONGSIDE
    its prose answer, in the SAME call, and Python verifies the arithmetic --
    intervening only on a detected, verifiable mismatch. operation="sum" or
    "insufficient_evidence" (or any missing operand) always falls through to
    the model's own prose unchanged -- this can only correct a verifiable
    error, never invent one.

    start_date/end_date are ISO calendar dates (YYYY-MM-DD), not unit-scaled
    floats -- an earlier version asked for "plain numbers in a single unit
    (e.g. epoch-day counts)" and the model would sometimes emit a truncated
    date fragment like 2023.03 instead (both operands "2023.03" -> a false
    true_diff of 0, silently turning a correct "7 days ago" into a wrong "0
    days ago" on live data). It also separately reported stated_result in a
    different unit than the unit field claimed (weeks vs days), which read as
    a "mismatch" and fired a correction that was numerically fine but
    reformatted a correct "2 weeks ago" into "14 days ago". Real calendar
    dates remove both failure modes: Python parses them and derives the
    unit-converted difference itself, so unit and operand encoding are no
    longer things the model can get inconsistent with each other."""
    operation: Literal["ago_since", "between", "sum", "insufficient_evidence"] = "insufficient_evidence"
    start_date: str | None = None
    end_date: str | None = None
    unit: Literal["days", "weeks", "months", "years"] | None = None
    stated_result: float | None = None
    answer: str = ""
