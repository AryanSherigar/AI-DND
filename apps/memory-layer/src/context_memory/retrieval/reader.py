"""Phase 3b: assembles the reader's context window from the fused top facts
plus sibling expansion, then synthesizes the final answer.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.retrieval.detectors import date_diff_in_unit, format_number, looks_like_duration_query
from context_memory.retrieval.models import DurationAnswer, ScoredFact
from context_memory.retrieval.sibling_expander import SiblingExpander

logger = get_logger(__name__)


class AnswerReader:
    def __init__(self, llm_client: LLMClient, sibling_expander: SiblingExpander, config: Config | None = None) -> None:
        self._llm = llm_client
        self._sibling_expander = sibling_expander
        self._config = config or Config()

    def read(
        self, question: str, top_facts: list[ScoredFact], context_id: str | None = None,
        question_date: datetime | None = None,
    ) -> str:
        with timed_operation(logger, "retrieval.phase3.reader_context", {"top_facts": len(top_facts)}) as ctx:
            # Format context
            context_blocks = []
            for fact in top_facts:
                date_str = ""
                if fact.observed_at:
                    try:
                        date_str = datetime.fromtimestamp(fact.observed_at, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        date_str = "Recent"
                else:
                    date_str = "Recent"
                speaker_str = fact.speaker or "user"
                context_blocks.append(f"[{date_str} | {speaker_str}]: {fact.text}")

            # Neighboring-turn expansion (ADR-005): pull in every other fact
            # extracted from the same source turn as a fact that already
            # earned its place in top_facts. Dated the same way top facts are
            # (see sibling_expander.py) -- previously bare `- {text}`, which left
            # ~30% of the reader's context undated and caused a wrong-order
            # answer on a real date-arithmetic question (§11.2). Speaker is
            # still not carried (no cheap source for it here), so these stay
            # under their own heading rather than interleaved with top_facts
            # as if independently ranked.
            if context_id is not None and self._config.retrieval_sibling_fact_limit > 0:
                try:
                    siblings = self._sibling_expander.find_siblings(context_id, [f.fact_id for f in top_facts], question)
                except Exception as e:
                    logger.debug("Sibling-fact expansion skipped: %s", e)
                    siblings = {}
                if siblings:
                    ctx["sibling_facts_added"] = len(siblings)
                    context_blocks.append("[related facts from the same conversation turns]:")
                    for text, observed_at in siblings.values():
                        if observed_at:
                            try:
                                d = datetime.fromtimestamp(observed_at, tz=timezone.utc).strftime("%Y-%m-%d")
                                context_blocks.append(f"- [{d}]: {text}")
                                continue
                            except Exception:
                                pass
                        context_blocks.append(f"- {text}")

            # Reference date first (§20), for elapsed-time questions ONLY.
            # Every fact carries a date, but the reader was never told what
            # "now" is -- so "how many days ago did I X?" was structurally
            # unanswerable and the model correctly said so ("the current date
            # isn't in the context"). Deliberately NOT unconditional: added
            # globally it measurably regressed a count question ("how many
            # magazine subscriptions do I currently have" went 2 -> 1, 3/3
            # runs), apparently by making the reader stricter about
            # "currently". Scoped to the questions that actually need it.
            is_duration_query = looks_like_duration_query(question)
            if is_duration_query and question_date is not None:
                context_blocks.insert(0, f"[today's date is {question_date.strftime('%Y-%m-%d')}]")
            context_str = "\n".join(context_blocks)

            prompt = self._config.reader_system_prompt_template.format(context=context_str)
            # Duration questions get step-by-step arithmetic guidance appended
            # in the SAME call (§20) -- never a second reasoning call, which is
            # the thing measured to reduce accuracy (§11.1).
            if is_duration_query:
                ctx["duration_guidance_applied"] = True
                prompt = prompt + self._config.duration_query_guidance
                if self._config.duration_structured_verification_enabled:
                    return self._duration_reader_synthesis(prompt, question, ctx, question_date)
            with timed_operation(logger, "retrieval.phase3.reader_synthesis"):
                return self._llm.text_completion(
                    prompt, question, temperature=self._config.reader_temperature,
                    max_tokens=self._config.reader_max_tokens, timeout=self._config.reader_timeout_seconds,
                )

    def _duration_reader_synthesis(
        self, prompt: str, question: str, ctx: dict, question_date: datetime | None = None,
    ) -> str:
        """§26: structured variant of the reader call for duration questions --
        one call, model reports its own operands alongside its prose, Python
        verifies and corrects only on a detected mismatch. Any failure
        (malformed JSON, missing operands, non-arithmetic operation) falls
        back to the plain-text reader call, so this can only help."""
        with timed_operation(logger, "retrieval.phase3.reader_synthesis") as inner_ctx:
            try:
                result = self._llm.structured_completion(
                    prompt + self._config.duration_query_structured_addendum, question, DurationAnswer,
                    temperature=self._config.reader_temperature, max_tokens=self._config.reader_max_tokens,
                    timeout=self._config.reader_timeout_seconds, max_retries=self._config.llm_structured_retry_attempts,
                )
            except Exception as error:
                logger.warning("Structured duration reader failed, falling back to plain text: %s", error)
                inner_ctx["duration_structured_failed"] = True
                return self._llm.text_completion(
                    prompt, question, temperature=self._config.reader_temperature,
                    max_tokens=self._config.reader_max_tokens, timeout=self._config.reader_timeout_seconds,
                )

            end_date = result.end_date
            question_day = question_date.strftime("%Y-%m-%d") if question_date is not None else None
            if result.operation == "ago_since" and question_day:
                # "N days/weeks ago" always resolves against the real reference
                # date, which Python already knows -- there is no need to trust
                # the model's own self-reported end_date for this operation at
                # all, and live data shows it is not always reliable (§26: one
                # run reported 2023-04-10 as the end_date when the true
                # question_date was that same day, which was fine, but there is
                # no reason to leave this to chance when the ground truth is
                # already in hand).
                end_date = question_day
            elif result.operation == "between" and question_day and result.end_date == question_day:
                # A "between two named events" question never has "today" as
                # one of its own endpoints -- live data shows the model
                # sometimes substitutes question_date for the second event's
                # actual date while still stating the (correct) prose answer
                # from its real reasoning. Trusting that operand would silently
                # overwrite a correct answer with a wrong one, so skip
                # correction and keep the model's own prose instead.
                end_date = None

            if (
                result.operation in ("ago_since", "between")
                and result.unit == "days"
                and result.start_date and end_date
                and result.stated_result is not None
            ):
                # Correction is restricted to unit="days" -- live data (§26)
                # showed weeks/months/years is where this goes wrong even with
                # correct dates: a 34-day routine is genuinely, colloquially
                # "about 4 weeks" (the gold answer), but exact conversion gives
                # 4.857142857142857 weeks, and overriding the model's own
                # correctly-rounded prose with that raw fraction is a strictly
                # worse answer, not a fix. Every real arithmetic-bug case this
                # was built for (education years, Nordstrom weeks, the charity
                # run, the mountain bike) either used "days" already or never
                # triggered a correction in the first place (operands already
                # matched), so this restriction costs nothing already verified.
                true_diff = date_diff_in_unit(result.start_date, end_date, result.unit)
                if true_diff is not None and abs(true_diff - abs(result.stated_result)) > 0.01:
                    ctx["duration_arithmetic_corrected"] = True
                    logger.info(
                        "Duration arithmetic mismatch: model stated %s %s (dates %s -> %s), "
                        "dates imply %s -- correcting",
                        result.stated_result, result.unit, result.start_date, end_date, true_diff,
                    )
                    verb = "ago" if result.operation == "ago_since" else "apart"
                    corrected = format_number(true_diff)
                    return f"{corrected} {result.unit} {verb}."
            return result.answer or "I don't have enough information to answer that."
