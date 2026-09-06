"""Single source of truth for every tunable value in the system: model
allocation per role, LLM call limits, retrieval scoring/thresholds, ingestion
concurrency, and every system prompt. Nothing below is read from `os.environ`
anywhere else in the codebase — if a value needs to be dialed, it's a field
here, not a literal buried in `retrieval.py`/`model_adapters.py`/`engine.py`.

Deliberately does NOT auto-load `.env` on import. `main` branch's version of
this module did (`load_dotenv()` at module scope) — that is an import-time
side effect: merely importing this module (e.g. `unittest discover` importing
every test file to enumerate cases, including a live-gated one it never runs)
silently repopulates `FIREWORKS_API_KEY` into the process environment from
disk, defeating any `skipUnless(os.environ.get(...))` gate and risking a real
billed call from a plain test run. Same posture `test_hydradb_live.py` already
takes for `CONTEXT_MEMORY_HYDRADB_TOKEN`: credentials come from the runtime
environment the caller explicitly set up (`source src/.env`, an exported var,
or a deploy-time secret), never from an implicit file read triggered by import.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from context_memory.core.llm_client import LLMClient
from context_memory.core.prompts import (
    BATCHED_ENTITY_RESOLUTION_SYSTEM_PROMPT,
    BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT,
    BATCHED_NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT,
    BATCHED_TEMPORAL_UPDATE_SYSTEM_PROMPT,
    DURATION_QUERY_GUIDANCE,
    DURATION_QUERY_STRUCTURED_ADDENDUM,
    ENTITY_RESOLUTION_SYSTEM_PROMPT,
    FACT_EXTRACTION_SYSTEM_PROMPT,
    NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT,
    QUERY_REWRITER_SYSTEM_PROMPT,
    READER_SYSTEM_PROMPT_TEMPLATE,
    RERANK_SYSTEM_PROMPT,
    TEMPORAL_RESOLVER_SYSTEM_PROMPT_TEMPLATE,
    TEMPORAL_UPDATE_SYSTEM_PROMPT,
)

# Default provider: Vertex AI (Google agentic platform), via `google-genai`'s
# API-key auth mode (`genai.Client(vertexai=True, api_key=...)`) rather than
# an OpenAI-compatible endpoint -- see `core/llm_client.py`'s module
# docstring for why the OpenAI-SDK-shaped provider this used to default to
# (Groq) was retired rather than kept as a fallback.
#
# gemini-3.8-flash is the main model -- the default here, and what every
# role gets unless overridden. `oss-120b` and `qwen-235b-a22b` are also
# available on this same platform/client for a role that wants a different
# model (e.g. a narrow classification task that doesn't need Gemini's
# full capability) -- set that role's own `<ROLE>_MODEL` env var to its
# model id, exactly the same per-role override mechanism this config
# already had before the Vertex AI migration.
_DEFAULT_MODEL = "gemini-3.8-flash"


def _role_api_key(env_name: str) -> str:
    """Per-role override, else the generic `LLM_API_KEY`, else
    `GOOGLE_CLOUD_API_KEY` (this project's own naming, per the Vertex AI
    migration guidelines), else the literal key this repo's own `.env`
    ships under (`Gemini_agentic_platform_api_key`) as a last resort so a
    fresh checkout works without renaming anything."""
    return os.getenv(
        env_name,
        os.getenv(
            "LLM_API_KEY",
            os.getenv("GOOGLE_CLOUD_API_KEY", os.getenv("Gemini_agentic_platform_api_key", "")),
        ),
    )


def _role_model(env_name: str) -> str:
    return os.getenv(env_name, os.getenv("LLM_MODEL", _DEFAULT_MODEL))


@dataclass(frozen=True)
class Config:
    # -- Ingestion/resolution roles (ADR-027/029) --------------------------
    entity_resolution_api_key: str = field(default_factory=lambda: _role_api_key("ENTITY_RESOLUTION_API_KEY"))
    entity_resolution_model: str = field(default_factory=lambda: _role_model("ENTITY_RESOLUTION_MODEL"))
    # Own reasoning_effort (not the global `llm_reasoning_effort`) -- see
    # `get_entity_resolution_client`'s comment: needed because a smaller
    # model behind this specific role may accept a different reasoning-effort
    # enum than whatever the extraction model needs (confirmed live:
    # `qwen.qwen3-32b` accepts "none" -- genuinely disables reasoning, ~3-4x
    # faster on this task -- while `openai.gpt-oss-20b`, used elsewhere,
    # rejects "none" outright and only accepts low/medium/high). Empty
    # string (default) falls back to `llm_reasoning_effort`, same as before
    # this field existed.
    entity_resolution_reasoning_effort: str = field(default_factory=lambda: os.getenv("ENTITY_RESOLUTION_REASONING_EFFORT", ""))

    temporal_update_api_key: str = field(default_factory=lambda: _role_api_key("TEMPORAL_UPDATE_API_KEY"))
    temporal_update_model: str = field(default_factory=lambda: _role_model("TEMPORAL_UPDATE_MODEL"))
    # Own reasoning_effort, same reasoning as entity_resolution_reasoning_effort
    # above -- this role never got the same treatment despite being the same
    # *kind* of call (a small, bounded, four-way classification decision, not
    # free-form generation). Measured live on a real 9-instance run
    # (docs/fixes_and_evaluation_findings.md §7): temporal_update.classify cost
    # 742s of serial LLM time on one 493-turn instance, essentially tied with
    # extraction itself and un-parallelized (unlike extraction, which is
    # prefetched) -- the single largest never-addressed ingest cost this
    # session found. Empty string (default) falls back to `llm_reasoning_effort`,
    # unchanged from before this field existed.
    temporal_update_reasoning_effort: str = field(default_factory=lambda: os.getenv("TEMPORAL_UPDATE_REASONING_EFFORT", ""))

    extractor_api_key: str = field(default_factory=lambda: _role_api_key("EXTRACTOR_API_KEY"))
    extractor_model: str = field(default_factory=lambda: _role_model("EXTRACTOR_MODEL"))

    # -- Retrieval roles ------------------------------------------------
    reader_api_key: str = field(default_factory=lambda: _role_api_key("READER_API_KEY"))
    reader_model: str = field(default_factory=lambda: _role_model("READER_MODEL"))

    temporal_resolver_api_key: str = field(default_factory=lambda: _role_api_key("TEMPORAL_RESOLVER_API_KEY"))
    temporal_resolver_model: str = field(default_factory=lambda: _role_model("TEMPORAL_RESOLVER_MODEL"))
    # See `entity_resolution_reasoning_effort`'s comment for why this is a
    # separate field from the global `llm_reasoning_effort` -- same
    # rationale, this role too is a narrow structured-decision task (date
    # range extraction) a smaller/non-reasoning model can handle.
    temporal_resolver_reasoning_effort: str = field(default_factory=lambda: os.getenv("TEMPORAL_RESOLVER_REASONING_EFFORT", ""))

    query_rewriter_api_key: str = field(default_factory=lambda: _role_api_key("QUERY_REWRITER_API_KEY"))
    query_rewriter_model: str = field(default_factory=lambda: _role_model("QUERY_REWRITER_MODEL"))
    query_rewriter_reasoning_effort: str = field(default_factory=lambda: os.getenv("QUERY_REWRITER_REASONING_EFFORT", ""))

    # -- LLM call limits, sized per role ------------------------------------
    # A 241-second call that returned an empty completion (hit its own output
    # ceiling before producing valid JSON) is what an unbounded call actually
    # does — confirmed live, not a theoretical risk. Every role gets a cap.
    # One shared cap isn't right either: extraction reasons over a whole turn
    # before emitting JSON and was the one role that hit 2048 and came back
    # empty (confirmed live), while classification/selection roles emit a few
    # words of JSON and gain nothing from a large ceiling but pay for one in
    # provider-side worst-case latency. Every role below is sized to its own
    # output shape rather than sharing one number.
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))
    # Sent on every call when set. Best-effort per provider; empty omits it.
    llm_seed: int | None = field(
        default_factory=lambda: int(os.environ["LLM_SEED"]) if os.getenv("LLM_SEED") else None
    )
    # Confirmed live (LongMemEval pilot): a reasoning model can spend its whole
    # completion budget on hidden reasoning and return empty content — the cap
    # bounds worst-case latency but doesn't prevent this. One retry (with a
    # blunter prompt and, only on a genuine budget-exhaustion `finish_reason`,
    # a doubled budget) recovers most of these instead of silently losing a
    # turn's facts. See `LLMClient.structured_completion`.
    llm_structured_retry_attempts: int = field(default_factory=lambda: int(os.getenv("LLM_STRUCTURED_RETRY_ATTEMPTS", "1")))
    # The OpenAI SDK's own retry count. Its default of 2 multiplies every timeout
    # (45s cap became 135s of real wall clock — measured). Kept at 1 rather than 0
    # because Groq rate-limits on tokens-per-minute and a 429 deserves one retry.
    llm_sdk_max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_SDK_MAX_RETRIES", "1")))
    # Separate from both retry counts above: a 429 raises out of `.create()`
    # rather than returning unparseable content, so neither of them ever saw it
    # and rate-limited calls failed outright, silently dropping a turn's facts
    # (confirmed live against Groq's 8k TPM free tier). Higher than the others
    # because a tokens-per-minute limiter legitimately needs several waits in a
    # row under concurrent prefetch; each wait honors the provider's own stated
    # retry-after, so this is mostly-idle time, not repeated load.
    llm_rate_limit_max_retries: int = field(default_factory=lambda: int(os.getenv("LLM_RATE_LIMIT_MAX_RETRIES", "5")))
    # How the response shape is described to the model: "typedef" (compact
    # TS/BAML-style class declaration) or "json_schema" (pydantic's own output).
    # Measured on the extraction schema: 839 chars as raw JSON Schema, 479 with
    # noise keys stripped, 225 as a typedef. That blob rides on every single
    # call, so under a tokens-per-minute limit it is throughput, not cosmetics.
    # Groq reports no prompt caching (verified: identical prompts billed at full
    # price twice, no `cached_tokens` field), so nothing amortizes this for us.
    llm_schema_format: str = field(default_factory=lambda: os.getenv("LLM_SCHEMA_FORMAT", "typedef"))
    # Vertex AI's `GenerateContentConfig.service_tier`: "" (default) leaves
    # it unset (standard on-demand serving); "flex" opts into Flex
    # Processing (cost-optimized, some latency/availability variability) --
    # worth trying first per the platform's own model allocation decision.
    # "priority"/"standard" are the SDK's other two real-time tiers.
    # Deliberately does NOT accept "batch" here: Vertex AI's actual Batch
    # mode is a different, asynchronous API (`client.batches.create(...)`,
    # submit-then-poll) that this client's synchronous
    # structured_completion/text_completion/chat_with_tools interface
    # doesn't support at all yet -- adopting real Batch mode needs its own
    # design (a submit/poll/retrieve flow, not a config value), tracked as
    # a separate follow-up rather than silently mislabeled as this field.
    llm_service_tier: str = field(default_factory=lambda: os.getenv("LLM_SERVICE_TIER", ""))
    # Sent only when non-empty, because valid values are model-specific
    # (qwen3.6: none|default — gpt-oss: low|medium|high) and an unsupported
    # value is a hard 400. Empty string omits the parameter entirely, which is
    # the right behavior for any provider/model that doesn't know it.
    llm_reasoning_effort: str = field(default_factory=lambda: os.getenv("LLM_REASONING_EFFORT", "none"))

    entity_resolution_max_tokens: int = field(default_factory=lambda: int(os.getenv("ENTITY_RESOLUTION_MAX_TOKENS", "512")))
    entity_resolution_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("ENTITY_RESOLUTION_TIMEOUT_SECONDS", "20")))
    batched_entity_resolution_system_prompt: str = BATCHED_ENTITY_RESOLUTION_SYSTEM_PROMPT
    # ON by default, same posture as temporal_update_batch_enabled (§8) --
    # unlike that fix, this batches mentions already-parallelized by
    # resolve_many's ThreadPoolExecutor, so the win is request COUNT, not a
    # comparable wall-clock multiplier. Set 0 to fall back to the
    # one-call-per-mention path, kept intact.
    entity_resolution_batch_enabled: bool = field(
        default_factory=lambda: os.getenv("ENTITY_RESOLUTION_BATCH_ENABLED", "1").lower() not in ("0", "false", "no")
    )
    entity_resolution_batch_tokens_per_mention: int = field(default_factory=lambda: int(os.getenv("ENTITY_RESOLUTION_BATCH_TOKENS_PER_MENTION", "48")))
    entity_resolution_batch_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("ENTITY_RESOLUTION_BATCH_TIMEOUT_SECONDS", "45")))

    def entity_resolution_batch_max_tokens_for(self, mention_count: int) -> int:
        return self.entity_resolution_max_tokens + self.entity_resolution_batch_tokens_per_mention * max(0, mention_count)

    temporal_update_max_tokens: int = field(default_factory=lambda: int(os.getenv("TEMPORAL_UPDATE_MAX_TOKENS", "512")))
    temporal_update_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("TEMPORAL_UPDATE_TIMEOUT_SECONDS", "20")))

    # Batched temporal-update classification (§8): measured 5.87 priors per
    # superseding fact (max 23), so 84% of these calls were the 2nd..Nth prior.
    # Set 0 to fall back to the pairwise path, which is kept intact.
    temporal_update_batch_enabled: bool = field(
        default_factory=lambda: os.getenv("TEMPORAL_UPDATE_BATCH_ENABLED", "1").lower() not in ("0", "false", "no")
    )
    # Embedding pre-filter on candidate priors. Calibrated on 3540 real recorded
    # comparisons (§8): every supersession below 0.15 was verifiably spurious.
    # 0 disables. Cuts priors-per-batch ~29%, not call count -- batching already
    # took that.
    temporal_update_similarity_threshold: float = field(default_factory=lambda: float(os.getenv("TEMPORAL_UPDATE_SIMILARITY_THRESHOLD", "0.15")))
    temporal_update_batch_tokens_per_prior: int = field(default_factory=lambda: int(os.getenv("TEMPORAL_UPDATE_BATCH_TOKENS_PER_PRIOR", "48")))
    temporal_update_batch_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("TEMPORAL_UPDATE_BATCH_TIMEOUT_SECONDS", "45")))

    def temporal_update_batch_max_tokens_for(self, prior_count: int) -> int:
        """Shared reasoning headroom plus one {idx, relation} object per prior."""
        return self.temporal_update_max_tokens + self.temporal_update_batch_tokens_per_prior * max(0, prior_count)

    # Extraction reasons over the whole turn before emitting JSON — this is the
    # role that actually hit the old 2048 shared cap and came back empty/truncated
    # (confirmed live). Given more headroom and more time to use it.
    extractor_max_tokens: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS", "4096")))
    extractor_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("EXTRACTOR_TIMEOUT_SECONDS", "45")))

    # Multi-stage max_tokens gateway for extraction (see
    # `extraction_max_tokens_for` below), tiered by turn content length in
    # characters. Replaces one flat ceiling paid on every call with the
    # smallest tier that still covers this turn -- thresholds are the real
    # p50/p75/p95/tail split measured over 25k real LongMemEval turns
    # (median 436 chars, p75 1692, p90 2524, p99 3452, max 31122 -- a few
    # turns are an order of magnitude longer than the rest). `tier_long`
    # keeps the prior flat default (4096) as the ceiling for the ~90th
    # percentile and below, so typical/long turns are unaffected; the new
    # `tier_xlong` gives the rare (~1%) outlier-length turns more headroom
    # than the old flat cap ever gave them -- those are exactly the turns
    # most likely to hit the reasoning-exhaustion-returns-empty failure mode
    # this project has already seen live with a different model (see
    # docs/fixes_and_evaluation_findings.md), and a short/medium turn now
    # gets a smaller allocation than before instead of paying the long-turn
    # ceiling every time.
    extractor_max_tokens_tier_short_chars: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_SHORT_CHARS", "300")))
    extractor_max_tokens_tier_short: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_SHORT", "1536")))
    extractor_max_tokens_tier_medium_chars: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_MEDIUM_CHARS", "1200")))
    extractor_max_tokens_tier_medium: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_MEDIUM", "2560")))
    extractor_max_tokens_tier_long_chars: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_LONG_CHARS", "3000")))
    extractor_max_tokens_tier_long: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_LONG", "4096")))
    extractor_max_tokens_tier_xlong: int = field(default_factory=lambda: int(os.getenv("EXTRACTOR_MAX_TOKENS_TIER_XLONG", "6144")))

    def extraction_max_tokens_for(self, content_length: int) -> int:
        """Multi-stage if/else gateway: the smallest max_tokens tier whose
        content-length threshold still covers this turn, instead of one
        flat `extractor_max_tokens` ceiling paid on every call regardless of
        size. Ascending thresholds, first match wins; anything past the
        last threshold gets the top tier, never a bare `extractor_max_tokens`
        fallback -- that field stays only for callers/tests that still want
        one fixed number.
        """
        if content_length <= self.extractor_max_tokens_tier_short_chars:
            return self.extractor_max_tokens_tier_short
        elif content_length <= self.extractor_max_tokens_tier_medium_chars:
            return self.extractor_max_tokens_tier_medium
        elif content_length <= self.extractor_max_tokens_tier_long_chars:
            return self.extractor_max_tokens_tier_long
        else:
            return self.extractor_max_tokens_tier_xlong

    # Batched extraction (opt-in, see docs/fixes_and_evaluation_findings.md §7):
    # packs `extraction_batch_size` turns into one LLM call instead of one call
    # per turn, cutting REQUEST count (not just per-call latency) -- the thing
    # that actually presses on a provider's RPM/TPM ceiling under concurrency.
    # Defaults to 1, i.e. today's one-call-per-turn behavior, unchanged --
    # packing turns into one prompt/response risks the model attributing a fact
    # to the wrong turn or inventing one not present in that turn's own content,
    # a real correctness risk that needs live verification before raising this
    # past 1 in the runs that matter. `PrefetchingExtractor` only takes the
    # batched path when this is set above 1 AND the extractor exposes
    # `extract_batch` (LLMExtractor does; FakeExtractor does not, and correctly
    # keeps running one-call-per-turn under this flag).
    extraction_batch_size: int = field(default_factory=lambda: int(os.getenv("EXTRACTION_BATCH_SIZE", "1")))
    # A batch response carries N turns' worth of JSON instead of one, so it
    # takes proportionally longer to reason over and emit -- give it more room
    # than a single turn's extractor_timeout_seconds rather than reusing it
    # unchanged and risking a spurious timeout on a batch that was otherwise
    # about to succeed.
    extractor_batch_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("EXTRACTOR_BATCH_TIMEOUT_SECONDS", "90")))

    def extraction_batch_max_tokens_for(self, content_lengths: Sequence[int]) -> int:
        """Sums each turn's own tiered allocation (`extraction_max_tokens_for`)
        across the batch, rather than tiering on total batch character length --
        keeps the per-turn headroom identical to the unbatched path (a batch of
        one short turn and one xlong turn gets short+xlong, not one blended
        tier) while naturally scaling the ceiling with batch size.
        """
        return sum(self.extraction_max_tokens_for(n) for n in content_lengths)

    # Was 0.2 for prose warmth. Measured (§9): 3 identical retrievals over the
    # same stored context answered "four" / "three" / "two" to one counting
    # question. Readability is not worth an unreproducible benchmark.
    reader_temperature: float = field(default_factory=lambda: float(os.getenv("READER_TEMPERATURE", "0.0")))
    reader_max_tokens: int = field(default_factory=lambda: int(os.getenv("READER_MAX_TOKENS", "1536")))
    reader_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("READER_TIMEOUT_SECONDS", "25")))

    temporal_resolver_max_tokens: int = field(default_factory=lambda: int(os.getenv("TEMPORAL_RESOLVER_MAX_TOKENS", "512")))
    temporal_resolver_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("TEMPORAL_RESOLVER_TIMEOUT_SECONDS", "15")))

    # Rewrites are not reproducible (§9) and depend only on the question, so
    # caching them makes repeat asks deterministic and skips one LLM call.
    query_rewrite_cache_enabled: bool = field(
        default_factory=lambda: os.getenv("QUERY_REWRITE_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")
    )
    # Unset = in-process only (repeat asks stable within one run). Set a path to
    # persist, so separate runs reproduce each other.
    query_rewrite_cache_path: str = field(default_factory=lambda: os.getenv("QUERY_REWRITE_CACHE_PATH", ""))
    query_rewriter_max_tokens: int = field(default_factory=lambda: int(os.getenv("QUERY_REWRITER_MAX_TOKENS", "768")))
    query_rewriter_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("QUERY_REWRITER_TIMEOUT_SECONDS", "15")))

    # -- Embedding (Milestone 7) ------------------------------------------
    embedding_model_name: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    )
    embedding_model_version: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_VERSION", "1"))

    # -- Retrieval tuning (FINAL_ARCHITECTURE.md §12) ----------------------
    # 15 -> 20. Every traced multi-session/preference retrieval miss on the
    # 30-instance LongMemEval sample had the same shape: the needed fact was
    # seeded and scored, just outside this cutoff, crowded out by a fact that
    # matched the question's wording (e.g. any dollar figure for a "how much"
    # question) without matching its actual topic. This doesn't fix the
    # underlying ranking-relevance gap (see retrieval.phase3's cutoff-boundary
    # log line, added alongside this change, for that diagnosis going
    # forward) -- it's a cheap, low-risk mitigation: a wider reader window
    # gives near-miss facts more room to still get seen while the real ranking
    # fix (surface-similarity vs topical-relevance) is designed properly.
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "20")))
    # Wider top_k for count/enumeration questions (§10.3/§11.1/§15): the
    # observed undercount failure was NOT extraction losing facts (verified
    # present in the store every time) -- it's `ranked[:top_k]` truncating
    # before every matching fact reaches the reader. A structured aggregation
    # LLM pass was tried by a published 90.8%-LongMemEval system and made
    # accuracy WORSE (91.2%->86.0%); this widens the existing top-k truncation
    # for detected count queries instead of adding a reasoning step.
    retrieval_count_query_top_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_COUNT_QUERY_TOP_K", "40")))
    # LLM reranking over the fused candidate pool (§23). OFF by default until
    # measured. Motivation is two confirmed pure-ranking failures where the
    # gold fact was in the store but lost the top_k cut ("Effective Time
    # Management workshop" absent from the 29 facts the reader saw; three
    # wedding-attendance facts crowded out by wedding-PLANNING content).
    # One call per QUERY (not per fact). Precedent: arXiv 2606.01435 uses
    # exactly this shape -- retrieve, let an LLM pick which candidates match
    # the question, then apply a deterministic policy -- and it is selection,
    # not the extra answer-reasoning call that §11.1 measured as harmful.
    # ON by default (§25): 3 independent runs, all positive, 0 regressions in
    # the most rigorous (compounded with the §24 temporal fix) -- crossed from
    # "promising, unproven" (§23) to decided. Directly targets the dilution
    # failure class (Mem0's own docs name it "semantic genericity failure":
    # broad memories outrank the decisive specific one) that a plain RRF
    # channel could not fix without regressing something else (§21.3).
    retrieval_rerank_enabled: bool = field(
        default_factory=lambda: os.getenv("RETRIEVAL_RERANK_ENABLED", "1").lower() not in ("0", "false", "no")
    )
    retrieval_rerank_candidates: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_RERANK_CANDIDATES", "60")))
    retrieval_rerank_max_tokens: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_RERANK_MAX_TOKENS", "1024")))
    retrieval_rerank_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("RETRIEVAL_RERANK_TIMEOUT_SECONDS", "30")))
    rerank_system_prompt: str = field(default_factory=lambda: os.getenv("RERANK_SYSTEM_PROMPT", RERANK_SYSTEM_PROMPT))

    rerank_api_key: str = field(default_factory=lambda: _role_api_key("RERANK_API_KEY"))
    rerank_model: str = field(default_factory=lambda: _role_model("RERANK_MODEL"))
    rerank_reasoning_effort: str = field(default_factory=lambda: os.getenv("RERANK_REASONING_EFFORT", ""))

    def get_rerank_client(self) -> LLMClient:
        effort = self.rerank_reasoning_effort or None
        return self._client(self.rerank_api_key, self.rerank_model, effort)
    # Appended to the reader prompt ONLY for duration/elapsed-time questions
    # (§20). Targets the measured failure: given "from high school to
    # completion of my Bachelor's" with facts "high school 2010-2014" and
    # "Bachelor's completed 2020, took four years", the reader summed the two
    # program durations (4+4=8) instead of subtracting the span endpoints
    # (2020-2010=10), 4 times out of 5. That is an "Expression error" in the
    # temporal-reasoning error taxonomy (wrong operation chosen), the most
    # fundamental of the five categories. Structure follows the three-step
    # in-prompt sequence (extract features -> compute -> answer) that
    # aclanthology.org/2025.vlsp-1.38 reports taking date arithmetic from
    # 0.87 to 0.98 -- deliberately in ONE call, since a separate reasoning
    # call is the thing measured to REDUCE accuracy (§11.1, 91.2%->86.0%).
    duration_query_guidance: str = field(default_factory=lambda: os.getenv("DURATION_QUERY_GUIDANCE", DURATION_QUERY_GUIDANCE))

    # §26: structured sibling of duration_query_guidance -- same reasoning steps,
    # plus an instruction to also report the operands as data (not just prose),
    # so Python can verify the arithmetic against what the model itself claims.
    duration_query_structured_addendum: str = field(
        default_factory=lambda: os.getenv("DURATION_QUERY_STRUCTURED_ADDENDUM", DURATION_QUERY_STRUCTURED_ADDENDUM)
    )
    duration_structured_verification_enabled: bool = field(
        default_factory=lambda: os.getenv("DURATION_STRUCTURED_VERIFICATION_ENABLED", "1").lower() not in ("0", "false", "no")
    )
    # Neighboring-turn expansion (ADR-005's accepted-but-never-implemented
    # "fact + span -> neighboring turn -> full chunk" tier). Traced live: a
    # question needing "20 potted herb plants" x "$7.5 each" got the price but
    # not the quantity, because the extraction prompt splits one turn into
    # several atomic facts and Phase 3 scores them independently -- pulling in
    # every other fact from the same source turn as an already-relevant one
    # re-unites what extraction split apart. 0 disables it entirely.
    retrieval_sibling_fact_limit: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_SIBLING_FACT_LIMIT", "20")))
    # SCAR (Semantic Continuity-Aware Retrieval; Zhong et al. 2026,
    # arxiv.org/abs/2606.16661) scores which siblings actually earn a spot,
    # rather than an unordered LIMIT -- confirmed live this mattered: a needed
    # sibling (4 candidates for its own turn) lost out to unrelated turns'
    # siblings under a shared, unordered cap. lambda penalizes a candidate for
    # being semantically distant from the fact that pulled it in; gamma sets
    # the bar a candidate must clear *relative to its own anchor's* query
    # relevance (a weak anchor -> a low bar; a strong anchor -> a high one).
    # Paper defaults, unchanged -- no tuning data of our own exists yet.
    retrieval_sibling_continuity_penalty: float = field(default_factory=lambda: float(os.getenv("RETRIEVAL_SIBLING_CONTINUITY_PENALTY", "0.1")))
    retrieval_sibling_relevance_ratio: float = field(default_factory=lambda: float(os.getenv("RETRIEVAL_SIBLING_RELEVANCE_RATIO", "0.80")))
    retrieval_overfetch_multiplier: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_OVERFETCH_MULTIPLIER", "4")))
    retrieval_overfetch_floor: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_OVERFETCH_FLOOR", "60")))
    retrieval_chat_ttl_hours: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_CHAT_TTL_HOURS", "24")))
    retrieval_temporal_buffer_days: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_TEMPORAL_BUFFER_DAYS", "2")))
    # Session-[:HAS_TURN]->Turn-[:EXTRACTED_FROM]->Fact-[:ABOUT]->Entity is the
    # deepest real path in the schema; MSpaths hops fact-to-fact via a shared
    # Entity. 4 hops routinely walks past directly-relevant facts into
    # loosely-associated ones, and each hop is a real per-fact HydraDB round
    # trip (no batched UNWIND reads — see retrieval.py), so it's a latency cost
    # for mostly-noise recall. 3 still reaches one shared-entity hop past the
    # seed set.
    retrieval_graph_max_hops: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_GRAPH_MAX_HOPS", "3")))
    # Phase 2 fetches one fact's graph node per HydraDB HTTP call (a genuine
    # N+1 -- HydraDB rejects UNWIND-batched reads, see retrieval.py's own
    # comments), so a retrieval with the overfetch floor's ~60-80 seeded facts
    # was ~60-80 sequential round trips. Concurrent, since each call is
    # independent/read-only and the local HydraDB HTTP transport holds no
    # shared per-call state. 8 matches the same default already used for
    # concurrent extraction prefetch in benchmark_runner.py.
    retrieval_graph_fetch_workers: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_GRAPH_FETCH_WORKERS", "8")))
    retrieval_structural_path_cap: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_STRUCTURAL_PATH_CAP", "3")))
    retrieval_entity_boost_cap: float = field(default_factory=lambda: float(os.getenv("RETRIEVAL_ENTITY_BOOST_CAP", "0.5")))
    # Composite scoring fuses semantic/keyword/structural/entity by Reciprocal
    # Rank Fusion (rank position within each channel, not raw score value) --
    # replaced a raw weighted sum of the four differently-scaled scores, which
    # let whichever one happened to read numerically "big" for a fact dominate
    # regardless of actual relevance (confirmed live and repeatedly on
    # LongMemEval traces: a topically-irrelevant fact with a coincidentally
    # high semantic/entity score routinely outranked the fact that actually
    # answered the question). 60 is RRF's standard constant (Cormack et al.
    # 2009); lower values weight top-ranked-in-any-single-channel facts more
    # heavily, higher values flatten the fusion toward facts that rank
    # decently across several channels rather than winning any one of them.
    retrieval_rrf_k: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_RRF_K", "60")))
    retrieval_abstention_semantic_threshold: float = field(
        default_factory=lambda: float(os.getenv("RETRIEVAL_ABSTENTION_SEMANTIC_THRESHOLD", "0.3"))
    )
    retrieval_abstention_message: str = field(
        default_factory=lambda: os.getenv("RETRIEVAL_ABSTENTION_MESSAGE", "I don't have that information in my memory.")
    )

    # -- Ingestion concurrency ---------------------------------------------
    ingestion_executor_max_workers: int = field(default_factory=lambda: int(os.getenv("INGESTION_EXECUTOR_MAX_WORKERS", "1")))

    # How many chunks `IngestionOrchestrator.run_batch` groups together before
    # flushing the graph write and the embedding/search-index write, instead
    # of one write per chunk. Not threading -- HydraDB serializes writes to
    # one `cell_id` through a single server-side mutex lane regardless of
    # client concurrency (verified live this session, see
    # docs/fixes_and_evaluation_findings.md §3.3) -- fewer, bigger calls,
    # the same lesson §3.2 already proved for the Postgres side. Extraction
    # (already parallelized via `PrefetchingExtractor`) and per-chunk
    # verification/job-state transitions are unaffected by this and stay
    # per-chunk; only the physical graph-write and embedding-write calls are
    # batched across the group. 1 disables grouping (identical to the
    # original per-chunk behavior, still the default for any caller that
    # only ever ingests one turn at a time, e.g. `MemoryEngine.add_turn_async`).
    #
    # 100, not the original 10: live-measured on a clean 100-turn slice
    # (real Postgres+HydraDB, contamination-free -- unique context per run,
    # warm embedder excluded from timing), grouping monotonically improved
    # with size right up to 100 (10=70.8s, 25=54.1s, 50=24.9s, 100=14.1s --
    # see docs/fixes_and_evaluation_findings.md §3.10). Safe to push this
    # high because `GraphWriter`'s per-call row cap (see
    # `DEFAULT_MAX_ROWS_PER_WRITE`) now splits any bucket that would exceed
    # HydraDB's real admission-control limit, discovered live at this same
    # group size before that cap existed -- grouping more chunks can only
    # cost more physical calls once a bucket needs splitting, never fail
    # outright. Not tested past 100 (the largest slice measured); raise
    # further only with the same kind of live measurement backing it.
    ingestion_write_batch_size: int = field(default_factory=lambda: int(os.getenv("INGESTION_WRITE_BATCH_SIZE", "100")))

    # -- Storage / transport connection settings ---------------------------
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "CONTEXT_MEMORY_DATABASE_URL",
            os.getenv("DATABASE_URL", "postgresql://context_memory@127.0.0.1:54329/context_memory"),
        )
    )
    hydradb_url: str = field(
        default_factory=lambda: os.getenv(
            "CONTEXT_MEMORY_HYDRADB_URL", os.getenv("HYDRA_DB_HOST", "http://127.0.0.1:8080")
        )
    )
    # A single shared, non-pooled psycopg connection was reachable
    # concurrently from FastAPI's request-thread handlers and the background
    # ingestion executor -- a thread's own read-back verification could see
    # `True` (Postgres shows a session its own uncommitted writes) just
    # before an unrelated concurrent thread's rollback on that same
    # connection silently discarded it. `min_size`/`max_size` need tuning
    # against real deployed concurrency; these defaults are a starting
    # point, not a measured final value.
    postgres_pool_min_size: int = field(default_factory=lambda: int(os.getenv("CONTEXT_MEMORY_POSTGRES_POOL_MIN_SIZE", "2")))
    postgres_pool_max_size: int = field(default_factory=lambda: int(os.getenv("CONTEXT_MEMORY_POSTGRES_POOL_MAX_SIZE", "10")))
    postgres_pool_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("CONTEXT_MEMORY_POSTGRES_POOL_TIMEOUT_SECONDS", "30")))
    hydradb_token: str = field(
        default_factory=lambda: os.getenv(
            "CONTEXT_MEMORY_HYDRADB_TOKEN",
            os.getenv("HYDRA_DB_API_KEY", "context-memory-local-smoke-token-32b"),
        )
    )
    hydradb_database: str = field(
        default_factory=lambda: os.getenv("CONTEXT_MEMORY_HYDRADB_DATABASE", os.getenv("HYDRA_DB_GRAPH_ID", "default"))
    )
    hydradb_request_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("HYDRADB_REQUEST_TIMEOUT_SECONDS", "15"))
    )
    # Phase 5 (harness plan): every LLM call recorded to `journal_steps`,
    # wrapped once at the composition root (see composition.py). On by
    # default -- a journal outage never breaks a request (StepJournal.record
    # swallows its own errors), so there's no live-traffic reason to default
    # this off.
    step_journal_enabled: bool = field(
        default_factory=lambda: os.getenv("STEP_JOURNAL_ENABLED", "1").lower() not in ("0", "false", "no")
    )

    # -- Prompts (wording lives in core/prompts.py; fields here so a caller
    #    can override per-instance without editing source) ------------------
    entity_resolution_system_prompt: str = ENTITY_RESOLUTION_SYSTEM_PROMPT
    temporal_update_system_prompt: str = TEMPORAL_UPDATE_SYSTEM_PROMPT
    batched_temporal_update_system_prompt: str = BATCHED_TEMPORAL_UPDATE_SYSTEM_PROMPT
    fact_extraction_system_prompt: str = FACT_EXTRACTION_SYSTEM_PROMPT
    batched_fact_extraction_system_prompt: str = BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT
    # AI-DND memory-layer contract: narrative-content sibling of the two
    # fields above, used only for runtime turn-batch/scenario-template
    # ingestion (see ingestion/orchestrator.py's `_extraction_service_for`).
    # Env-overridable (unlike the two chat-tuned fields above, which stay
    # bare defaults) -- this pair has no LongMemEval-equivalent benchmark to
    # protect, so following rerank_system_prompt/duration_query_guidance's
    # override-friendly pattern here costs nothing and helps hand-tuning.
    narrative_fact_extraction_system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT", NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT
        )
    )
    batched_narrative_fact_extraction_system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "BATCHED_NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT", BATCHED_NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT
        )
    )
    temporal_resolver_system_prompt_template: str = TEMPORAL_RESOLVER_SYSTEM_PROMPT_TEMPLATE
    query_rewriter_system_prompt: str = QUERY_REWRITER_SYSTEM_PROMPT
    reader_system_prompt_template: str = READER_SYSTEM_PROMPT_TEMPLATE

    def harness_snapshot(self) -> dict[str, object]:
        """Phase 8: the config every eval run should be recorded alongside.

        The §4 bug (`retrieval.py:305` silently falling back to a rerank
        model different from the one the 76.7% baseline was measured with,
        because neither composition root passed it) is exactly what happens
        when a benchmark number is reported without knowing what harness
        config produced it -- Harness-Bench's own stated discipline is
        recording the config with every number, not assuming it never
        drifts. One dict, every role's model plus the knobs measured to
        move the score (rerank on/off, retrieval_top_k)."""
        return {
            "extractor_model": self.extractor_model,
            "entity_resolution_model": self.entity_resolution_model,
            "temporal_update_model": self.temporal_update_model,
            "reader_model": self.reader_model,
            "temporal_resolver_model": self.temporal_resolver_model,
            "query_rewriter_model": self.query_rewriter_model,
            "rerank_model": self.rerank_model,
            "retrieval_rerank_enabled": self.retrieval_rerank_enabled,
            "retrieval_top_k": self.retrieval_top_k,
            "step_journal_enabled": self.step_journal_enabled,
        }

    def _client(self, api_key: str, model: str, reasoning_effort: str | None = None) -> LLMClient:
        # Vertex AI migration: no `base_url` anymore -- `LLMClient` talks to
        # Vertex via `google-genai`'s API-key auth mode
        # (`genai.Client(vertexai=True, api_key=...)`), which resolves its
        # own endpoint internally. See `core/llm_client.py`'s module
        # docstring.
        return LLMClient(
            api_key=api_key, model_name=model,
            sdk_max_retries=self.llm_sdk_max_retries,
            reasoning_effort=reasoning_effort if reasoning_effort is not None else self.llm_reasoning_effort,
            rate_limit_max_retries=self.llm_rate_limit_max_retries,
            schema_format=self.llm_schema_format,
            seed=self.llm_seed,
            service_tier=self.llm_service_tier,
        )

    def get_entity_resolution_client(self) -> LLMClient:
        # Own reasoning_effort, not the global `llm_reasoning_effort` --
        # different Gemini tiers may accept different `thinking_level`
        # ranges. Empty string omits the param entirely (provider default),
        # same convention as `llm_reasoning_effort` itself.
        effort = self.entity_resolution_reasoning_effort or None
        return self._client(self.entity_resolution_api_key, self.entity_resolution_model, effort)

    def get_temporal_update_client(self) -> LLMClient:
        # Own reasoning_effort -- same convention as get_entity_resolution_client
        # above, see temporal_update_reasoning_effort's field comment.
        effort = self.temporal_update_reasoning_effort or None
        return self._client(self.temporal_update_api_key, self.temporal_update_model, effort)

    def get_extractor_client(self) -> LLMClient:
        return self._client(self.extractor_api_key, self.extractor_model)

    def get_reader_client(self) -> LLMClient:
        return self._client(self.reader_api_key, self.reader_model)

    def get_temporal_resolver_client(self) -> LLMClient:
        effort = self.temporal_resolver_reasoning_effort or None
        return self._client(self.temporal_resolver_api_key, self.temporal_resolver_model, effort)

    def get_query_rewriter_client(self) -> LLMClient:
        effort = self.query_rewriter_reasoning_effort or None
        return self._client(self.query_rewriter_api_key, self.query_rewriter_model, effort)
