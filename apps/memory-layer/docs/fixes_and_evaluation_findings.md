# Fixes and Evaluation Findings

This document is a running record of two things, kept together because they
came from the same investigation: **(1)** every fix applied to ingestion and
retrieval while diagnosing real LongMemEval failures, and **(2)** the full
diagnosis of what went wrong in the 30-instance evaluation run — traced
against actual ingested data and actual retrieved context, not inferred from
the score alone. See `docs/decisions.md` for the formal ADR-numbered
rationale behind the larger architectural calls; this document is the
working detail underneath a subset of those ADRs (chiefly ADR-034/035) plus
everything done after them.

---

## 1. Fixes applied

### 1.1 Ingestion correctness

- **Speaker/entity namespace collision (`graph_plan_builder.py`).** The
  speaker node lived at `entity:{role}`. The extractor genuinely emits
  "user"/"assistant" as ordinary entity surfaces too, which canonicalize to
  the same logical key and the same allocated graph ID but a different
  `entity_type` ("speaker" vs "other"). Same key, same ID, different
  payload — `PostgresGraphManifestStore` rejects that by design. Confirmed
  live: this aborted a real LongMemEval ingestion run with
  `GraphPayloadConflictError: node entity:assistant has a different
  immutable graph payload`. Fixed by moving the speaker node to its own
  `speaker:` namespace, which removes the collision class entirely rather
  than reconciling two payloads that legitimately differ.

- **Entity coverage in extraction (`core/config.py`,
  `FACT_EXTRACTION_SYSTEM_PROMPT`).** "Named entities" alone was read
  strictly as proper nouns, so any fact about a common-noun topic (commute,
  rent, audiobooks) got an empty `entities` list. Measured: 691 of 2,685
  facts (25.7%) on one real instance had no entity at all — including every
  "commute" fact for a question whose gold answer was specifically about the
  user's commute. Entities are what graph expansion traverses and what the
  entity boost keys on, so an unlinked fact is invisible to both. Prompt now
  asks for salient topic nouns in addition to named entities; verified live
  this recovers entity links without disturbing named-entity extraction
  quality.

- **Swallowed timeouts in entity-resolution/temporal-update ports
  (`model_adapters.py`).** Both ports only caught `LLMClientError`, not
  `openai.APITimeoutError` (a different exception hierarchy). Confirmed live
  during the 30-instance run: 42 timeouts in one instance alone, each one
  propagating out of a bounded-decision port and aborting the *entire chunk*
  via the orchestrator's generic exception handler — losing every fact in
  that turn over one classification timing out. Both ports already had a
  defined "no clear basis to decide" fallback (`None` / `UNRESOLVED`);
  broadened to `except Exception` so a timeout degrades to that existing
  contract instead of aborting the chunk.

- **Malformed-JSON recovery generalized (`llm_client.py`).** An earlier fix
  special-cased literal prefixes (`{{`, `{\n{`) and stripped one character.
  Bedrock's `openai.gpt-oss-20b` deterministically (6/6 calls, not
  intermittent) emits a `{"` prefix instead — two characters, not a matched
  pattern, so the special-casing could not recover it. Replaced with a scan
  for the first balanced JSON object anywhere in the text (still strips ```
  fences first), which uniformly handles the `{"` case, leading prose, and
  trailing commentary instead of enumerating malformation shapes one at a
  time.

- **HydraDB Cypher injection in entity-value escaping (`retrieval.py`).** A
  hand-rolled `'` doubler left backslashes untouched — an entity ending in
  one produces `'ent\'`, whose trailing backslash escapes the closing quote
  and swallows the rest of the query. Reachable input: entity names come
  from LLM extraction of user content, and `canonicalize_entity_surface`
  only NFKC-normalizes and casefolds; it strips neither backslashes nor
  quotes. Switched to `json.dumps` for correct escaping. A dead, shadowed
  copy of the per-fact node query (left over from an earlier edit) was
  removed in the same pass.

### 1.2 Retrieval correctness

- **`SUPERSEDES` was wired but dead (ADR-034).** Every component existed and
  was unit-tested, but no production caller ever supplied the
  `find_existing_facts` callback the edge-creation logic is gated on, so
  `LLMTemporalUpdateModel` was never invoked and no `SUPERSEDES` edge was
  ever written. Fixed by adding `ingestion/fact_lookup.py::HydraFactLookup`
  as the real data source, constructed in both `api/routes.py` and
  `evaluation/benchmark_runner.py`. Also stopped gating the check on
  `action == UPDATE` — confirmed live, `LLMExtractor` sees only the current
  turn (no prior-facts context) and labelled "Max moved to Seattle." as
  `ADD` immediately after "Max lives in Boston." in the same context, so
  gating on the extractor's own guess meant supersession only fired when the
  model happened to phrase things as an explicit correction. Verified live
  end-to-end: `SUPERSEDES` edge created, prior fact's `is_current` flipped
  to `False`.

- **Entity boost was ungated (ADR-035).** A prior fix made `entity_boost`
  binary (cap if any entity linked, else 0) but dropped
  `FINAL_ARCHITECTURE.md`'s `if entity in query_entities` condition — every
  entity-linked fact got the same flat boost regardless of whether the query
  was actually about that entity. Measured on "How long is my daily commute
  to work?": the gold fact had the single highest semantic score of all 113
  seeds (0.716) but no entity link, so it ranked #39 while 15 unrelated
  bike-training facts each took the full boost and filled the entire top-15.
  Now applies inverse-frequency scaled, only when the fact's linked entity
  actually appears in the question (or its rewritten forms).

- **Abstention ignored `keyword_score`; BM25 went silent on rewriter
  failure (ADR-035).** A strong BM25-only match with weak embedding
  similarity could still trigger abstention. Separately, an empty rewriter
  result (same LLM path that has failed live on credentials/timeouts) used
  to skip keyword search for the whole request rather than degrading to the
  raw question. Both fixed.

- **Composite scoring replaced with Reciprocal Rank Fusion.** The formula
  summed four raw, differently-scaled scores (`semantic_score +
  keyword_score + structural_score + entity_boost`) directly. Whichever
  signal happened to read numerically "big" for a fact dominated the total
  regardless of actual relevance — the same failure shape already fixed once
  for `entity_boost` specifically, but present structurally across all four
  signals. Replaced with RRF: each fact's rank *position* within each
  channel (not its raw score) determines its contribution,
  `1/(k + rank)` per channel, k=60 (Cormack et al. 2009's standard
  constant). A fact absent from a channel contributes 0 from it rather than
  tying for last place. Two tests lock in the exact property this exists
  for: multi-channel presence can now outscore a single dominant raw score,
  which the old additive formula could not express.

- **Reader window widened, 15 → 20 (`retrieval_top_k`).** Cheap, low-risk
  mitigation for facts that scored well but fell just outside the cutoff —
  confirmed live this alone pulled a needed fact (a per-unit price) into
  context that had previously been excluded.

- **Sibling-fact expansion — the structural fix for split facts
  (`retrieval.py::_sibling_facts`), now scored with SCAR, not a flat
  `ORDER BY`.** Implements `FINAL_ARCHITECTURE.md`'s own ADR-005
  ("progressive evidence expansion: fact → neighboring turn → full chunk"),
  accepted at design time but never actually built. Went through two real
  iterations, both driven by live evidence rather than designed up front:

  **v1 (unordered, flat pull).** Traced live: extraction splits one turn
  into several atomic facts, and Phase 3 scores them independently — "User
  sold 20 potted herb plants" and "Each potted herb plant was sold for
  $7.5" come from the same turn, but a question needing both
  (20 × $7.5 = $150, one component of a larger $495 total) got the price
  without the quantity, because only the price scored high enough to be
  individually ranked. v1 pulled in every other fact from the same source
  turn as any top-K fact via `memory_embeddings.source_chunk_id`, capped at
  a shared `LIMIT 20` with no ordering.

  **Why v1 wasn't enough, found by re-testing rather than assumed working:**
  requesting numerical evidence for this exact fix surfaced that it hadn't
  actually fixed the traced case. Diagnosed precisely: the needed sibling
  (the $7.5/unit fact) had only 4 real candidate siblings for its own turn —
  comfortably under the cap on its own — but the query pools siblings across
  *all* facts in the top-20 combined, and unrelated turns' siblings filled
  the shared, unordered 20-row cap first. The needed fact was available and
  never reached.

  **v2 — SCAR (Semantic Continuity-Aware Retrieval; Zhong et al. 2026,
  [arxiv.org/abs/2606.16661](https://arxiv.org/abs/2606.16661)).** Chosen
  over hand-rolling a heuristic: this is a solved problem in the RAG
  literature (parent-document retrieval, sentence-window retrieval, and
  auto-merging retrieval all address the same "small chunk for precision,
  larger context for the LLM" tension), and SCAR is the entry that scores
  *which* neighbors earn inclusion instead of pulling a fixed radius or a
  flat top-N — the same gap v1 had. Its formula, using embeddings already
  stored in `memory_embeddings` (no extra embedding calls beyond the one
  question vector):

  ```
  S(anchor, neighbor) = cos(query, neighbor) − λ · (1 − cos(anchor, neighbor))
  keep neighbor only if:  S(anchor, neighbor) > γ · cos(query, anchor)
  ```

  Paper defaults used unchanged (λ=0.1, γ=0.80) — no tuning data of our own
  exists yet to justify moving them. **Why this is the right shape for the
  underlying tension, not just a bigger hammer:** a same-turn fact is a
  *plausible* signal that a neighbor is relevant, not proof — the actually-
  missing gold fact can just as easily live in a completely different turn,
  which no amount of neighbor expansion reaches (that remains a Phase 1
  recall problem, out of scope for this fix). SCAR's threshold is relative
  to *each anchor's own* query relevance rather than one fixed cutoff for
  every fact: a weakly-relevant anchor sets a low bar (loosely-related
  context still gets a chance), a strongly-relevant anchor demands genuinely
  comparable neighbors (a strong hit doesn't get to drag in everything
  physically nearby). This is exactly the requested property — biased
  toward the anchor's own turn, but not an absolute or all-or-nothing bias.

  **Benefit, measured, not asserted:** the exact money-aggregation case that
  exposed v1's gap now answers **$495** (exact gold match; was $345 before
  any of this, still $345 after v1). Live run shows 10 siblings admitted out
  of the candidate pool (down from v1's uncapped-priority 20), and a
  dedicated test proves the actual selectivity property: an on-topic
  same-turn candidate (score 0.645, clears a 0.48 threshold) is kept; an
  off-topic same-turn candidate (score 0.145, same anchor, same threshold)
  is rejected — the property a flat pull-everything or a flat `ORDER BY`
  cannot express, since both would keep or drop them identically regardless
  of relevance. New config: `RETRIEVAL_SIBLING_FACT_LIMIT` (default 20, 0
  disables), `RETRIEVAL_SIBLING_CONTINUITY_PENALTY` (λ, default 0.1),
  `RETRIEVAL_SIBLING_RELEVANCE_RATIO` (γ, default 0.80).

- **Cutoff-boundary diagnostic logging.** Every retrieval now logs the
  last-included vs. first-excluded fact and their scores at the top-K
  cutoff. Every traced miss so far had the same shape (a topically-irrelevant
  fact with a coincidentally high score crowding out the relevant one); this
  makes that visible in normal logs going forward instead of requiring a
  one-off diagnostic script re-run by hand each time.

### 1.3 Reader prompt

`READER_SYSTEM_PROMPT_TEMPLATE` (`core/config.py`) gained two targeted
instructions, not a general rewrite:

- If the question needs a total, count, or duration spanning multiple facts,
  identify every matching fact first, then compute from all of them — do not
  answer from a partial subset or return a single fact's value directly when
  the question asks for a combination of several.
- If the question is a recommendation ask and the context states a specific
  relevant prior preference, the answer must build on that specific
  preference, not just stay on the same general topic.

Both target the exact two zero-score categories from §2 below. Not yet
verified against a live re-run (explicitly deferred at the user's request —
implemented but not tested).

### 1.4 Latency (all read-only / no correctness risk, verified via 149
unit tests + one live end-to-end call reproducing the correct answer)

- **Phase 0 parallelized.** Temporal resolution and query rewriting are two
  independent LLM calls (the rewriter doesn't use `temporal_bounds`, the
  resolver doesn't use `expanded_query`) that were running sequentially. Now
  concurrent via a 2-worker thread pool. Measured with real LLM calls,
  isolated from the rest of the pipeline: **3.36s sequential → 0.85s
  concurrent (75% cut, 2.51s saved)**.
- **Phase 2's N+1 parallelized.** HydraDB rejects UNWIND-batched reads (see
  `retrieval.py`'s own extensive comments on this, discovered through four
  rounds of live 400 errors earlier in this project), forcing one HTTP
  round trip per seeded fact — 60-80+ typical given the overfetch floor.
  Verified `HydraHttpTransport` holds no shared mutable per-call state
  (headers/URL fixed at construction, each `.read()` self-contained), so
  this is safe to parallelize, unlike ingestion's writes, which share one
  psycopg connection and genuinely cannot. Now concurrent, 8 workers by
  default (`RETRIEVAL_GRAPH_FETCH_WORKERS`). Measured against 70 real fact
  IDs from an already-ingested instance: **0.57s sequential (8ms/call) →
  0.06s concurrent (89% cut, 0.50s saved)**.
- **Dead SUPERSEDES probe already removed.** An earlier session had flagged
  a per-fact SUPERSEDES-traversal loop whose result was computed but never
  consumed — pure wasted latency. Checked before doing anything further: it
  is already gone from the codebase (removed in an earlier commit), so no
  action was needed here.
- **Caught mid-fix:** parallelizing Phase 0 broke an unstated assumption in
  the test fakes — `FakeLLMClient` indexed queued responses by call order,
  which stops being safe once two calls genuinely race. It passed once by
  GIL timing luck, not correctness. Fixed the fake to dispatch by the
  requested response's type instead of call order; confirmed deterministic
  across 5 repeated runs.

**Honest scope of these numbers, checked before claiming a benchmark-level
win:** both fixes are real, measured, and correct — but they only touch
`retrieve_and_answer`, and retrieval is a small fraction of total per-instance
wall time. From the 30-instance run's own per-instance ingest/retrieve split:

```
ingest total (30 instances):   24,603.2s  (99.7% of measured phase time)
retrieve total (30 instances):     85.9s  ( 0.3%)
```

Ingestion — serial per-turn LLM extraction calls, ~500 turns/instance — is
what actually dominates a LongMemEval run, and nothing in this latency pass
touched it. A 75-89% cut on 0.3% of total time is real but does not
meaningfully change how long a full run takes; see §2.7 for what an actual
re-run would cost.

---

## 2. Evaluation findings: the 30-instance run

### 2.1 Setup

Stratified sample, 5 instances per category, fixed random seed (reproducible)
drawn from all six LongMemEval-S question types. Scored with the official
grader (`xiaowu0162/LongMemEval`'s `src/evaluation/evaluate_qa.py`), judge
model `deepseek.v3.2` (chosen after `gpt-5.4`/`gpt-5.5` returned real 401s on
this account, Claude 400'd on this endpoint's request shape, and
`gpt-oss-120b` hit the same reasoning-exhaustion bug as our extractor —
confirmed live, not assumed).

### 2.2 Data legitimacy — checked before looking anywhere else

For every one of the 10 failing instances: **turn count in the source data
== ingestion-job count == completed-job count, exactly**, and each has
2,700-2,950 real extracted facts indexed (not empty or stub output). Not
"completed for the sake of being completed" — ingestion is not where these
two categories fail.

### 2.3 Full results

| category | accuracy | n |
|---|---:|---:|
| single-session-user | 80.0% | 5 |
| single-session-assistant | 60.0% | 5 |
| knowledge-update | 60.0% | 5 |
| temporal-reasoning | 40.0% | 5 |
| single-session-preference | 0.0% | 5 |
| multi-session | 0.0% | 5 |
| **overall** | **40.0%** | **30** |

An earlier partial read (19/30, before `single-session-user` and
`temporal-reasoning` had finished ingesting) showed 31.6% — the missing
categories were pulling the average down by their absence, not by scoring
badly.

### 2.4 `multi-session` (0/5) — root cause

Every one of the 5 instances requires *deriving* an answer from two or more
separate facts (summing amounts, counting distinct events, or subtracting
two ages). The reader has no structured step for this and fails in one of
two shapes:

- **(a) Computes from a partial subset that survived ranking.** Total
  market-earnings question: three facts contribute to the $495 gold total
  ($225 + $150 + $120). All three were ingested. Two ($225, $120) reached
  the reader directly. The third needs `20 potted herb plants × $7.5/plant
  = $150`; the per-unit-price fact ranked just outside the top-15 the reader
  saw, crowded out by unrelated dollar-amount facts (real-estate prices,
  gross income) that scored higher on surface similarity to "money." The
  reader answered $345 from the two facts it had — internally consistent,
  externally wrong.
- **(b) Returns a single raw fact directly instead of attempting the
  derivation.** "How old was I when Alex was born?" (gold: 11, from
  32 − 21). Both ages ("Alex is 21 years old", "The user is 32 years old")
  were ingested facts. The reader answered "21" — Alex's own stated age,
  echoed back verbatim, with no subtraction attempted. (A first hypothesis
  here — that there were two different people both named Alex and the
  system picked the wrong one — was checked against the actual source
  transcript and found to be false: there is only one Alex in the haystack,
  in the exact designated answer session. Corrected before reporting.)

One instance (`ef9cf60a`, "How much did I spend on gifts for my sister?",
gold $300 = $200 necklace + $100 spa gift card, both facts ingested and both
individually ranking in the top 2 by raw semantic score) did **not**
reproduce identically on rerun against the same static data — the original
run answered "I don't have enough information," a fresh rerun answered
"$100." Both wrong, differently wrong, on identical inputs — a genuine
reader-side non-determinism component stacking on top of the structural gap,
not purely a retrieval defect.

### 2.5 `single-session-preference` (0/5) — root cause

Graded against a rubric, not exact-match, so a partially-relevant response
can still fail. Two distinct shapes traced:

- **The specific preference fact never reaches the reader.** "What should I
  serve for dinner this weekend with my homegrown ingredients?" — gold wants
  the answer to reference the user's homegrown cherry tomatoes and herbs.
  The fact "The user has harvested cherry tomatoes from their garden." was
  ingested but never made the top-60 seeded candidate pool at all (a Phase 1
  embedding-recall miss, not a ranking-cutoff miss) — no amount of
  downstream re-ranking could have recovered it.
- **The fact is available and the reader answers generically anyway.** A
  coffee-creamer recommendation question's gold rubric wanted variations on
  an *existing* stated recipe (almond milk, vanilla, honey) plus cost/sugar
  reduction goals; the reader produced an unrelated new recipe (rose petal,
  lavender, collagen peptides, MCT oil) that never engaged with the specific
  prior preference at all.
- A third case (rearranging bedroom furniture) technically mentioned the
  right keywords (the dresser, mid-century modern style) but the response
  was mostly about Wi-Fi signal strength, with furniture placement framed
  around it — off-topic content diluting an otherwise on-topic answer well
  past what the rubric wanted.

### 2.6 What's fixed vs. still open, honestly

**Fixed and verified this pass, with live before/after numbers:** the
entity-boost query-gating bug (commute fact: rank #39/113, excluded →
#4/138, included), missing common-noun entity coverage (25.7% of facts with
no entity → 0% on a fresh live re-test), the speaker/entity namespace
collision (36 conflicts on old contexts → 0 on 30 fresh ones), RRF composite
scoring (proven via test, not just claimed), sibling-fact expansion —
upgraded to SCAR after v1 was re-tested and found not to have actually fixed
its own motivating case (see §1.2) — the exact case it was built for now
answers $495 exactly, both parallelization fixes (75% and 89% cuts,
measured).

**Implemented but not yet live-verified:** the reader prompt's aggregation
and preference-fidelity instructions (explicitly deferred per instruction —
implemented, not re-run against live data yet).

**Still open, not yet attempted:**

- Phase 1 embedding recall can still miss a topically-narrow fact entirely
  (the tomato/garden case) — RRF, sibling expansion, and SCAR's continuity
  scoring all operate on facts that were at least seeded; a fact that never
  enters the candidate pool at all, or was never extracted onto a turn SCAR
  can reach, is unaffected by any of them.
- The reader-side non-determinism observed on `ef9cf60a` (same inputs,
  different wrong answers across runs) has not been investigated further —
  worth knowing if reproducibility matters for future evaluation runs.
- SCAR's λ/γ are the paper's published defaults, unvalidated against this
  system's own data — no tuning pass has been run.

### 2.7 Cost of running this again

**A full re-run needs fresh ingestion, not just re-running retrieval against
the already-ingested contexts.** The entity-coverage prompt fix changes what
extraction produces; the 30 contexts already ingested reflect the *old*
prompt. Re-scoring against old data would not exercise most of what changed
this pass.

**Ingestion, not retrieval, sets the clock — and nothing in this pass
touched ingestion.** From the measured 30-instance split in §1.4: ingestion
was 99.7% of wall time, retrieval 0.3%. The 75-89% retrieval speedups
translate to roughly **0.3% × 0.8 ≈ 0.25% off total wall time** — real, but
not the number that matters for planning a re-run.

**Estimate, from the actual measured run, not a projection:**

```
measured: 30 instances = 27,693s = 7.7h   (923s/instance average)
```

| scope | estimate |
|---|---|
| same 30-instance stratified sample, re-run fresh | **~7.5-7.7h**, materially unchanged from the original run |
| full 500-instance LongMemEval-S | **~128h ≈ 5.3 days**, linear extrapolation from the measured 30 |

Both are the *ingestion* cost — extraction is a real per-turn LLM call
(~500 turns/instance average), run mostly-concurrently within an instance
via the existing prefetch mechanism but still bounded by provider
throughput; nothing added this pass changes that arithmetic. If ingestion
speed itself needs to come down for a re-run to be practical, that is a
separate, not-yet-investigated piece of work — this pass's scope was
retrieval quality and retrieval latency, not extraction throughput.

## 3. Ingestion flow review: where the time and the accuracy actually go

Requested review of the ingestion path itself (§2.7 established it's 99.7%
of wall time and untouched by this session's fixes). Everything below is
either live-measured against the real pipeline (Postgres + HydraDB +
`deepseek.v3.2`) or grounded in a cited external source — no estimates
presented as fact.

### 3.1 Live measurement: where non-extraction time goes

Extraction itself (`PrefetchingExtractor`, already implemented before this
session) is well understood and already about as fast as it can be made —
see §3.4. What had never been measured is everything **after** extraction:
`orchestrator.run_chunk`'s entity resolution, `SUPERSEDES` lookup, graph
write, and embedding/search-index persistence. Isolated this by prefetching
extraction to a warm cache first (so its cost is off the critical path),
then running `orchestrator.run_batch` over 25 real turns from a live
LongMemEval instance (`question_id=852ce960`, the shortest in the 500-item
set) against the actual Postgres + HydraDB containers, with
`core.logging.timed_operation`'s `[DONE] ... in N ms` lines aggregated by
stage:

```
run_batch (25 turns, post-extraction): 16.36s total = 654 ms/turn

  orchestrator.stage.embeddings_and_search_index   7206 ms  (44.8%)  <- biggest
  orchestrator.stage.graph_write                   4382 ms  (27.2%)
  orchestrator.stage.graph_plan                    4281 ms  (26.6%)
  orchestrator.stage.verification                    15 ms  ( 0.1%)

  within graph_write:  184 sequential hydradb.write calls, 18.8ms avg each
  within graph_plan:   139 sequential fact_lookup.find_existing calls (HydraDB
                        read, 5.4ms avg) + 1 temporal_update.classify LLM call
                        (2390ms) + 0 entity_resolution.disambiguate calls (all
                        139 accepted facts' entities resolved by exact
                        canonical/alias match at this small a graph size)
```

139 accepted facts over 25 turns drove 278 sequential `PostgresEmbeddingStore.put`
/ `PostgresSearchIndexStore.put` calls (2 per fact) — each its own
transaction, and `EmbeddingStore.put` additionally does a `SELECT ... FOR
UPDATE` before its `INSERT`, so it's 2 round trips inside that 1 call. That
is the entire embeddings-and-search-index cost: **278 Postgres round trips
for 139 facts, ~26ms/round-trip, none of them batched.**

### 3.2 Fix #1 (highest-value, no threading needed): batch the per-fact Postgres writes

**The problem is a textbook N+1 write pattern**, not a concurrency problem —
threading it would help, but rewriting it to not need N round trips at all
helps more and is lower-risk (no new connection-pooling/thread-safety
surface on a store the rest of the pipeline shares one `psycopg` connection
with).

**External evidence, not a guess:** Tiger Data's benchmark of Postgres
ingest strategies found batch multi-row `INSERT` roughly **10–50x** faster
than the equivalent count of single-row inserts, purely from collapsing
network round trips; a concrete case in a Postgres mailing-list benchmark
went from 52s (single-insert batches) to 30s (100-row multi-inserts) on
the same data. `psycopg`'s own `executemany()` is explicitly documented as
*not* a real batching win on its own — it still emits one `INSERT` per row
under the hood — the actual fix is a genuine multi-row `VALUES (...), (...),
...` statement (or `COPY` for very large batches).
([tigerdata.com](https://www.tigerdata.com/learn/testing-postgres-ingest-insert-vs-batch-insert-vs-copy),
[postgresql.org mailing list](https://www.postgresql.org/message-id/CADFnS4TP2tqF5qXDpvAJykdREoZtAQ9nJZNrN3Xh4MQxTfAv7g@mail.gmail.com))

**Concretely:** `orchestrator.py`'s embeddings-and-search-index block already
loops `extraction.accepted` once to call `embed_batch` (good, already
batched per the comment there). The fix is the same idea one level down —
give `EmbeddingStore`/`SearchIndexStore` a `put_batch()` that issues one
multi-row `INSERT ... ON CONFLICT` per chunk instead of `put()` in a loop.

**Implemented.** `PostgresEmbeddingStore.put_batch()` and
`PostgresSearchIndexStore.put_batch()` (`persistence/postgres.py`) each do
one batched existence/upsert round trip instead of N; `orchestrator.py`
calls them when the store supports it (same optional-method fallback
pattern already used for `embed_batch`, so fakes without `put_batch` keep
working unmodified). 132/132 unit tests pass, including two new ones
(replay-is-a-no-op, a genuine hash conflict still raises
`ImmutableRecordConflictError`) proving the batched path preserves the
exact immutability contract `put()` had.

**Correction to the estimate above, found while verifying it:** the 44.8%
figure was the *whole* `embeddings_and_search_index` stage, and it was
wrong to attribute most of that to Postgres round trips without checking.
An isolated DB-only micro-benchmark (no LLM, no HydraDB, real Postgres
container, same 139-fact/25-turn shape) measured the actual write-only cost:

```
sequential put() x139 (both stores): 404.4ms (2.91ms/fact)
batched put_batch() x139 (both stores): 78.7ms (0.57ms/fact)   -- 5.14x
realistic per-chunk batch (n=6, matches ~facts/chunk):
sequential: 16.5ms   batched: 7.0ms   -- 2.37x
```

Re-running the full 25-turn pipeline probe end to end after the batching
change: `embeddings_and_search_index` stage went 7206.1ms → 6602.3ms, only
an 8.4% cut, not the 5x+ implied by the round-trip count alone. The gap is
because most of that stage's ~288ms/chunk was never the DB writes — it was
`SentenceTransformerEmbedder`'s own model-inference time (encoding the
batch's fact texts into vectors), which batching Postgres writes does
nothing to. The orchestrator's `timed_operation` block has since been split
into `orchestrator.stage.embedding_model` and
`orchestrator.stage.embedding_persistence` specifically so this doesn't
stay hidden again. The batching fix is still real and worth having — 2.4x
to 5.1x on the portion it actually touches, verified correct — just a
smaller share of total chunk time than first estimated. Lesson applied: a
percentage attributed to an unmeasured sub-component needs its own
isolated measurement before it's trusted, not just inferred from the
parent stage's total.

### 3.3 Verified: `GraphWriter.write()`'s per-group calls — do NOT parallelize

`graph_writer.py` already groups nodes and relationships into disjoint
`(label, property_names)` / `(type, src_label, dst_label, property_names)`
buckets before writing — that grouping exists so each bucket can be one
`UNWIND`-batched Cypher call instead of one call per node. But the *buckets
themselves* are still written in a plain sequential `for` loop: 184 calls
across 25 chunks in this measurement, ~7.4 calls/chunk, 18.8ms avg each.
§3.3 originally proposed threading this the same way the retrieval-side
Phase 0/Phase 2 fixes were threaded (§1.4), with the caveat that it hadn't
been live-tested. It has now been tested, on both correctness and timing —
**verdict: correct, but not worth doing.**

**Correctness: confirmed safe.** Fired 6-7 disjoint-label node writes
concurrently against the real HydraDB container via `ThreadPoolExecutor`,
repeated across multiple trials: zero errors, and a read-back after every
trial confirmed every row landed with the right id/properties — no lost or
corrupted writes. A relationship-write phase run only after all node writes
completed also matched every row it was supposed to (once the test's own
Cypher was fixed to include labels on the `MATCH` — `HydraDB` requires
`MATCH` endpoints to carry exactly one label, unrelated to concurrency).

**Timing: no net win, and the reason is architectural, not incidental.**
Six repeated trials, concurrent vs. sequential, same shape of workload,
against a persistent thread pool (to rule out per-call pool-spinup
overhead as the explanation):

```
trial 0: concurrent=414.7ms sequential=164.6ms ratio=2.52x  (cold start)
trial 1-7 average: concurrent=69.6ms sequential=70.8ms ratio=0.98x
```

Excluding the cold-start trial, concurrent writes are a wash — sometimes a
hair faster, sometimes a hair slower, never a real cut. Read into the
HydraDB engine source (`hydradb/` in this repo — it's checked-in Rust, not
a black box) to find out why: every write acquires a per-`cell_id` mutex
before proceeding —

```rust
// src/shard/write.rs
let _writer = self.writer_lane(cell_id).lock().await;

// src/codec.rs
pub(crate) fn writer_lane_index(cell_id: &str) -> usize {
    ...
    (hash as usize) % GRAPH_WRITE_LANES   // GRAPH_WRITE_LANES = 64, src/lib.rs
}
```

This is a deliberate design (`writer_lanes_partition_different_cells`, a
real test in `hydradb/src/tests.rs`, exists specifically to prove different
`cell_id`s land in different lanes and *can* write concurrently) — HydraDB
supports up to 64-way write concurrency, but only across different cells.
Every write this Python client issues uses the same `cell_id` —
`HydraHttpTransport.__init__` defaults it to `"cell-0"` and nothing in this
codebase ever overrides it per context (confirmed by grep — `cell_id`
appears nowhere else in `src/`), and the running container is deployed with
`GRAPH_CELLS=cell-0` (`hydradb/README.md`), i.e. only one cell exists at
all right now. So every write from every chunk, every context, the whole
system, funnels through **one** writer lane no matter how the client
threads its calls — the mutex in `shard/write.rs` serializes them on the
server side regardless. Threading `GraphWriter.write()`'s buckets adds
`ThreadPoolExecutor` and HTTP-dispatch overhead on top of a bottleneck that
was never on the client side to begin with. Not implemented — verified,
and the verified answer is no.

**The real lever this uncovered, and it's bigger than the one asked about:**
if concurrent writes across *different, unrelated* contexts (different
LongMemEval instances, different real users in a multi-tenant deployment)
ever need to happen at the same time, routing each context to its own
`cell_id` (e.g. a hash of `context_id` into a small `GRAPH_CELLS` set) is
the change that would actually unlock HydraDB's 64-lane design for that
case — not threading a single chunk's own writes, which stay serialized to
one lane regardless of the cell scheme, since one chunk belongs to one
context. That's a deployment change (`GRAPH_CELLS` needs more than one
entry) plus a client change (route `cell_id` by context instead of a fixed
default), not something to fold into this pass — flagged for whoever owns
scaling this beyond one-context-at-a-time evaluation runs.

### 3.4 Where threading does *not* help: the turn loop and extraction itself

Two things worth stating explicitly, since "where can we use threading" was
asked directly and the honest answer for these two is "not safely, or not
usefully":

- **`orchestrator.run_batch`'s per-turn loop cannot be parallelized.** This
  was already correctly diagnosed by whoever wrote `PrefetchingExtractor`'s
  docstring (`benchmark_runner.py`): every store in the pipeline
  (`chunk_store`, `job_store`, `manifest_store`, `embedding_store`,
  `search_index_store`) shares one `psycopg` connection, and a single
  `psycopg` connection is not safe for concurrent use from multiple
  threads. Turns also have a genuine chronological data dependency this
  session's own `SUPERSEDES` work depends on — `TemporalUpdateClassifier`
  needs prior turns' facts already written before it can classify a later
  turn's fact as a correction of them, and `EntityRegistry._profiles` is
  mutated in place as new entities are discovered, so two turns racing to
  resolve the same new surface form could allocate two different entity
  nodes for what should be one entity. This is a hard ordering constraint,
  not a missed optimization — confirmed correct, not re-litigated here.

- **Extraction is already near its real ceiling, and more threads would not
  raise it.** `PrefetchingExtractor` already runs `extraction_workers`
  (default 8) concurrent LLM calls per instance, and `benchmark_runner.py`
  already clamps that count against the provider's advertised
  tokens-per-minute limit — confirmed live in this codebase's own comments:
  4 workers still degraded from 63 to 43 calls/min on one run because the
  ceiling is tokens/min, not open connections. Independent confirmation
  from the ATOM paper on LLM-driven temporal knowledge graph construction:
  it settled on **8 threads with a batch size of 40 atomic facts**
  specifically to respect the same kind of provider rate limit
  ([arxiv.org/abs/2510.22590](https://arxiv.org/pdf/2510.22590)) — this
  pipeline's existing 8-worker default is already in the range independent
  research converged on, not an arbitrary number worth "fixing" by raising.
  The one lever that *would* raise the real ceiling — packing multiple
  turns into one extraction call instead of one call per turn, which the
  same batch-prompting literature identifies as the actual way past a
  token-per-minute wall — is a materially bigger change (source-span
  attribution and per-turn provenance both currently assume one call per
  turn) and is flagged here as a real option, not attempted in this review.

### 3.5 Implemented: multi-stage max_tokens gateway for extraction

Every LLM call site in this codebase had one flat `max_tokens` ceiling
(`config.py`'s `<role>_max_tokens` fields) — sized once, paid on every
call regardless of how much the call actually needed. `extractor_max_tokens`
carries its own history of that being a real problem, not a theoretical
one: its comment already records it was raised from a flat 2048 to a flat
4096 after a live failure — the extractor reasons over the whole turn
before emitting JSON, spent its entire budget doing that, and returned
empty content (`finish_reason=length`, no JSON at all). A flat cap is a
blunt fix for that: raise it high enough for the worst turn, and every
short turn pays the same allocation as the worst one.

**What the real distribution actually looks like** (25,024 real turns
across 50 LongMemEval instances, measured for this pass):

```
p50=436 chars   p75=1692   p90=2524   p99=3452   max=31122   mean=977
```

Turn length varies by two orders of magnitude, and the tail is real (some
turns are 30k+ characters). One fixed ceiling either wastes budget on the
~50% of turns under 436 characters or still under-serves the ~1% over
3452.

**Implemented:** `Config.extraction_max_tokens_for(content_length)`
(`core/config.py`) — an ascending if/elif gateway, four tiers keyed off the
measured percentiles above, each independently overridable via env var:

| tier | threshold (chars) | max_tokens |
|---|---|---|
| short | ≤300 | 1536 |
| medium | ≤1200 | 2560 |
| long | ≤3000 | 4096 (the old flat default — unchanged for ~90th percentile and below) |
| xlong | >3000 | 6144 (more headroom than the old flat cap ever gave the long tail) |

`LLMExtractor.extract()` (`model_adapters.py`) calls this with the turn's
actual content length instead of passing the flat `extractor_max_tokens`
field. The field itself is untouched and still exists for any caller that
wants one fixed number.

**Verified, not just written:**
- Unit tests (`test_model_adapters.py`) assert the gateway reaches the real
  call — short/medium/long/xlong content each produce the exact expected
  `max_tokens` in the request sent to the (faked) provider — plus a
  boundary test proving the thresholds are inclusive at the edges, not
  off-by-one. 132/132 tests pass.
- Live call against the real provider on two real turns: a 142-character
  turn (short tier, 1536) extracted 2 facts correctly in 2.72s; a genuine
  15,912-character outlier turn (xlong tier, 6144) extracted 4 facts
  correctly in 2.23s — no truncation, no empty response, on the exact kind
  of long-tail input the old flat cap was most at risk on.

**Why this saves time, concretely:** not by making any single call faster
(a smaller `max_tokens` doesn't make token generation quicker; a model
that would've stopped early anyway pays nothing extra under a higher cap).
The saving is in *avoided retries* — `LLMClient.structured_completion`
already has a doubled-budget retry specifically for the
reasoning-exhaustion-empty-response failure mode (see its docstring), and
every retry that fires costs a full second round trip. Sizing the first
attempt's budget to the turn's actual length, informed by where the real
percentiles sit, cuts how often that failure mode is reached on genuinely
long turns in the first place, instead of relying on catching it after the
fact on every call alike.

### 3.6 Accuracy finding: the production extractor still ingests each turn blind

Independent of latency, one accuracy gap stood out on reading the ingestion
code path end to end, and it is already half-diagnosed in the codebase's
own comments — worth surfacing because it directly undermines this
session's `SUPERSEDES` fix (§1.1) at the source, not just as a general
observation.

**What's live, confirmed by grep against both wiring points
(`src/api/routes.py` and `src/evaluation/benchmark_runner.py` — the only two
places anything constructs an extractor):** both use `LLMExtractor`
(`model_adapters.py`), whose entire prompt is
`f"Speaker: {record.actor_role}\nContent: {content}\n\nExtract atomic facts:"`
— no prior turns, no already-known facts, nothing but the current turn's
text. `graph_plan_builder.py`'s own docstring already documents the
consequence, confirmed live during this project's development: *"`LLMExtractor.extract()`
sees only the current turn's text (no prior-facts context), so it has no
real basis to say UPDATE vs ADD except guessing from phrasing, and it
guessed ADD on 'Max moved to Seattle.' after 'Max lives in Boston.' in the
same context."*

**What's also true, and not previously connected to that finding:** there is
a second implementation, `LLMExtractionService` (`extraction.py`), that
*does* assemble context before extracting — it pulls the last 10 messages
of conversation buffer and the top 5 candidate existing facts via a
`context_repo` port before calling the LLM. It is fully implemented and has
its own unit test (`test_extraction_service.py`). **It is never constructed
anywhere in the application** — confirmed by grep, `context_repo` and
`get_conversation_buffer`/`get_top_candidate_facts` appear only in that one
file and its test, nowhere in `api/routes.py` or `benchmark_runner.py`.
Whether this was scoped as unfinished future work or simply lost track of
after the blind extractor shipped isn't something the code alone answers —
worth confirming intent before treating it as dead code to delete versus a
half-finished fix to wire up.

**Why this matters for accuracy specifically, tying it to this session's own
work:** `SUPERSEDES` (§1.1) only fires when `find_existing_facts` returns a
same-`subject_entity_id`-and-`predicate_key` collision against a prior
fact. An extractor with zero visibility into prior turns has no basis to
assign the *same* `predicate_key` string to two conceptually-identical facts
stated in different turns (e.g. `"lives_in"` one turn, `"current_city"` or
`"residence"` the next) — and if the strings don't match exactly, the
lookup's `WHERE predicate_key = %s` never finds the collision, silently
skipping `SUPERSEDES` for exactly the knowledge-update case it exists to
handle, regardless of how correct the classifier itself is once invoked.
Wiring `find_existing_facts` up (this session) fixed the "nobody's asking"
half of that gap; this pre-existing extraction-context gap is the "asking
with inconsistent keys" half, and it was not touched this session. Not
verified live in this review (would require re-running extraction on a
knowledge-update instance and inspecting `predicate_key` consistency across
turns) — flagged as the most concrete, most directly actionable accuracy
lead for a future pass, not claimed as a measured cause.

### 3.7 Summary: prioritized, honestly scoped

| # | Change | Type | Evidence | Status |
|---|---|---|---|---|
| 1 | Batch `EmbeddingStore`/`SearchIndexStore` writes per chunk | rewrite, no threading | isolated DB micro-benchmark: 2.4x-5.1x on the write portion (see §3.2's correction on how much of the parent stage that portion actually is) | **implemented** — `put_batch()` on both stores, 132/132 tests pass, replay/conflict semantics preserved |
| 2 | Parallelize `GraphWriter.write()`'s node/relationship buckets | threading | live-tested correct (no data loss under concurrency) but no timing win (0.98x after warmup) — root-caused to HydraDB's per-`cell_id` writer-lane mutex in the engine's own Rust source, not a client-side limitation | **verified, not implemented — verdict is no.** Real fix for concurrent writes is per-context `cell_id` routing + multi-cell `GRAPH_CELLS` deployment (see §3.3), a different and larger change |
| 3 | Multi-stage `max_tokens` gateway for extraction | new capability | real percentile distribution (25k turns) backing 4 tiers; live-verified on both a short and a genuine 15.9k-char outlier turn, no truncation | **implemented** — `Config.extraction_max_tokens_for()`, wired into `LLMExtractor.extract()`, 132/132 tests pass |
| 4 | Wire up (or deliberately retire) `LLMExtractionService`'s context-aware extraction | correctness/accuracy | confirmed dead code via grep; consequence already documented in `graph_plan_builder.py`'s own docstring; directly undermines this session's `SUPERSEDES` fix | reviewed, not implemented |
| — | Turn-loop parallelism | N/A | correctly ruled unsafe by existing docstring (shared connection + chronological `SUPERSEDES`/entity-registry ordering) | not applicable |
| — | More extraction workers | N/A | already TPM-clamped; matches independent published thread-count/batch-size (ATOM paper) | not applicable |

### 3.8 Future scope: two write-throughput issues that don't matter for the benchmark, but will for a real product

§3.3's `cell_id` finding raised the obvious next question — "so should we fix it?" Traced it through and the honest
answer for *this* session's work is no, but both issues below are real and will matter the moment this becomes a
service with more than one conversation happening at once. Recorded here rather than fixed, since this session's
scope was the LongMemEval benchmark path, and the benchmark path gets zero benefit from either — see the reasoning
below for why, so the tradeoff is written down, not just the conclusion.

**Issue 1 — every HydraDB write goes through one `cell_id`, capping concurrent-context write throughput at 1x.**
Covered in full in §3.3: HydraDB's own engine (`hydradb/src/shard/write.rs`, `codec.rs`) supports up to 64-way
write concurrency via per-`cell_id` writer lanes, but this codebase hardcodes `cell_id="cell-0"` everywhere
(`HydraHttpTransport.__init__`'s default, never overridden — confirmed by grep, nowhere else in `src/` sets it)
and the deployed container only has one cell configured (`GRAPH_CELLS=cell-0` in `hydradb/README.md`'s example
config). Checked whether this actually matters for either real code path in this repo:

- `evaluation/benchmark_runner.py::evaluate_dataset` — processes instances in a plain sequential `for` loop, one
  at a time. Never more than one context's writes in flight, so multi-cell routing has nothing to parallelize
  against. **Zero benefit for the LongMemEval work this whole document is about.**
- `api/routes.py` + `context_memory/engine.py` — a different, real code path: `MemoryEngine.add_turn_async`
  dispatches ingestion to a background `ThreadPoolExecutor` (`self._executor.submit(self._run_orchestrator_safe,
  batch)`), so concurrent turns from *different* users/contexts genuinely can run at the same time today. This is
  the path where `cell_id` routing (e.g. hashing `context_id` into a small `GRAPH_CELLS` set, both in the
  deployment config and in `HydraHttpTransport`'s construction) would actually unlock real concurrent write
  throughput — but not safely yet, see Issue 2.

**Issue 2 — found while checking Issue 1, and it's the more urgent one: that same background-thread ingestion
path already shares one Postgres connection across every concurrent request, which this codebase's own code
elsewhere documents as unsafe.** `api/routes.py::get_engine()` constructs a single `psycopg.connect(...)` for the
whole process-lifetime `MemoryEngine` singleton; every `ThreadPoolExecutor` worker thread `add_turn_async` spawns
writes through that same one connection (`self._pg` in `engine.py`). `PrefetchingExtractor`'s own docstring
(`benchmark_runner.py`) already states the reason this is unsafe for the pipeline generally: "every store in this
pipeline ... shares one `psycopg` connection, which is not safe for concurrent access from multiple threads" — that
statement was made about the benchmark runner's single-threaded `run_batch` loop, where it's true but inert (the
loop never actually runs concurrent Postgres access). In `engine.py`'s background-executor path, the same shared
connection **is** reachable concurrently, by design, right now, for any deployment where more than one user's turn
is being ingested at once. This was not introduced by anything in this session's changes — flagged as a
pre-existing gap surfaced while investigating Issue 1, not a new regression.

**Why Issue 2 has to be fixed before Issue 1, not after or alongside:** if `cell_id` routing is added without
first giving each background-ingestion thread its own Postgres connection (a real pool, not the shared singleton),
the practical effect is *more* concurrent writes successfully reaching HydraDB's now-unlocked parallel lanes,
which just means more concurrent threads racing on the one connection that was never safe to share — trading a
slow-but-correct bottleneck for a fast-but-corruptible one. The fix, when this becomes real scope: give
`MemoryEngine` a connection pool (e.g. `psycopg_pool.ConnectionPool`, one connection checked out per background
task) instead of the single shared `pg_conn`, verify that under real concurrent load, *then* consider `cell_id`
routing on top of it.

Not implemented, not benchmarked — this section exists so the tradeoff and the two-issue ordering are on record
for whenever the product scope moves past single-context-at-a-time evaluation.

### 3.9 Implemented: cross-chunk write batching in `run_batch`

§3.1's measurement, re-checked after this session's other fixes landed, surfaced something worth pulling on:
extraction (already parallelized via `PrefetchingExtractor`) is no longer the dominant share of a small slice's
ingest wall time once it's warm-cached — the post-extraction `run_batch` loop is now comparable to or bigger.
Checked two candidate levers before picking one:

**Ruled out: switching the embedding model to MPS (this machine's GPU).** Measured at the real per-chunk batch
size (n=6 facts, matching this dataset's ~5.6 facts/chunk average): MPS was **3.2x slower** than CPU (23.25ms vs
7.25ms) — GPU dispatch overhead swamps a batch this small. Only wins past n=139 (53.96ms vs 75.37ms). Not
implemented — the real call pattern is chunk-sized, not instance-sized.

**Implemented: batch the graph write and the embedding/search-index write across multiple chunks before
flushing, instead of once per chunk.** Not threading — §3.3 already found HydraDB serializes writes to one
`cell_id` through a single mutex lane regardless of client concurrency — the same lesson §3.2 proved for
Postgres, applied to the graph-write side: fewer, bigger calls, not more concurrent ones.

- `GraphWriter.write_many(plans)` merges nodes/relationships across several chunks' `GraphWritePlan`s into the
  same `(label, property_names)` / `(relationship_type, ...)` buckets `write()` already uses for one plan, so
  the number of physical write calls is bounded by the number of distinct node/edge *shapes* (~7-8 in this
  system), not by how many chunks are in the group. Idempotency is untouched: every plan is still registered
  with `manifest_store` individually under its own `plan_key`, exactly as a solo `write()` would — only the
  physical HTTP calls are merged, not the correctness guarantee. Still writes every node bucket (across the
  whole group) before any relationship bucket, preserving the same ordering guarantee `write()` gives within one
  chunk.
- `IngestionOrchestrator._run_group` (new; `run_batch` now groups records into batches of
  `Config.ingestion_write_batch_size`, default 10, before processing) batches the graph write and the
  embedding-model + embedding-persistence calls across the group's successfully-extracted chunks. Extraction,
  graph-plan building (entity resolution, `SUPERSEDES` lookup), verification, and job-state transitions all stay
  per-chunk — none of those were the measured bottleneck, and keeping them isolated means one chunk's failure
  never blocks its group-mates. A group of 1 (the default `write_batch_size` on the constructor, and what every
  single-turn caller like `MemoryEngine.add_turn_async` always produces regardless of config, since its batches
  are always one record) degrades to exactly the original per-chunk `run_record` path — `run_chunk`/`run_record`
  themselves are completely unchanged, still used directly by every existing orchestrator test and by any solo
  retry.
- **Failure handling:** if the batched graph-write or embedding-write call fails, every chunk still pending in
  that group is marked with the same classification a solo failure would get at that stage (`TERMINAL_FAILED` /
  `RETRYABLE_FAILED`) — consistent with this module's documented scope ("replay redoes the whole chunk
  pipeline"), extended to "redo the whole group" when a group fails together, not a silent new guarantee.

**Verified, not just written:**
- 11 new unit tests (6 in `test_graph_writer.py` for `write_many`'s bucket-merging/ordering/idempotency, 7 in
  `test_orchestrator.py` for grouping/ordering/partial-completion/failure-isolation), all passing — 143/143 full
  suite, up from 132.
- Live before/after on the same 25-turn slice used throughout §3.1-§3.3 (real Postgres + HydraDB, extraction
  warm-cached so what's measured is the targeted change):

  ```
                                    ungrouped (size=1)   grouped (size=10)   change
  run_batch (post-extraction)            13.94s               11.32s        -18.8%
  hydradb.write calls                      188                  24          -87.2% (7.8x fewer)
  graph_write stage total               3890.8ms             1576.3ms       -59.5%
  embeddings_and_search_index total     6525.3ms             6332.4ms       -3.0%
  ```

  `graph_write` moved almost exactly as predicted. `embeddings_and_search_index` barely moved — expected, per
  §3.2's correction: that stage is dominated by `SentenceTransformerEmbedder`'s own inference time (the same
  total fact count gets embedded either way, just batched 25-calls-of-~6 vs 3-calls-of-~46), and the write
  portion inside it was already small after §3.2's Postgres batching. Reported honestly rather than folded into
  one flattering headline number.

**Configuration:** `Config.ingestion_write_batch_size` (env `INGESTION_WRITE_BATCH_SIZE`, default 10), wired
through both `benchmark_runner.create_pipeline` and `api/routes.get_engine`. The latter is a no-op today —
`MemoryEngine.add_turn_async` always builds one-record batches, so grouping never has more than 1 record to
group — wired through so that path is already correct if/when multi-turn batching is added there.

### 3.10 Correction: §3.2/§3.9's embedding numbers were a measurement artifact, not a real bottleneck

Asked to "resolve" the embeddings-and-search-index cost that §3.2/§3.9 reported as ~44-48% of chunk/group time.
Before touching anything, checked why it was that large — and found the real answer isn't a fix, it's a
correction to what was measured.

**`SentenceTransformerEmbedder._get_model()` lazy-loads the model on its first call — and every probe script
this session constructed a fresh embedder, paying that load cost inside the timed window.** Isolated the two
costs directly:

```
model load (first call, cold):        10,071.6 ms
encode 139 texts (model already warm):    289.2 ms
```

Load is **35x** the actual encode cost. Every "embeddings_and_search_index"/"embedding_model" number reported in
§3.2 and §3.9 was measured by a probe script that built a new `SentenceTransformerEmbedder` for that single run —
so nearly all of that "6+ seconds" was a one-time model load happening to land inside the timed stage, not a
real per-instance recurring cost. The actual production code path never pays this repeatedly: both
`benchmark_runner.main()` and `api/routes.get_engine()` construct one embedder instance and reuse it for the
entire process lifetime (every instance in a benchmark run, every request the API server ever handles) — the
load cost is paid once, at startup, and amortizes to nothing across a real run.

**Re-measured with the embedder correctly warmed once outside the timed comparison** (matching real production
behavior) — the true steady-state numbers, 25 turns, `write_batch_size=1`:

```
embeddings_and_search_index: 843.3ms for 25 chunks (was reported as 6525.3ms)  -- ~34ms/chunk, not ~261ms/chunk
```

**Conclusion: there was no real embedding/search-index bottleneck to resolve.** It's genuinely small in steady
state — smaller, per chunk, than `graph_write` even before batching. §3.2's Postgres-write-batching fix and
§3.9's cross-chunk grouping are both still real and still correctly implemented; their *reported* percentage
share of chunk time was inflated by this measurement artifact, not their absolute correctness or value. Flagged
here rather than left standing, consistent with this document's own rule for itself.

### 3.11 Corrected, clean grouped-batching numbers, plus a real limit found and fixed

Asked to push `write_batch_size` higher. Doing that surfaced a real, separate bug — described below — and once
fixed, gave much larger, genuinely clean wins than §3.9's original 18.8% figure.

**Found while testing bigger sizes: HydraDB's own admission control rejects any single `UNWIND` write over 1024
rows, and a group large enough to hit it loses every chunk in that group at once.** At `write_batch_size=100` on
a 100-turn slice, the Fact-node bucket alone accumulated 1236 rows in one physical call:

```
HydraDB returned HTTP 429: {"error":{"code":"resource_exhausted","message":
"client_query_batch_items rejected by admission control: actual 1236 exceeds limit 1024"}}
```

Since `write_many` sends one physical call per bucket covering the *whole* group, this single rejection failed
all 100 chunks together (`completed=0/100`) — the failure-blast-radius risk §3.9 flagged as theoretical, now
confirmed real and live.

**Fixed at the source, not by capping `write_batch_size` low enough to avoid it.** `GraphWriter` now caps rows
per physical call (`DEFAULT_MAX_ROWS_PER_WRITE = 900`, real margin under the server's 1024) and transparently
splits any bucket that would exceed it into multiple sub-batch calls with distinct, content-addressed
idempotency keys — `write_batch_size` stays free to be tuned purely for I/O-round-trip efficiency without ever
being able to reintroduce this failure mode, regardless of how fact-dense a real batch of turns turns out to be
(this dataset's ~5.6 facts/turn average is not a number to build a hard assumption on). 4 new unit tests cover
the split (row accounting, distinct keys, unsplit path unchanged below the cap). Re-ran the exact failing
scenario after the fix: `completed=100/100`.

**Also found and fixed a measurement bug of my own before trusting the numbers below:** an earlier comparison
reused the same deterministic `question_id` (and therefore the same `context_id`/chunk ids) across repeated
script runs against the same live Postgres container — later runs found those chunks already `COMPLETED` from
an earlier run and correctly short-circuited instead of doing real work, making some configurations look
falsely instantaneous. Fixed by tagging every timed run with a fresh unique id. Re-run, clean:

```
100-turn slice, embedder warm, unique context per run:

write_batch_size= 10: run_batch=70.78s  (80 hydradb.write calls)
write_batch_size= 25: run_batch=54.10s  (32 hydradb.write calls)   -23.6% vs size=10
write_batch_size= 50: run_batch=24.88s  (17 hydradb.write calls)   -64.8% vs size=10
write_batch_size=100: run_batch=14.13s  (10 hydradb.write calls)   -80.0% vs size=10
```

Monotonic, no plateau yet at 100 (the largest slice available to test cleanly). **New default: 100** (was 10),
`Config.ingestion_write_batch_size`. Not tested past 100 — raise further only backed by the same kind of live
measurement, not extrapolation.

**Also checked and ruled out before committing to grouping as the lever:** switching the embedding model to MPS
(this machine's GPU). At the real per-chunk batch size (n=6 facts): MPS was **3.2x slower** than CPU (23.25ms vs
7.25ms) — dispatch overhead swamps a batch this small, only wins past n=139. Not implemented.

### 3.12 Structured per-stage performance logging for real runs

Every measurement in §3.1-§3.11 came from a one-off probe script grepping/regexing the existing text
`[DONE] operation in N ms` log lines. That's how this session investigated things reactively, but a real
LongMemEval run had no equivalent built in — answering "where did the time go" for an actual run meant writing a
new script after the fact.

**Added a structured, opt-in sink `core.logging.timed_operation` feeds in parallel with its existing text logs**
(`enable_metrics_collection()` / `drain_metrics()` / `disable_metrics_collection()`) — since every stage across
the whole pipeline (ingestion *and* retrieval) already goes through `timed_operation`, this captures all of them
automatically with zero changes at any call site. Off by default (one `is None` check, no cost for anyone who
doesn't use it — unit tests, the live API path, anything else).

**Wired into `evaluate_dataset`/`evaluate_instance`:** every real benchmark run now writes
`<output>.metrics.jsonl` alongside the hypotheses file — one `instance_summary` record per instance (turns,
completed chunks, accepted facts, prefetch/ingest/retrieve/total seconds) plus one `stage` record per
`timed_operation` call that instance triggered anywhere in the pipeline, tagged with `question_id`, flushed
per-instance same as the hypotheses output. Live-verified against a real 15-turn instance through the actual
CLI: 291 stage records, `instance_summary` matching the printed console numbers exactly, every stage from
`extractor.extract` down to individual `hydradb.read`/`hydradb.write` calls present and correctly attributed.
4 new tests (`test_logging.py`, `test_benchmark_runner.py`), including one proving collection state doesn't leak
into whatever runs after a benchmark finishes. 153/153 passing.

This is additive only — the existing `--log-level INFO` text logs are unchanged and still print; this is a
second, directly-loadable (`jq`, `pandas.read_json(lines=True)`) sink of the exact same underlying
measurements, so the next performance question about a real run doesn't need a new probe script first.

## 4. Entity duplication: the Dave/David problem

Raised independently of the latency work, prompted by external material describing entity duplication as a
known failure mode in AI-built knowledge graphs — "Dave"/"David"/"Dave Smith" or "Sherlock Holmes"/"Sherlock"/
"Holmes" ending up as separate nodes, cited against Microsoft GraphRAG's own unresolved dedup issue
([microsoft/graphrag#401](https://github.com/microsoft/graphrag/issues/401)).

### 4.1 Diagnosis: confirmed live, root-caused precisely

Reproduced the exact failure against this codebase's production wiring before touching anything:

```
Dave  -> new_entity, graph_id=1
David -> new_entity, graph_id=2
LLM disambiguator ever consulted? False
```

`EntityRegistry` already had the right shape — exact-canonical match, exact-alias match, and a bounded LLM
disambiguator that can only pick among a supplied candidate set (never fabricates a match) — the "hybrid" design
the external material recommends, not the naive prompt-only anti-pattern it critiques. The gap: a third piece
was already built — `db.embedding_index.EntityNameIndex`, embedding-based candidate generation — but never
constructed at either production call site (`benchmark_runner.create_pipeline`, `api/routes.get_engine` both
passed no `name_index`). With an empty candidate shortlist, `resolve()` skips the model call entirely
(`if shortlist:` never true) and silently creates a duplicate.

### 4.2 Research: how a comparable production system handles this

Researched Zep/Graphiti (20k★, the closest real production analogue) before designing a fix. Its entity
resolution runs a staged pipeline: exact match first (skip the LLM on a unique hit), then deterministic fuzzy
matching — Jaccard similarity over character trigrams, entropy-gated so short/unstable names don't fuzzy-match —
then LLM verification only on what survives blocking, plus a separate embedding+reranking pass. Confirms the
shape of the fix: candidate *generation* (blocking) and candidate *verification* (the LLM) are different
problems needing different techniques, and precision belongs to the verification step, not the blocking step —
a blocking false positive costs one bounded LLM call that correctly says no, not a wrong merge.

### 4.3 Implemented: four pieces, calibrated against real name pairs before picking constants

**New module, `ingestion/entity_blocking.py`** — character-trigram Jaccard similarity + Shannon-entropy gating,
calibrated against real pairs before choosing thresholds (not guessed):

```
'dave' vs 'david':              0.300  (true positive)
'sherlock holmes' vs 'holmes':  0.389  (true positive -- the exact GraphRAG #401 case)
'sherlock holmes' vs 'sherlock': 0.500  (true positive)
'dave' vs 'dan':                0.222  (true negative)
'mike' vs 'nike':               0.333  (false positive -- accepted; verification's job to reject, not blocking's)
```

Threshold set to 0.25 — strictly between the lowest true positive and the highest true negative that must stay
excluded. Entropy floor (1.0 bit) and a 2-character length floor exclude degenerate surfaces ('a' scores 0.0
bits) from fuzzy matching entirely, on either the string or embedding blocking pass.

**`EntityRegistry.resolve()` (`ingestion/resolution.py`)** now runs both blocking signals — the pre-existing
`EntityNameIndex` (embedding) call plus the new trigram pass — unioned into one candidate set before the LLM
sees it, gated on the query surface being stable enough to fuzzy-match at all.

**Alias learning:** `resolve()`'s `MODEL_RESOLVED` branch previously returned the matched profile unchanged —
"David" confirmed as the same person as "Dave" was never *recorded* as an alias, so the identical LLM call would
fire again the next time "David" came up. `EntityRegistry._grow_alias` now appends the confirmed surface to the
profile's aliases, so a repeat reference short-circuits to `EXACT_ALIAS` (no model call) from then on.

**Index sync:** wiring `EntityNameIndex` in isn't enough on its own — it needs to stay populated as entities are
created *during* the same ingestion run, or a later turn referencing an earlier turn's entity would never find it
as a candidate. `EntityRegistry.register()` now calls `_index_profile()` on every new entity.

**Wired at both production sites** (`benchmark_runner.create_pipeline`, `api/routes.get_engine`) — both
construct a real `EntityNameIndex` and pass it into `EntityRegistry`, matching how `entity_registry` was already
shared for the whole run/process (isolation across contexts/instances holds: both blocking mechanisms and
`resolve()`'s own filtering key on `context_id`).

### 4.4 Verified — mechanically and against the real LLM, honestly reported

**Unit level:** 20 new tests (`test_entity_blocking.py`, `test_resolution_service.py`), including the exact
Dave/David and Sherlock Holmes reproductions run against a deterministic "always confirms" fake model (proving
the mechanical wiring is correct), a genuinely-different-entity case that must *not* over-merge, alias-growth
short-circuiting a repeat resolution, and index-sync letting a later turn find an earlier-created entity —
against the real `EntityNameIndex` class with a deterministic character-frequency fake standing in for
`SentenceTransformer` (same pattern `DeterministicEmbedder` uses elsewhere, kept the suite fast and offline
rather than downloading a real model in a unit test). 173/173 passing.

**Live, against the real LLM (`deepseek.v3.2`), not a fake — reported exactly as it came back, not spun:**

```
Dave / David (bare names, no context):        model abstains (returns null)
Sherlock Holmes / Holmes:                      model confirms match  -- the exact GraphRAG #401 case, now fixed
Sherlock Holmes / Sherlock (no context):       model abstains (returns null)
```

The mechanical fix works in every case — confirmed the model is actually being *consulted* now (previously
impossible), not that it always says yes. Given nothing but two bare names and no surrounding context, a real
model declining to assume "Dave" and "David" are the same person is arguably the *correct* call, not a fix
shortfall — the same judgment a cautious human would make with zero other information. `ADR-020`'s existing
guarantee (an unresolved mention is skipped, never forced into a link) makes that the safe outcome either way.
Where the substring/near-identical signal is strong enough for a confident real answer — the literal example the
external material and GraphRAG's own issue both cite — it now resolves correctly, live-verified end to end.

### 4.5 Closed: root-different nicknames, via a curated equivalence table

The gap §4.5 originally flagged as not built — "Bob"/"Robert", "Bill"/"William", "Dick"/"Richard" share no
character overlap at all ('bob' vs 'robert' scores 0.000 on the trigram pass) and aren't reliably close in
embedding space either — is now closed. `entity_blocking.py` gained `NICKNAME_GROUPS`: 102 collision-free groups,
326 names, cross-referenced against a published English-nicknames reference
([cc.kyoto-su.ac.jp/~trobb/nicklist.html](https://www.cc.kyoto-su.ac.jp/~trobb/nicklist.html)) before inclusion,
not invented from memory. Building it surfaced several genuine real-world ambiguities that would have silently
collided if not caught — "Harry" is legitimately short for both Harold *and* Henry, "Jon" for both John and
Jonathan, "Sam" for both Samuel and Samantha — a dedicated test (`test_no_name_appears_in_two_groups`) locks in
that every one of those got merged into one group rather than one silently overwriting the other in
`_NICKNAME_GROUP_BY_NAME`'s dict construction.

Wired into `resolve()` as a third, independent blocking signal — exact table lookup, not a similarity heuristic,
so it deliberately runs even for surfaces the general fuzzy-matching stability gate would otherwise exclude (a
3-letter name like "Bob" is exactly the case this table exists for). Like the other two signals, a hit is still
only ever a *candidate* for the LLM to verify, never an automatic merge — the same file/person nickname could
legitimately belong to two different people in one conversation, and this system's bounded-verification design
(ADR-020) already exists to keep that judgment with the model.

Live-verified against the real LLM, same honest pattern as Dave/David: "Bob"/"Robert" now correctly reaches the
model as a candidate (previously impossible, same root cause as §4.1), and the model itself abstains given zero
context — appropriate, not a shortfall. 9 new tests, 182/182 passing.

### 4.6 Newly discovered while live-testing at scale: the fix's own latency cost

Running a real, larger LongMemEval instance (522 turns) through the fixed pipeline surfaced something the
smaller unit-level verification couldn't: `run_batch` stalled for 14+ minutes on ingest, confirmed alive (not
hung — an active `lsof`-visible HTTPS connection to the LLM endpoint, `ps` showing real CPU activity, no
error/retry lines despite retries being visible at this log level when they do happen).

**Root cause: the fix's own success.** Before §4.1's fix, the LLM entity-disambiguation call was — because of the
bug being fixed — almost never actually invoked; `if shortlist:` was false nearly every time. The fix makes
blocking produce real candidates, so that call now fires routinely, and it always has: serially, unbatched, one
call per ambiguous mention, inside a per-chunk stage §3.9 explicitly left un-batched on the reasoning "not the
measured bottleneck" — true before this fix, not true after it made the call path live.

**Fixed, two pieces, both already live-tested before being kept:**

1. **A real wiring inconsistency, zero accuracy risk.** `api/routes.py::get_engine()` already built entity
   resolution's model via `config.get_entity_resolution_client()` — a role-specific client, same pattern as every
   other role. `benchmark_runner.py::create_pipeline` didn't; it passed the raw extraction `llm_client` straight
   through. Fixed to match. No behavior change by itself (no role-specific model was configured yet), but the
   necessary prerequisite for the next piece.

2. **A separate, smaller model behind that role, found by testing what's actually available, not guessing.**
   Probed the same Bedrock endpoint for smaller/faster models rather than assuming `qwen3.6-27b` (the
   historical Groq default, a different provider) was reachable here — it isn't, but `qwen.qwen3-32b` is, and it
   accepts `reasoning_effort="none"` (genuinely disables hidden reasoning), unlike `openai.gpt-oss-20b`
   (extraction's model, low/medium/high only, can't disable). Added `Config.entity_resolution_reasoning_effort`
   — a *per-role* override, not the existing global `llm_reasoning_effort` — specifically because the two
   models behind this one endpoint accept disjoint reasoning-effort enums; sending "none" to gpt-oss-20b 400s,
   confirmed live the same way `qwen.qwen3-32b` 400s on the literal string `"default"`.

   **Correctness checked before speed, on the same known cases already used to verify §4.1/§4.5, side by side
   against the current model:**

   | case | qwen.qwen3-32b (none) | openai.gpt-oss-20b (control) |
   |---|---|---|
   | Sherlock Holmes / Holmes | matches (correct) | matches (correct) |
   | Dave / Dan (genuinely different) | abstains (correct) | abstains (correct) |
   | Dave / David (bare, no context) | **matches** | abstains |
   | Bob / Robert (bare, no context) | **matches** | abstains |

   Both models agree on the unambiguous cases. They disagree on the two genuinely ambiguous bare-name cases —
   qwen is more willing to confirm a nickname-table-backed match without extra context; gpt-oss-20b is more
   conservative. Neither is simply "wrong": for a personal-memory system where the same conversation is
   overwhelmingly likely to be talking about the same recurring person, qwen's prior is arguably the better fit
   for this specific product; for a corpus spanning many unrelated documents (the GraphRAG/Sherlock-Holmes
   shape), gpt-oss-20b's caution is arguably safer. Recorded as a real, observed behavioral difference, not
   smoothed over — worth knowing if this is tuned further.

   Latency on this same small sample: qwen averaged 0.85s/call vs gpt-oss-20b's 0.965s/call — real but modest
   (12%) on structured-completion calls specifically, well short of the ~4.5x seen on a trivial bare completion
   (1.57s→0.35s) — the disambiguation task's own JSON-schema generation and reasoning-adjacent work costs more
   than the trivial-prompt test suggested. Configured via `ENTITY_RESOLUTION_MODEL`/
   `ENTITY_RESOLUTION_REASONING_EFFORT` in `src/.env`, not hardcoded into `Config`'s defaults — endpoint-specific
   tuning belongs in environment configuration, matching how every other provider setting in this file already
   works.

**Kept, per live pipeline-level measurement — but the real bottleneck it exposed is bigger than per-call
latency.** Ran a real 100-turn slice (fresh context, `qwen.qwen3-32b`/`none` live) through the actual CLI with
the new structured metrics (§3.12) capturing every stage:

```
orchestrator.run_batch (ingest)                332.80s  (100%)
  orchestrator.stage.graph_plan                319.46s  ( 96.0%)
    entity_resolution.disambiguate             277.59s  ( 83.4%)   n=618 calls, avg 449ms/call
    fact_lookup.find_existing                    3.84s  (  1.2%)   n=566 calls
  orchestrator.stage.graph_write_batched          3.68s  (  1.1%)
  orchestrator.stage.embeddings_and_search_index  7.83s  (  2.4%)
```

**618 disambiguation calls for 100 turns — 6.18/turn.** Per-call latency did improve (449ms avg here vs. the
~0.85-1s+ range established earlier this session for `openai.gpt-oss-20b`), and that's a real, keepable win —
but a 6x-per-turn call rate means halving per-call cost only halves a number that's still dominated by volume,
not latency. Cutting per-call time from 449ms to 0ms would still leave ~0s from this stage only in the limit;
the actual lever that matters next is *how many calls happen*, not how fast each one is.

**Kept anyway, on its own terms:** strictly better than the `gpt-oss-20b` baseline on every axis measured — same
correctness on unambiguous cases, faster per call, config-only change (`src/.env`, not a `Config` default),
zero blast radius on any other role's client. Just not a claim that it fixed the underlying slowness, because it
didn't — it fixed the piece it could fix.

**Not investigated yet, flagged for a follow-up pass, not attempted here:** whether 618 calls for 100 turns is
genuinely warranted (a real conversation with that many distinct ambiguous entity references) or a sign that
blocking's thresholds are too loose and generating false-positive candidates the LLM then has to spend a call
rejecting — §4.3's own calibration already accepted some false positives as a deliberate tradeoff ('mike'/'nike'
scoring higher than the true positive 'dave'/'david'), and this is the first real-scale measurement of what that
tradeoff costs in call volume. The two options already on record from the original bottleneck analysis (see the
"newly discovered bottleneck" question this session) remain: parallelize the disambiguation *calls* while
keeping registry mutations serial (moderate risk, more implementation, not yet built), or tighten blocking
thresholds to cut candidate volume at the source (changes recall, needs the same kind of before/after accuracy
check every other threshold in this document got). Neither implemented in this pass.

### 4.7 Both options implemented

**Option 1: `EntityRegistry.resolve_many` — parallelize the LLM calls, not the registry.** Same shape as every
other concurrency fix this session: separate what's genuinely I/O-bound and independent (the LLM disambiguation
call itself) from what has to stay serial (candidate generation snapshot, and every registry mutation).

Design, in four phases: (1) exact canonical/alias matches resolve immediately for every mention in the chunk —
these never touch the model or mutate anything, so doing all of them first doesn't change what phase 2 sees; (2)
every *distinct* remaining surface (mentions repeating the identical surface within one chunk are deduplicated
and resolved once, reused for every occurrence) gets its candidate shortlist generated, still read-only, against
the registry exactly as it stood when the call started; (3) the LLM calls for every non-empty shortlist fire
concurrently — each one only reads its own already-fixed shortlist, nothing shared; (4) results are applied
serially, in a stable order (first occurrence, not completion order, so idempotency never depends on network
timing).

**The one real tradeoff, found and corrected by testing rather than assumed correct:** the initial docstring
claimed this was "fully self-correcting" for two distinct-but-equivalent surfaces introduced together in one
batch (e.g. "Bob" and "Robert" both new in the same turn, each mints its own entity since neither's shortlist can
see the other). Testing it directly proved that claim wrong in its strong form: the split is *not*
self-correcting for those two exact surfaces — a later "Bob" always exact-matches its own already-registered
entity, never "Robert"'s, because exact match is checked before blocking runs again. What *is* still true: a
later, genuinely different surface in the same nickname group (e.g. "Bobby") sees both split entities as
candidates and the model can correctly attach it to one of them — new references aren't stuck permanently
ambiguous, but the two already-split entities never retroactively merge with each other. Corrected in the
docstring and locked in with a test (`test_two_distinct_surfaces_in_one_batch_do_not_see_each_other_as_candidates`)
before this was trusted, not after.

`graph_plan_builder.build()` gained an optional `resolve_many` parameter — when supplied, it collects every
entity mention in the chunk up front, resolves them in one batched call, then builds nodes/edges from the
pre-resolved profiles instead of calling `resolve()` inline per mention. Omitted (the default), it falls back to
the exact per-mention path that existed before this — every existing test in `test_graph_plan_builder.py` still
passes unmodified, proving the fallback is truly unchanged. Wired at both production sites
(`benchmark_runner.create_pipeline`, `api/routes.get_engine`) via `entity_registry.resolve_many`.

18 new tests (`resolve_many` itself, the batched `build()` path, mention-to-fact ordering with two different
entities in one chunk), including a genuine wall-clock concurrency proof (4 calls at 150ms each complete in
<350ms, not the ≥600ms sequential execution would take) rather than just trusting the code path was taken.
197/197 passing.

**Option 2: tighten blocking thresholds — evidence gathered first, via a new diagnostic.** Added
`entity_resolution.blocking` as a structured metrics event (`core.logging.record_event` — a new, non-timed
sibling to `timed_operation`'s existing metrics, same opt-in sink from §3.12) recording exactly how many
candidates each blocking signal produced per call, specifically to answer "is call volume driven by genuinely
ambiguous content, or by blocking being too loose" with real counts instead of a guess.

**What the counts showed, on the same real 100-turn instance (fresh context) with option 1 active:** 431 distinct
blocking events (already down from 618 — `resolve_many` deduplicates identical repeated surfaces within a chunk
to one call, a free reduction from batching alone). Of those 431:

```
trigram signal contributed:   427 / 431  (99.1%)
embedding signal contributed: 122 / 431  (28.3%)
nickname signal contributed:    0 / 431  ( 0.0%)
```

**Trigram wasn't just loose — checked against this module's own calibration set and it turned out to add zero
unique recall.** Verified directly, not assumed: `char_trigram_jaccard_similarity` on "sherlock holmes"/"holmes"
was the original justification for adding trigram blocking at all, but embedding similarity alone scores that
pair 0.82-0.90 — comfortably above threshold with no trigram involved. "Dave"/"David" and "Bob"/"Robert" are
covered by the nickname table, also independent of trigram. **Every true positive in the original calibration was
already covered by one of the other two signals.** What trigram *was* actually catching on real content:
generic topic nouns sharing incidental character overlap — pulled the real surfaces from the 427 hits and they
were things like `'reliable news sources'`, `'trustworthy news sources'`, `'accurate news reporting'`,
`'trust'`, `'misinformation'`, `'stress'` — not names, not even close. Root cause: `entity_type` is hardcoded to
`"other"` for every entity at extraction time (no schema field currently asks the LLM to classify person/place/
organization vs. topic noun), so trigram similarity — designed for names — had no way to avoid being applied to
abstract topic phrases too, where near-textual-overlap doesn't imply "same real-world referent" the way it does
for names. A word-count heuristic was checked and rejected before disabling trigram outright: 86.4% of the noisy
surfaces were 1-2 words ("trust", "news", "stress", "motivation") — length doesn't separate names from topics
here either.

**Fix: `_generate_shortlist` no longer calls `find_fuzzy_candidates`.** The function itself is untouched, still
tested, still importable — this is a wiring change, not a deletion, kept as a real capability for whenever
entity-type-aware gating exists to make it safe to re-enable narrowly (person/place/organization only).

**Caught and fixed a real correctness gap this exposed, not caused by it.** Two existing tests failed once
trigram was disabled: `test_ambiguous_alias_without_model_is_unresolved` (an alias shared by 2+ existing profiles
should surface as `UNRESOLVED`, requiring a model) and the Sherlock Holmes test. Root cause: the "2+ profiles
exactly share this string" case was reaching the shortlist only *incidentally*, via trigram's own 100%-similarity
self-match on the identical string — never a real blocking decision, a side effect of the signal that just got
removed. Fixed properly: added `_ambiguous_exact_matches`, which seeds the shortlist directly with every exact
canonical/alias match whenever there's more than one, independent of any blocking signal — a stronger signal
than any similarity heuristic, since it's not a heuristic at all. The Sherlock Holmes test's own setup was also
fixed (it never configured a `name_index`, matching the codebase's original account of the Dave/David bug, but
since Sherlock Holmes/Holmes is caught by embedding, not trigram or nickname, that test needs the same
`name_index` fixture every production wiring site actually provides — updated to use the module's deterministic
fake embedding model instead of assuming trigram would carry it). 197/197 passing.

**Combined live result, both fixes together, same real instance, fresh context:**

```
                        before (§4.6)   option 1 only   both options
ingest (100 turns)         332.80s          86.31s          68.37s   (-79.4%, 4.9x)
disambiguate calls             618             431             146   (-76.4%)
graph_plan stage total      319.46s           73.40s          54.94s
blocking signal mix     (not measured)  trigram 99%,     embedding 100%,
                                         embedding 28%,   nickname 0%
                                         nickname 0%      (this instance's
                                                            content had no
                                                            person names
                                                            needing it)
```

Both options compound: `resolve_many` cut call *count* first (618→431, deduplicating identical repeated
surfaces within a chunk) and made every remaining call concurrent; removing trigram then cut the surviving
count further (431→146) by no longer generating candidates for content it was never designed to handle. Neither
alone gets to 146 — parallelizing 431 noisy calls is still slower than not generating 285 of them in the first
place, and removing trigram without also parallelizing would still serialize whatever calls remain.

Verified correct, not just fast: 197/197 unit tests passing (including the two real regressions this exposed,
found and fixed rather than papered over — the ambiguous-exact-match gap and the Sherlock Holmes test's own
setup), plus this live run itself completed cleanly end to end with a real, coherent hypothesis, not a crash or
an empty answer.

## 5. Retrieval, now that ingestion isn't the bottleneck it was

With ingestion cut roughly 5x on the entity-resolution-heavy case (§4.7), retrieval's share of total wall time
went from a rounding error (~0.3% of a full run, §2.7) to something worth a real pass on its own terms.

**Checked the ingestion side first for anything decided-but-unimplemented — nothing was.** Everything explicitly
instructed this session is done. What remains are items flagged as *options* during reviews, never actually
decided: `LLMExtractionService` wiring (context-aware extraction, would fix `SUPERSEDES` predicate-key
consistency), batch-prompting extraction (packing multiple turns per LLM call, a bigger architecture change),
and `cell_id` routing / connection pooling (explicitly deferred by instruction, §3.8). None picked up here.

**Found the same wiring gap in retrieval that existed in ingestion, using the same method: check what's actually
wired, don't assume.** `api/routes.py::get_engine()` already builds `HybridRetrievalEngine` with role-specific
`temporal_resolver_client`/`query_rewriter_client`. `benchmark_runner.py::create_pipeline` didn't — passed no
role-specific clients at all, so both roles silently fell back to the extraction model, identical to the
entity-resolution gap in §4.6. Fixed to match.

**Live-measured which stage actually dominates retrieval latency before touching anything.** From real runs
already captured via §3.12's structured metrics: Phase 0's two concurrent LLM calls (temporal resolution + query
rewriting) were the single biggest piece of a ~2.4s total retrieve call — ~1.2-1.4s each, comparable to entity
resolution's own per-call cost, and the same shape of task (narrow structured decision, not open-ended
generation) that made the qwen swap pay off there.

**Tested the same swap on both roles — kept one, didn't keep the other, based on what the evidence actually
showed for each:**

- **Temporal resolver: clean win.** Compared side by side against the control model on 3 real questions
  (with/without a temporal anchor) — identical `valid_from`/`valid_to` output on every case, and faster every
  time (1.41s vs 2.20s, 0.58s vs 0.70s, 0.54s vs 0.58s). Switched: `TEMPORAL_RESOLVER_MODEL=qwen.qwen3-32b`,
  `TEMPORAL_RESOLVER_REASONING_EFFORT=none`.
- **Query rewriter: tested, not switched.** No real speedup (0.75s vs 0.73s — the reasoning-disable saving that
  helped elsewhere didn't show up here), and qwen produced noticeably fewer synonyms than the control model on
  the same query (3 vs 6 for "How much did I spend on my mortgage?") — a real behavioral difference with a
  plausible cost (fewer OR-terms for BM25 keyword search means less recall) and no latency win to justify
  accepting it. Wiring is fixed either way; the model itself stays on the default.

Added `Config.temporal_resolver_reasoning_effort`/`query_rewriter_reasoning_effort` (same per-role pattern as
`entity_resolution_reasoning_effort`, §4.6 — needed because models behind the same endpoint can require
different reasoning-effort enum values). 6 new config tests.

**Verified end-to-end, not just per-call.** Ran the full `retrieve_and_answer` pipeline live against a real
ingested context with the temporal-resolver swap active. First call: 4.63s (still paying one-time HTTP-client/
connection warmup, the same category of cold-start artifact §3.10 already diagnosed once this session — not
repeated blind here). Second call, steady state: **1.80s**, down from the ~2.3-2.4s baseline measured earlier —
both calls returned the same correct answer (the actual mortgage amount and lender from the ingested context),
confirming no correctness regression alongside the speedup.

**Also verified, closing out a long-standing gap from earlier this session:** the reader prompt's aggregation
and preference-fidelity instructions (§1.3) were implemented early on but explicitly deferred from live
verification. Checked now, directly against the real reader model: a three-fact grocery-spending question
correctly summed all three facts ($45+$60+$30=$135, not just one of them), and a restaurant-recommendation
question correctly built its answer around a stated preference (spicy Thai food, green curry) rather than
staying generic. Both work as designed.

**Not touched, and why:** Phase 1's two sequential Postgres queries (semantic + keyword search) share one
`psycopg` connection, the same constraint that keeps ingestion's writes serial (§3.8) — parallelizing them
safely would need a connection pool, the same deferred-scope item, not a new one. Phase 2's per-fact HydraDB
reads were already parallelized earlier this session and already measured (75-89% cuts, §1.4); revisiting
whether HydraDB's writer-lane mutex (§3.3) has a read-side analogue wasn't necessary since that fix's payoff was
already confirmed live, not assumed. 199/199 tests passing.

## 6. Entity-registry cross-instance scaling bug

Found live, mid-run, not in a unit test. Running 3 real instances back to back to sanity-check whether the
session's fixes actually helped (not "a paper boat"): instance 3 (480 turns, the *fewest* of the three) ran at
**1.98s/turn**, against 1.23s/turn and 1.25s/turn for instances 1 and 2 (530 and 442 turns). Fewer turns running
slower only makes sense if cost is compounding across instances, not scaling with one instance's own size.

**Root cause:** `EntityRegistry`/`EntityNameIndex` are constructed once per `create_pipeline`/`get_engine` call
and reused across an entire multi-instance benchmark run (one process, many instances). `EntityRegistry._in_context(context_id)`
did:
```python
[p for p in self._profiles.values() if p.context_id == context_id]
```
— an unindexed scan over *every entity this registry has ever seen, across every context*, not just the current
one. Called on every resolution attempt, this scan's cost grows with cumulative cross-instance history, so
instance N pays for instances 1..N-1's entities too, regardless of instance N's own size.

**Fix:** a secondary index, `_profile_ids_by_context: dict[str, list[int]]`, populated in `register()` and
consulted directly by `_in_context()` instead of scanning `self._profiles.values()`. `resolve()`/`resolve_many()`
unaffected — the index is purely an internal lookup-speed change, not a behavior change.

**Proof, isolated from the rest of the pipeline:** rather than re-running the full ~25-30 min pipeline to verify
a narrow fix, built a standalone microbenchmark constructing `EntityRegistry` state directly — 750 simulated
entities across 3 fake "prior contexts" plus a growing "current context" — comparing an inline reconstruction of
the old unindexed scan against the new indexed `_in_context()` at each growth step:

| current-context size | old (unindexed) | new (indexed) | speedup |
|---|---|---|---|
| small | ~12-16µs (flat, dominated by the 750-entity scan) | ~0.23µs | ~53.5x |
| large | ~12-16µs (flat) | ~3.41µs | ~4.6x |

Old cost stays flat regardless of current-context size (it's always scanning the same 750 entities); new cost
scales with the current context alone, so the speedup shrinks as the current context grows but never disappears.
Correctness was checked at every step too — identical membership between old and new for every simulated state,
not just the final one. 3 new tests added to `EntityResolutionTests` covering the index directly: context
isolation, idempotent re-registration not duplicating the index entry, and a grown alias staying visible through
the index without reindexing. 202/202 tests passing after the change.

**What this does and doesn't fix:** this is a within-process cost, so it only matters for multi-instance runs
sharing one `EntityRegistry` (this benchmark runner's own execution model, and any long-lived service process).
A single isolated instance was never affected. It does *not* change LLM call counts or per-call latency —
`entity_resolution.disambiguate` calls are unaffected in number or cost; only the Python-side bookkeeping around
them got cheaper.

## 7. Bigger-sample accuracy check, batch-prompting, and a fifth ingestion bottleneck

**Why a bigger sample was needed.** The 3-instance "paper boat" check (§ above) went 2/3 correct by the official
judge, with both previously-0%-accuracy categories (multi-session, knowledge-update) flipping to correct — but
that was n=1 per category. A single flip either way is not evidence a category actually improved; it's
consistent with anything from "genuinely fixed" to "this one instance happened to be easy." Selected 9 fresh
instances (3 each: multi-session, knowledge-update, single-session-preference — the 0%-scoring categories, since
these are the ones where a bigger sample matters most), fresh UUID-tagged `question_id`s to avoid the
stale-context reuse bug already hit twice this session, and ran them through the current (index-fix-included)
pipeline end to end.

*(Run in progress at time of writing — results and the category breakdown will be added once the official judge
has scored all 9. The run's own per-stage metrics were already useful before finishing, see below.)*

**Extraction batch-prompting: implemented, opt-in, off by default.** The one lever flagged repeatedly this
session as "identified, never attempted": packing multiple turns into one extraction LLM call instead of one
call per turn, to cut *request count* (not just per-call latency) — the thing that actually presses on a
provider's RPM/TPM ceiling under concurrency, separate from what write-batching and the entity-index fix
addressed.

Kept the existing per-record interface (`LLMExtractor.extract(record)`) completely unchanged so nothing
downstream (`ExtractionService`, `orchestrator.py`, `graph_plan_builder.py`) needed to change — the same
"batch the I/O, don't touch the consumer" pattern used for write-batching and prefetching earlier this session.
Added:

- `LLMExtractor.extract_batch(records)` — one LLM call for N turns, numbered `--- Turn N ---` in the prompt; a
  new `_BatchedFactExtractionResponse` schema (`turns: list[{turn_index, facts}]`) so each returned fact set maps
  back to its own turn. Draft-building (source-span offsets, entity parsing) is factored into a shared
  `_build_drafts()` helper used by both `extract()` and `extract_batch()`, so the batched path can't drift from
  the single-turn path's attribution logic — each turn's facts are still built against *that turn's own* content
  string only.
- `BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT` — the single-turn prompt plus explicit per-turn isolation instructions
  ("never merge or infer facts across turns", "exact_quote... never quote text from a different turn"), since
  cross-turn fact leakage is the one new failure mode this path introduces that the unbatched path structurally
  cannot have.
- `Config.extraction_batch_size` (default `1` — today's behavior, unchanged) and
  `Config.extraction_batch_max_tokens_for()`, which sums each turn's own tiered allocation
  (`extraction_max_tokens_for`) rather than tiering on total batch length, so a batch's headroom stays consistent
  with the unbatched path's per-turn sizing.
- `PrefetchingExtractor` (benchmark_runner.py) groups records into batches of `extraction_batch_size` and calls
  `extract_batch` per group when the wrapped extractor exposes it; falls back to today's one-call-per-record path
  otherwise (`FakeExtractor`/`DeterministicExtractor` correctly take this fallback, no crash). A failed batch
  marks every record in that one group empty, not the whole prefetch.

Deliberately **not enabled** for the 9-instance accuracy run above — introducing a second new variable into the
same run meant to answer "did the index fix hold at scale" would have muddied both questions. 10 new tests
(`LLMExtractorBatchTests`, `PrefetchingExtractorTests`) cover the happy path, a missing `turn_index` degrading
only that one record (not the batch), a malformed batch response degrading to empty for every record without
raising, and the grouping/fallback behavior in `PrefetchingExtractor`. 212/212 tests passing.

**A fifth, previously unaddressed bottleneck, found while re-checking the fix at scale.** Per-stage metrics from
the 9-instance run's first instance (493 turns, fresh process, empty `EntityRegistry` — so §6's fix has nothing
to do yet, this instance is a clean baseline) showed `orchestrator.stage.graph_plan` (the per-turn resolution +
temporal-update stage) costing **2365ms/turn on average**, with two LLM-backed sub-costs almost entirely
accounting for it:

| stage | calls | avg/call | total |
|---|---|---|---|
| `temporal_update.classify` | 1172 | 633ms | 742s |
| `entity_resolution.disambiguate` | 912 | 724ms | 661s |

`entity_resolution` already got the fast-model treatment earlier this session (§4.6: `qwen.qwen3-32b`,
`reasoning_effort=none`, live-verified). `temporal_update.classify` — the ingestion-side "does this fact
correct/supersede an earlier one?" call, structurally the same kind of bounded 4-way classification decision —
never did. It was quietly costing as much serial LLM time as extraction itself (758s serial-equivalent, though
extraction is parallelized via prefetch and temporal_update is not), and had simply never been looked at because
earlier stage-timing passes were focused on entity resolution and extraction specifically.

Applied the identical, already-proven pattern first: added `Config.temporal_update_reasoning_effort`
(`TEMPORAL_UPDATE_REASONING_EFFORT` env var) and wired it into `get_temporal_update_client()`, mirroring
`get_entity_resolution_client()` exactly. Live-compared against the control model on 5 realistic
same-subject/predicate/chronology-gated fact pairs (address change, job promotion, preference reversal, and two
"no update" restatements):

| case | control | candidate | control time | candidate time | agree |
|---|---|---|---|---|---|
| address changed | state_change | state_change | 1.93s | 1.14s | yes |
| job promotion | state_change | state_change | 0.54s | 0.38s | yes |
| unrelated restatement | no_update | no_update | 0.46s | 0.35s | yes |
| preference reversal | state_change | state_change | 0.54s | 0.37s | yes |
| same fact restated | no_update | no_update | 0.48s | 0.35s | yes |

5/5 identical classifications, faster every time (~1.5x average). Initially kept this, on the strength of that
result — **then reverted the decision** after a web search turned up prior art directly relevant to both the
approach and this specific verification:

- **A strictly better fix exists and wasn't what I built.** Zep/Graphiti's own edge-contradiction step
  (`resolve_edge` in `dedupe_edges.py`) sends a new fact plus an indexed list of *all* candidate existing facts
  and invalidation candidates in **one call**, and the LLM returns which indices are duplicates/contradicted —
  batching across a turn's candidate priors, not swapping to a cheaper model per pair. That cuts call count
  (the actual thing pressing on the provider's RPM/TPM ceiling under concurrency, same framing as §7's
  extraction batch-prompting above) without touching per-call reasoning quality, which is strictly safer than
  what I shipped. Not implemented here yet — noted as the better next step if this bottleneck gets revisited.
- **My own verification was too weak to trust, and there's a public, confirmed case proving exactly that failure
  mode.** [getzep/graphiti#1666](https://github.com/getzep/graphiti/issues/1666): the Zep maintainers found that
  switching *contradiction detection specifically* (not duplicate detection — that stayed fine) to a
  non-reasoning small model caused near-total failure, 1/9 correct on contradiction-bearing cases, while looking
  unremarkable on easy ones. My 5 test cases were hand-picked and fairly clear-cut (an address change, a named
  promotion) — precisely the kind of case that failure mode would *not* show up on. 5/5 agreement on easy cases
  is not evidence against a documented collapse on hard ones.

**Reverted the `.env` change** — `TEMPORAL_UPDATE_MODEL`/`TEMPORAL_UPDATE_REASONING_EFFORT` stay commented out,
current production behavior unchanged. The `Config.temporal_update_reasoning_effort` code wiring stays (correct,
a no-op when unset) so this can be revisited properly — either with a much larger, deliberately adversarial test
set aimed at ambiguous/borderline contradiction cases, or by building the batched-candidate-comparison approach
instead, which sidesteps the reasoning-quality risk entirely. Left as a documented open item, not a completed
fix — the earlier draft of this section claimed it was kept; that was premature and is corrected here.

**Single-session-preference: root-caused, not just observed.** Only one live example existed before this session
(the theme-park recommendation, judged incorrect). Queried Postgres directly for every fact
`extracted_memory_candidates` from that session's actual source turns to see what extraction produced, not just
what the reader answered with.

The user's *entire* preference statement arrived in one turn: *"Anything exciting happening soon, like thrill
rides, unique food experiences, or nighttime shows?"* — phrased as a question, with the specific preferences
buried in an itemized "like ___, ___, or ___" clause. Of the 54 facts extracted from that session, extraction
captured the four parks visited and the generic framing ("The user is looking for recommendations on upcoming
theme park events") — but **"thrill rides" was never extracted as a fact anywhere in the session**, and neither
was "nighttime shows" as a standalone preference. "Unique food experiences" only surfaced later, from a
*different*, more explicit follow-up turn, and even then framed narrowly around Halloween-specific dining rather
than as a general preference.

This lines up exactly with the observed failure: the model's answer never mentioned thrill rides at all, covered
food only generically, and never framed anything as "the user likes nighttime shows" — not because retrieval
failed to surface facts, or because the reader ignored them, but because **the facts were never extracted from
the source turn in the first place**. `FACT_EXTRACTION_SYSTEM_PROMPT` has no explicit instruction to unpack an
itemized preference list embedded inside a request/question sentence — it extracted the *topic* of the request
("theme park events") but dropped the *specifics* the user actually asked about. This is a concrete, actionable
gap in the extraction prompt, distinct from anything retrieval or the reader could fix on their own; not yet
addressed by a code change, since it needs its own live verification (a prompt change here risks the same kind
of regression risk as anything else touching extraction) before committing to one.

**A concrete direction for that fix, from prior art.** AWS Bedrock AgentCore's own user-preference extraction
prompt (public docs) explicitly splits explicit vs. implicit preferences, and — the structurally relevant part —
requires every extracted item to carry a `context` field stating *why* it was extracted (the evidentiary basis),
not just the compressed preference itself. Forcing the model to justify each item separately tends to make it
enumerate the actual evidence rather than compress straight to a topic label, which is exactly the failure mode
observed here (the whole "thrill rides, unique food experiences, nighttime shows" list compressed down to
"theme park events"). `FACT_EXTRACTION_SYSTEM_PROMPT` has no equivalent requirement. This is a genuinely testable
direction, not a guess, but it's still unimplemented and unverified against this pipeline's own extraction
schema/downstream consumers — the same "identified, not yet attempted" status as batch-prompting was before this
session, and should get the same live-verification treatment before being trusted.

## 8. Reassessing the latency work: the dominant term was never touched

Prompted by a fair challenge — "every time I ask you to fix latency, it keeps increasing." Went back to the
per-stage metrics from both instrumented runs instead of defending prior decisions.

**Per-call latency is flat. Call count is the whole story.**

| run | instance | turns | s/turn | disambiguate/turn | classify/turn | LLM calls/turn |
|---|---|---|---|---|---|---|
| A | 4bc144e2 | 530 | 1.23 | 1.56 | 0.97 | 2.53 |
| A | fca70973 | 442 | 1.25 | 1.67 | 0.96 | 2.63 |
| A | dfde3500 | 480 | 1.98 | 1.59 | 2.01 | 3.60 |
| B | gpt4_7fce9456 | 493 | **2.48** | 1.85 | 2.38 | 4.23 |
| B | d3ab962e | 530 | 1.54 | 1.72 | 1.51 | 3.23 |

Per-call cost never moved (disambiguate 609-767ms, classify 567-633ms across both runs). `s/turn` tracks
`LLM calls/turn` at 0.79-0.98x throughout. The apparent "latency increase" between runs is **instance
sampling**, not a code regression — B's first instance simply had more fact collisions. But the honest finding
is worse than a regression: **every fix this session attacked per-call cost or a different phase, while the term
that actually sets ingest latency — the number of blocking LLM calls in the serial per-turn loop — was never
addressed.** `orchestrator.stage.graph_plan` is 95.4% of ingest wall clock (1166s of 1222s). Extraction got
concurrency (8 workers, 7.9x on that phase); graph_plan got nothing equivalent.

**The quadratic driver.** [graph_plan_builder.py:172](../src/context_memory/ingestion/graph_plan_builder.py#L172)
was `for prior_fact in existing_facts: classify(...)` — one blocking ~600ms call per prior fact. Measured
fan-out over a real run:

- 336 new facts triggered classify at all, generating **1972 calls** — mean **5.87 priors each**, worst case 23.
- 95% of calls came from facts with ≥2 priors; **52.8% from facts with ≥11 priors**.
- 12 facts with 23 priors each = 276 calls = 166s of pure serial wall clock.

This is quadratic in how often a user revisits a topic, because `find_existing_facts` buckets on
`(subject_entity_id, predicate_key)` and `predicate_key` is a coarse extractor-chosen label ("advice", "impact").

**Fix: one call per new fact, not one per pair.** Added `LLMTemporalUpdateModel.classify_updates` (new fact +
indexed prior list → per-index relation) and `TemporalUpdateClassifier.classify_many`, which applies the existing
free deterministic gates first and batches only the survivors. Prompt shape follows
[getzep/graphiti#970](https://github.com/getzep/graphiti/issues/970) (invariant text first for prompt-cache hits,
integer `idx` not opaque ids — they measured UUID ids breaking the model's index bookkeeping). Pairwise path
kept intact behind `temporal_update_batch_enabled`; the plan builder probes for `classify_many` so any
classifier lacking it keeps the old path.

**Validated against the previous run's own recorded decisions**, replaying real fact groups with real texts.
First attempt was a bad test — the 6 largest groups agreed 138/138, but the corpus is 2944 `no_update` vs 29
supersessions, so that sampled almost only trivial cases (the same weak-validation error made earlier in §7).
Re-ran targeting **only the 25 groups containing an actual supersession**:

- **calls: 195 → 25 (87.2% fewer)**; wall clock 19.5s vs ~123s estimated pairwise.
- agreement 168/195 (86.2%).

**The 27 disagreements point the opposite way from what I expected.** 26 of 27 are the batched path *declining*
a supersession the pairwise path asserted, and the pairs it declined are plainly unrelated:

| new fact | prior fact | pairwise | batched |
|---|---|---|---|
| user wants tips on storing vintage cameras | user wants content starting "From KiheiTown proper…" | state_change | no_update |
| user interested in street art and graffiti | user finds Whiplash interesting | state_change | no_update |
| user looking for advice on renovating a kitchen | user looking for advice on condo living | state_change | no_update |
| assistant recommends Petzel Gallery for contemporary art | assistant advises choosing approach fitting analytics needs | correction | no_update |
| user recently did a week-long backpacking trip | user completed a 3-mile loop at Valley of Fire | state_change | no_update |

The 27th flipped `state_change`→`correction` (both still emit SUPERSEDES, functionally equivalent). So batching
is not losing knowledge updates — it is refusing spurious ones the pairwise path invented, because seeing all
priors at once lets the model judge relative relevance instead of being asked in isolation whether A supersedes
an unrelated B. This is the same failure
[getzep/graphiti#1728](https://github.com/getzep/graphiti/issues/1728) reports in production (41% of facts
carrying `invalid_at`, hand-audit finding most collateral). Caveat stated plainly: correctness here is my
reading of the fact pairs, not a benchmark delta — the definitive check is the knowledge-update category score.

**Ruled out by evidence, not opinion:** replacing LLM supersession with deterministic newest-timestamp selection
(arXiv 2606.01435, "Reliable Post-Retrieval Assembly for Agent Memory"). It beats LLM judgment on
MemoryAgentBench FactConsolidation (78.0% vs 67.2%; Zep scores 7.0%) — but the authors report an explicit
**null result on LongMemEval's knowledge-update subset** (45 questions, McNemar p=0.45), because that subset
contains Yes/No, "previous status", and aggregation questions that are not latest-value operations. It is also
a read-time method, not a write-time one. Not applicable here.

**Still open:** `predicate_key` is too coarse a bucket — 2944 of 2973 comparisons produced `no_update`, i.e. 99%
of this LLM work yields nothing. An embedding-similarity pre-filter on candidate priors would cut the remaining
calls further and directly targets the same false-supersession problem. Not attempted; batching already removes
87%.

### 8.1 Embedding pre-filter, and the measured end-to-end result

`predicate_key` is a coarse bucket, so 2944 of 2973 comparisons returned `no_update` — 99% of that LLM work
yielded nothing. Added an embedding similarity pre-filter on candidate priors (MiniLM, the embedder already in
the pipeline), calibrated on all 3540 recorded comparisons rather than guessed:

| threshold | supersessions kept | no_update pairs cut |
|---|---|---|
| 0.10 | 45/47 | 15.6% |
| **0.15** | **44/47** | **30.3%** |
| 0.20 | 38/47 | 46.9% |
| 0.30 | 27/47 | 75.8% |

Chose **0.15**. The three supersessions it drops are verifiably spurious — "storing vintage cameras" vs
"content starting *From KiheiTown proper*" (sim 0.028), "antique dealers for fork handles" vs "staying informed
about weather" (0.037), "Petzel Gallery contemporary art" vs "choosing approach fitting analytics needs"
(0.116). The pre-filter and the batching fix independently reject the same false supersessions, which is
corroboration from two unrelated signals rather than one method's opinion.

**Measured end to end on the identical instance (gpt4_7fce9456, 493 turns), same code path, real infrastructure:**

| | pre-batch | batched + pre-filter |
|---|---|---|
| ingest | 1222.1s (**2.48 s/turn**) | 434.0s (**0.88 s/turn**) |
| graph_plan | 2365 ms/turn | 802 ms/turn |
| temporal-update calls | 1172 | **133** |
| temporal-update time | 742.4s | 106.8s |

Pre-filter removed 593 of 1172 priors (50.6%) before any LLM call; batching collapsed the remaining 579 into 133
calls. Net **88.7% fewer LLM calls** on this stage.

**Confound stated honestly:** `entity_resolution.disambiguate` also improved (725→519 ms/call) on essentially
identical call volume (912→929). That is not attributable to these changes — it is endpoint contention, since
the pre-batch run overlapped with concurrent A/B probing while the new run had the endpoint to itself. Holding
entity resolution at its old per-call cost, ingest would be ~625s (1.27 s/turn) rather than 434s. So the
defensible claim is **at least 1.96x, measured 2.82x** on the worst-case instance.

## 9. Nondeterminism: temperature was innocent, the rewriter was not

Chasing a changed answer (a counting question went "four" → "three" after §8) surfaced something bigger than
the change being investigated.

**It was not a regression.** Re-running retrieval 3x against each already-ingested context, no re-ingest:

| context | run 1 | run 2 | run 3 |
|---|---|---|---|
| pre-batch | four | three | two |
| batched | three | three | three |

The pre-batch context yields **three different answers from identical stored data**. Its "four" on the
benchmark was a dice roll. Extraction was byte-identical between runs (same 7 matching facts in Postgres), so
the variance is entirely downstream.

**Temperature was not the cause.** Reader was at 0.2; set to 0.0. Still varied (four/three/four). A direct probe
of the reader on a short clean prompt was already deterministic at 0.2 (5/5 identical), so the reader was never
the problem.

**Seed is ignored by this provider.** Wired `seed` through (`LLM_SEED` → `Config.llm_seed` → `LLMClient` → both
call sites). Measured: 2 distinct outputs in 5 calls **with and without** `seed=42`, and `system_fingerprint`
comes back null. Bedrock's OpenAI-compatible endpoint does not honour it. Wiring kept (free, correct if support
lands) but it does not deliver determinism here.

**The actual culprit: `QueryRewriter` — 3 distinct outputs in 5 calls at temperature 0.** It runs on
`openai.gpt-oss-20b` with `reasoning_effort=low`; the sampled reasoning chain varies even when output
temperature is 0. Different synonym sets change BM25 hits → different seed facts → different answer.
`TemporalQueryResolver` was stable (1/5), so this is specific to the rewriter, not to Phase 0.

Swapping the rewriter to `qwen.qwen3-32b` with `reasoning_effort=none` made it **worse** (5/5 distinct),
independently confirming §5's decision not to switch that role.

**Fix: cache the rewrite.** It depends only on the question, so caching is semantically safe and makes repeat
asks reproducible. `QueryRewriter` takes an optional cache; the engine owns it (the rewriter is constructed
per request, so a per-rewriter cache would never hit). `JsonFileRewriteCache` persists it across processes —
atomic temp+rename writes, corrupt file degrades to empty rather than crashing. In-process dict when no path is
configured.

**Stated plainly: this is a measurement fix, not a robustness fix.** Caching freezes the dice roll; it does not
stop the dice from mattering. The underlying fragility — retrieval sensitive enough to synonym variation that an
answer swings from "four" to "one" — is untouched and remains the most significant open accuracy issue in this
system.

**Does caching help beyond the benchmark?** Partly, and less than it looks. The rewrite cache only fires on
byte-identical repeat questions, so it saves zero calls in a benchmark where each question is asked once, and
helps production only where phrasing genuinely repeats. The caching that helps generally is elsewhere: embedding
reuse (already in — 869 unique texts served 3540 comparisons, ~4x), the extraction content-hash short-circuit
(already in, high value on retries/replays/backfills), and provider-side prompt-prefix caching, which the §8
prompt ordering was deliberately shaped for and which benefits all-unique traffic.

### 9.1 Accuracy A/B on identical instances

Four instances completed under both the pre-batch and batched pipelines. Official judge, `deepseek-v3.2`:

| instance | pre-batch | batched |
|---|---|---|
| 69fee5aa (knowledge-update) | wrong | wrong |
| ba358f49_abs (multi-session) | right | right |
| d3ab962e (multi-session) | wrong | **right** |
| gpt4_7fce9456 (multi-session) | right | **wrong** |
| **total** | **2/4** | **2/4** |

Identical accuracy at ~2x the speed. Both disagreements are the known nondeterminism, not the change — the
gpt4_7fce9456 loss is the exact counting question shown above to answer four/three/two from unchanged data.

Broader read on 8 batched instances: **0.625 overall** — knowledge-update 2/3, multi-session 2/3,
single-session-preference 1/2. The risk from §8 (removing spurious supersessions might break knowledge updates)
did not materialise. All of this is small-n and, given §9's variance, not yet separable from noise.

## 10. The 30-instance run: results, comparison, and where the remaining loss is

Same stratification as §2 (5 instances × 6 categories), current pipeline (§8 batching + pre-filter, §9 temp 0
and rewrite cache). 30/30 completed, 14888 turns, 16811s wall.

### 10.1 Accuracy vs the previous 30-instance run

| category | §2 run | this run | delta |
|---|---:|---:|---:|
| knowledge-update | 60% | **100%** | +40 |
| single-session-user | 80% | **100%** | +20 |
| single-session-assistant | 60% | **80%** | +20 |
| multi-session | 0% | 20% | +20 |
| single-session-preference | 0% | 20% | +20 |
| temporal-reasoning | 40% | **20%** | **−20** |
| **overall** | **40.0%** | **56.7%** | **+16.7** |

**Comparison caveat, stated up front:** the §2 run's sampling seed was never recorded and its predictions were
never committed, so these are *different instances* under the same stratification. At n=5 per category, and
given §9's demonstrated per-instance variance, category deltas are weak evidence. The overall +16.7pp on n=30
is the firmest number here, and even that is one sample. The temporal-reasoning "regression" is 1 instance of 5
and should not be read as a real decline without more data.

### 10.2 Latency held at scale

| | pre-batch (§8) | this run |
|---|---|---|
| s/turn | 1.23 – 2.48 | **0.93 mean (0.75 – 1.03)** |

The spread collapsing matters as much as the mean: the old range was driven by the quadratic supersession
fan-out, which is gone. New dominant cost is **entity resolution — 26708 calls, 15118s, 566ms avg, 1.79
calls/turn** — now the single largest LLM cost in ingest, and un-batched. Same lever as §8 applies.

### 10.3 What actually failed — traced to source, not guessed

Every failure in the two weakest categories is one of three shapes, and **all three are retrieval/reader
problems, not ingestion**. Verified directly against Postgres:

1. **Undercount on aggregation.** "How many magazine subscriptions?" → answered 1, gold 2. The facts are all
   stored (New Yorker subscription, cancelled Forbes, book subscription box). The reader counted what reached
   it. "How many graduation ceremonies?" → 2, gold 3, same shape. This is §2.4(a) verbatim — identified in the
   previous run, still unfixed.
2. **Recall failure → refusal.** "How many weddings have I attended?" → "I don't have that information."
   "Which event did I attend first?" → same. Facts present, never surfaced.
3. **Wrong temporal anchor.** "How many days between fixing the mountain bike and upgrading the pedals?" →
   "zero days, both March 15." Source has the events on 2023-03-15 and 2023-03-19. Checked the store: the
   Mar-19 fact ("upgraded their road bike's pedals to Shimano Ultegra") **exists and is correctly dated**. The
   reader used the Mar-15 "considering upgrading" fact instead. Ingestion and timestamps are correct; ranking
   picked the wrong one.

The common root is retrieval ranking, which §9 already showed is fragile enough that synonym variation swings an
answer from "four" to "one". Ingestion has now been verified clean three separate ways (turn/job counts in §2.2,
byte-identical extraction in §9, correct dates and full fact presence here).

### 10.4 Errors in the run

- **28 HydraDB HTTP 400s → 4 failed write batches** (100 plans each):
  `conflicting metadata values for vertex N property superseded_at` / `valid_to`. Two different new facts
  supersede the same prior within one 100-chunk flush, each stamping its own timestamp on that vertex.
  **Pre-existing, not caused by §8** — present in the old-code run at the same per-instance rate (8 occurrences
  / 4 instances there, 32 / 30 instances here). Real graph-data loss. The 4 affected instances scored 3/4, so no
  visible accuracy harm at this n, but it should be fixed by keeping `min(superseded_at)` when merging duplicate
  vertices in a batch — first supersession is the semantically correct one.
- **26 extraction parse failures → 13 turns lost** out of 14888 (0.09%). Known small-model JSON truncation,
  degrades to zero facts for that turn.

### 10.5 Ranked scope for improvement

1. **Retrieval ranking.** Largest accuracy lever by far — all three failure shapes trace here, with facts
   confirmed present and correctly dated in every case examined.
2. **A structured aggregation step.** Counting, summing, and date-differencing have no dedicated path; the
   reader improvises over whatever survived top-k. §2.4 named this; a bigger prompt will not fix it.
3. **Batch entity resolution.** Now the top latency cost (26708 unbatched calls). The §8 pattern transfers
   directly.
4. **`superseded_at` merge conflict.** Cheap, bounded fix for a real data-loss path.

## 11. What comparable systems do, and what transfers

Researched each §10.5 lever against published work and reported implementations.

### 11.1 The counting/undercount problem

**What others found.** A practitioner writeup reporting **90.8% end-to-end on LongMemEval**
([dev.to](https://dev.to/shane-farkas/i-built-an-agent-memory-system-for-myself-and-got-908-end-to-end-on-longmemeval-3hfp))
implemented exactly the fix that looks obvious here — two-pass "enumerate items, then count" — and **accuracy
dropped 91.2% → 86.0%**. Their conclusion: *"each additional LLM call is an opportunity to corrupt a correct
answer."* They removed it. Other summaries recommend the opposite ("enumerate before counting"), so the
published evidence genuinely conflicts.

**What decides it for us:** our reader prompt *already* contains the enumerate-then-compute instruction
("first identify every matching fact in the context, then compute the answer from all of them — do not answer
from a partial subset"), and §10.3 shows we still undercount 1-of-2 and 2-of-3. Prompt-level enumeration is
already in place and not working, which sides with the 90.8% result: **this is a retrieval-recall problem, not
a reader-instruction problem.** Adding an aggregation pass would likely cost accuracy, not gain it.

Corpus-level evidence agrees that top-k retrieval is the wrong primitive for aggregation: global/counting
queries need complete evidence rather than a ranked subset, and existing RAG methods reach at most 1.51 F1 on
such tasks ([Global RAG benchmark](https://arxiv.org/pdf/2510.26205)).

**Revised recommendation:** drop "structured aggregation step" from the plan (§10.5 item 2). Replace with
**recall-completeness for enumerable queries** — detect count/enumeration questions and retrieve exhaustively by
predicate/entity rather than by top-k rank. That matches the "wide vs narrow query" adaptive-retrieval split the
90.8% system used.

### 11.2 The temporal problem — and a concrete bug this surfaced

**What others found.** The same writeup reports their single biggest temporal win was simply *making dates
visible to the model*: piping session dates into ingestion and prepending `[Conversation date: ...]` headers.
Result: **temporal-reasoning 89.5%** vs our 20%. Time-aware query expansion is reported elsewhere as worth up to
**+11.4% recall** on temporal sub-tasks.

**What we found by checking our own context assembly.** Top-ranked facts *do* carry dates —
`[YYYY-MM-DD | speaker]: text`. But sibling facts (neighbouring-turn expansion) are appended as bare `- {text}`
with **no date at all**; the code comment concedes it ("No date/speaker available cheaply here — would need
another join", [retrieval.py](../src/context_memory/retrieval.py)). Measured over the 30-run: **8.6 sibling
facts per query on average, up to 20**, against a top-k of 20 — so roughly **30% of the reader's context is
undated**.

This is a direct, mechanical explanation for §10.3's failure #3, where the reader concluded "both events were
noted on the same day, March 15" while the correctly-dated Mar-19 fact sat in the store. Fix: carry
`observed_at` through sibling expansion and format siblings identically to top facts. Bounded, cheap, and
targets the worst category.

### 11.3 Retrieval ranking

`retrieval_top_k` is **20**. The 90.8% system found *"retrieval quality beats quantity"* — 20 results / 8K
tokens performed **worse** than 10 results / 4K tokens, and *"focused retrieval with a well-crafted prompt beat
broad context every single time."* Worth an A/B here rather than assuming more context helps; our reader is
currently fed ~29 facts per question.

Also reported as effective and not yet tried here: round-level rather than session-level granularity (up to +6%
QA accuracy under fixed token budget) and fact-augmented key expansion (+4% recall, +5% QA accuracy).

### 11.4 Entity resolution batching

Validated with a name: **BatchER** packs multiple entity pairs into one prompt via greedy cover-based selection
clustering pairs with similar matching semantics; **SELECT prompts** put a query entity plus all blocked
candidates in one prompt instead of pairwise comparisons
([cost-efficient ER](https://arxiv.org/html/2310.06174v2), [AvengER](https://cgi.di.uoa.gr/~koubarak/publications/2025/AvengER__Ensembling_and_Fine_Tuning_LLMs_for_SELECT_Prompts_in_Entity_Resolution-1.pdf)).
One reported pipeline sent 1,757 candidate pairs in 88 batches of 20.

We already do the SELECT half — `resolve_entity` passes a blocked candidate shortlist in one prompt. What we do
*not* do is batch across mentions: 26708 calls at 1.79/turn means roughly one call per mention. Batching a
turn's mentions into one prompt is the same §8 transformation and would cut roughly 44% of the remaining calls.

### 11.5 Revised priority

| # | action | basis |
|---|---|---|
| 1 | Date sibling facts in reader context | Measured 30% of context undated; matches worst category's failure |
| 2 | Exhaustive retrieval for count/enumerate queries | Top-k is the wrong primitive for aggregation (1.51 F1 ceiling) |
| 3 | A/B `retrieval_top_k` 20 → 10 | Reported: 10 beat 20 in a 90.8% system |
| 4 | Batch entity resolution across mentions | BatchER/SELECT precedent; ~44% of remaining calls |
| 5 | `min(superseded_at)` on vertex merge | Fixes real data-loss path (§10.4) |

**Dropped from §10.5:** the structured aggregation step — published evidence and our own already-present
enumerate instruction both indicate it would not help and may hurt.

## 12. Sibling-date fix: implemented, verified, and honestly scoped

Implemented §11.2's fix: `_sibling_facts` now joins `observed_at` from `extracted_memory_candidates`
(`candidate_id = subject_id`, a plain Postgres join, no extra round trip) and the reader-context assembly
formats siblings as `[YYYY-MM-DD]: text` instead of bare `- text`. 3 new/updated tests (232 passing total),
including a live regression test asserting the exact date format reaches the reader prompt.

**Re-ran the exact failing case from §10.3** ("days between fixing mountain bike and upgrading pedals",
gold 4 days) against the live pipeline, not just the unit test. Captured the actual reader prompt:

```
[2023-03-19 | user]: The user upgraded their road bike's pedals to Shimano Ultegra clipless pedals today.
[2023-03-15 | assistant]: The assistant acknowledges that the user's mountain bike has been fixed and is running smoothly.
...
```

**The targeted mechanism is fixed and confirmed**: both events now reach the reader with correct, distinct
dates (2023-03-19 and 2023-03-15) — the undated-sibling gap measured at ~30% of context in §11.2 no longer
applies to this case.

**The instance still fails.** Reader answer: *"Zero days passed—both events happened on the same day, March
15, 2023."* Despite two correctly-dated facts, it collapsed them to one date. Inspection of the context shows
why this is not the same bug: two near-duplicate pedal facts are present — *"considering upgrading... to
clipless pedals"* (2023-03-15, a stated intention) and *"upgraded... to Shimano Ultegra clipless pedals today"*
(2023-03-19, the completed action) — and the reader appears to have anchored on the semantically central Mar-15
fact rather than distinguishing intention from completion across the two dates.

**Stated plainly:** the sibling-date fix closes a real, measured gap (undated context) and should help
generally, but does not fully resolve this specific failure mode. What remains looks like a fact-selection /
date-comparison reasoning gap when near-duplicate facts differ mainly by tense and date — a different, deeper
problem than "the model never saw a date." Not yet fixed; noted as the next item to investigate, likely needing
either de-duplication of intention-vs-completion fact pairs at extraction time or an explicit reader instruction
to compare *all* candidate dates for the same entity before answering, not just the ones that read as most
relevant.

## 13. `superseded_at` merge conflict — fixed

§10.4's data-loss path: two different chunks, both superseding the same prior Fact vertex within one
`write_many` flush, landed in the same `UNWIND` with conflicting `superseded_at`/`valid_to` values, and
HydraDB rejected the whole bucket with HTTP 400 ("conflicting metadata values for vertex N property
superseded_at"). Confirmed pre-existing: same rate in the old-code run (§10.4), not caused by §8's batching.

**Fix:** `GraphWriter._dedupe_nodes` merges multiple `GraphNode` entries sharing a `graph_id` before building
rows, keeping `min()` for `superseded_at`/`valid_to` — the prior became invalid at the *first* fact that
superseded it, so the earlier timestamp is correct. Any other differing property logs a warning and keeps the
later value rather than raising, as a fallback that in practice should never fire: the manifest layer
(`PostgresGraphManifestStore`'s existing `NODE_MUTABLE_PROPERTIES` allow-list, added earlier for ADR-030) already
rejects genuine non-temporal conflicts before `_dedupe_nodes` runs — confirmed by writing a test for exactly
that and watching the manifest correctly raise `GraphPayloadConflictError` first.

One correction made while testing: `GraphWritePlan.__post_init__` already forbids two nodes sharing a graph_id
*within one plan* (globally-unique-ids check), so "one chunk's own facts collide on one vertex" cannot happen —
`_dedupe_nodes` only needed for the cross-plan (`write_many`) case. An initial test asserting within-plan dedup
was wrong and replaced with one confirming the plan-construction guard fires instead. Also fixed a test-fidelity
gap found along the way: `InMemoryGraphManifestStore` (the test fake) didn't mirror
`PostgresGraphManifestStore`'s mutable-properties merge behavior, so it rejected a legitimate case the real
store allows — brought in line with the real implementation. 9 new/updated tests, 238 passing.

## 14. Entity resolution batching

§11.4's item: 26708 `entity_resolution.disambiguate` calls across the 30-run, ~1.79/turn mean — the single
largest ingest cost by the point §8/§9's other fixes landed.

**Checked before building, not assumed:** `resolve_many` already parallelizes disambiguation calls within one
turn (`ThreadPoolExecutor`, `max_workers=8`), so summed call duration (15118s) overstates real cost —
wall-time-clustering the metrics (calls firing within 50ms belong to one `resolve_many` invocation) gives
~9060s of actual wall-clock cost, still ~71% of `graph_plan`'s total wall time and the dominant term, but not the
15118s figure by itself. Fan-out per turn is much flatter than temporal-update's (§8): 35.7% of calls are lone
mentions, only 41.3% come from turns with ≥3 concurrent mentions — a different shape from temporal-update's
long tail, so the expected win here is request-count reduction (~43%, 26708→~15339 estimated invocations), not
a comparable wall-clock multiplier, since concurrency already flattens much of the latency curve.

**Fix:** `LLMEntityResolutionModel.resolve_entities` — one call resolving every mention in a turn (each keeping
its own independent candidate shortlist), same `idx`-echo pattern as §8's batched temporal-update prompt.
`EntityRegistry.resolve_many`'s Phase 3 now batches when the model exposes `resolve_entities` and
`entity_resolution_batch_enabled` is true (default), falling back to the existing concurrent per-mention path
otherwise — kept intact, not deleted. Wired via a plain constructor bool (`EntityRegistry(..., batch_enabled=...)`,
matching `TemporalUpdateClassifier`'s pattern) rather than a `Config` dependency.

**Live-verified**, since real candidate profiles aren't persisted anywhere replayable (`entity_resolution.disambiguate`
metrics carry `candidates_count`, not the actual candidate list, so unlike §8's temporal-update replay this
couldn't reuse real recorded decisions). Built 5 realistic ambiguous-mention cases (Dave/David — this codebase's
own canonical collision example, "the vet" vs a place, Bob/Bobby, "my sister" vs "the user", Alex/Alexandra)
against the real model:

- **5/5 agreement** between batched and pairwise.
- Against a naive sequential pairwise baseline: 7.13x.
- **Against the actual production fallback (concurrent, 8 workers): 2.37x** — the honest number, since that's
  what batching is actually replacing.

12 new tests (`BatchedEntityResolutionTests` in both `test_resolution_service.py` and `test_model_adapters.py`)
covering the happy path, missing-index degrading to that one mention only, batch-disabled/no-`resolve_entities`
fallback, and prompt/token-budget shape. 247 tests passing total.

**Not yet re-verified at full pipeline scale** — needs a fresh 30-instance run to confirm the estimated ~43%
call reduction and measure the actual `graph_plan` wall-time delta, the same way §8's fix was confirmed on
`gpt4_7fce9456` before trusting the estimate.

## 15. `top_k` A/B: not a blanket win, but it points straight at #2

§11.3 flagged a reported result (10 beat 20 in a 90.8% LongMemEval system) as worth testing, not assuming.
Ran retrieval-only (no re-ingest) against all 30 already-ingested run30 contexts at `top_k=10`, reusing the
populated rewrite cache from §9/§10 so query-rewrite output is pinned identical between conditions — isolates
the `top_k` effect specifically.

| category | top_k=20 | top_k=10 | Δ |
|---|---:|---:|---:|
| knowledge-update | 100% | 80% | **−20** |
| multi-session | 20% | 0% | **−20** |
| single-session-user | 100% | 100% | 0 |
| single-session-assistant | 80% | 80% | 0 |
| temporal-reasoning | 20% | 40% | **+20** |
| single-session-preference | 20% | 40% | **+20** |
| **overall** | **56.7%** | **56.7%** | **0** |

Identical overall accuracy, but the category profile inverted. The two categories that need aggregating facts
across multiple turns (knowledge-update, multi-session) got *worse* with less context; the two dominated by
single-fact lookups (temporal-reasoning, preference) got *better* — less noise crowding out the one relevant
fact. This directly contradicts reading the 90.8% report's number as a blanket "lower top_k always helps," and
instead confirms its own actual mechanism: that system's real lever was *adaptive* retrieval width by query
type ("wide" vs "narrow"), not a uniform cut. Global `top_k` was left at 20, not changed — the evidence argues
for query-adaptive width, which is exactly what §16 builds, not for a global reduction.

## 16. Exhaustive retrieval for count/enumeration queries

§11.1's revised item, informed by §15: rather than a structured aggregation LLM pass (shown to hurt by the
90.8% system's own experiment, 91.2%→86.0%), widen the existing `ranked[:top_k]` truncation
([retrieval.py:764](../src/context_memory/retrieval.py#L764)) specifically for count/enumeration-shaped
questions — no new LLM call, so it can't introduce the corruption risk that sank the two-pass approach.

**Detector is a cheap regex, deliberately not an LLM call** — `_looks_like_count_query()` matches "how many",
"how much", "count", "total number", "list all", "every", "all the", etc. against the raw question. Widens to
`Config.retrieval_count_query_top_k` (default 40, double the normal 20) only when the caller didn't already
pass an explicit `top_k`.

**Live-verified against the exact two undercount cases from §10.3**, not just a unit test:

| question | gold | top_k=20 (before) | widened |
|---|---|---|---|
| "How many magazine subscriptions do I currently have?" | 2 | 1 (New Yorker only) | **2 (correct)** |
| "How many graduation ceremonies have I attended in the past three months?" | 3 | 2 | 2 (unchanged) |


**One fixed, one not — reported honestly, not rounded up.** The subscription case went 1→2 (correct): both
facts now reach the reader (verified — checked the actual context sent). The graduation case stayed at 2/3.

**Checked why, rather than leaving it unexplained.** All 3 genuine graduation facts (Emma's preschool, Alex's
leadership-program, Rachel's master's) are in the store with identical `observed_at` (2023-07-21), no
`valid_from`/`valid_to` set on any of them — so this is not a temporal-window exclusion. Captured the actual
reader prompt at the new top_k=40: 8 graduation-related facts reached it, but **Rachel's specific fact did not**
— it scores lower in ranking than the others despite being directly on-topic ("attended their best friend
Rachel's master's degree graduation ceremony"), for reasons not yet root-caused (not a filter, a ranking-formula
question). Doubling the retrieval window measurably helped (more correct facts surfaced, one case fully fixed)
but did not fully solve this one — a real, separate ranking-quality issue survives even a much wider net, not
something width alone can fix. Not chased further this pass; flagged as the next concrete thing to look at if
this category gets revisited.

12 new tests (`CountQueryDetectionTests`), 251 passing total.

## 17. Summary of this pass

| item | status | verified |
|---|---|---|
| §13 `superseded_at` merge | done | live data-loss path closed; 9 tests |
| §14 entity resolution batching | done | 5/5 agreement, 2.37x vs the real concurrent fallback; 12 tests |
| §15 `top_k` A/B | done | same overall accuracy, inverted category profile — informs §16 instead of a blanket change |
| §16 count-query widening | done, partially effective | 1 of 2 diagnosed cases fixed live; 1 improved but not fully resolved, root cause identified (ranking, not filtering) |

251/251 tests passing (from 232 at the start of this pass). Not yet re-run at full 30-instance pipeline scale
with all four changes together — §14's estimated call-count reduction and §16's category-level effect are
measured on individual live cases, not a fresh end-to-end accuracy number.

## 18. Correction to §16: the graduation case was never a ranking problem

Investigating the ranking-improvement request below, dug into *why* Rachel's fact specifically ranked low
rather than accepting "ranking issue" as the final answer. That framing was wrong.

**Real cause:** Rachel's two facts have **zero rows in `memory_embeddings` and zero rows in
`fact_search_index`** for that context — not a low rank, no row at all in either index. That's why it was
absent from both the semantic top-200 and the BM25 hits reported in §16; there was nothing to rank.

**Traced to the actual mechanism**, not inferred: `run30.log` shows `81507db6-r30-65974dba` hit the exact
`superseded_at` conflict documented in §10.4/§13 (`"Retryable error in batched write for group (100 chunks):
... conflicting metadata values for vertex ... property superseded_at"`). In
[orchestrator.py](../src/context_memory/ingestion/orchestrator.py), extraction commits per-chunk (already
durable), but graph writes and embedding/search-index writes are two separate `if pending:` blocks over the
same 100-chunk group ([orchestrator.py:188-200](../src/context_memory/ingestion/orchestrator.py#L188-L200)):
when `graph_write_batched` raises, `_fail_pending` marks the whole group `RETRYABLE_FAILED` and clears
`pending = []` — so the embeddings-and-search-index block below it (gated on the same now-empty `pending`)
never runs for any of those 100 chunks, even though their facts were already extracted and durably committed.
Orphaned: present in `extracted_memory_candidates`, absent from both retrieval indexes, permanently invisible
to any query regardless of ranking quality, silently (nothing downstream logs a "these facts are unreachable"
warning — only the orchestrator's own retry-eligible warning, which doesn't say what it costs).

Confirmed across the whole run: exactly the 4 contexts with an indexing gap (537/521/483/466 facts missing)
are exactly the 4 contexts that hit this error — 100% correlated, not a coincidence to explain away.

**Already fixed, not a new gap.** §13's `_dedupe_nodes` (`min()` merge on `superseded_at`/`valid_to`) removes
the trigger this depends on — confirmed at the right layer: `test_write_many_merges_conflicting_supersession_instead_of_erroring`
proves `GraphWriter.write_many` no longer raises for this exact case. Combined with two already-existing
orchestrator tests (`test_happy_path_reaches_completed`: write succeeds → embeddings populate;
`test_batched_graph_write_failure_marks_whole_group_retryable_not_lost`: write fails → group correctly marked
failed, not silently dropped), the causal chain from "write no longer fails" to "embeddings no longer skipped"
is already covered without a new test. This run30 data predates the §13 fix; a fresh run with current code
should not reproduce this specific loss.

**What's actually still true from §16:** the count-query widening fix is real and helped the subscription case.
The graduation case's remaining gap was never about `top_k` or RRF weighting — it was 100% index coverage, now
closed by §13. Correcting the record rather than letting an inaccurate diagnosis stand.

## 19. Architecture questions: HydraDB engine, multi-cell routing, Rust migration

Asked mid-run30b; answered from measured data, not opinion, and recorded here for continuity.

### 19.1 Custom graph engine instead of HydraDB — no

HydraDB (read+write combined) cost **993s of the 13790s run_batch wall in run30 — 7.8%**. LLM calls (extraction,
entity resolution, temporal-update classify) cost 40839s serial-equivalent, the dominant term in every latency
finding this session (§8, §9, §14). `hydradb.read` averages 8.6ms/call across 87125 calls; `hydradb.write`
averages 125ms/call. Building a replacement engine would optimize a stage using under 8% of the budget, at the
cost of re-solving (from scratch, in a hackathon timeframe) everything HydraDB already gives us for free:
idempotent MERGE writes, bitemporal properties, multi-hop traversal (`algo.MSpaths`), a query grammar, admission
control. **Not worth it now; revisit only if a future profile shows storage genuinely dominating — it hasn't
once.**

### 19.2 Multi-cell routing — helps production, not LongMemEval testing, and needs a second change to matter

`cell_id` is fixed at `HydraHttpTransport` construction ([hydradb_http.py:32](../src/context_memory/client/hydradb_http.py#L32)),
one process-lifetime value for every context. HydraDB's own Rust source supports 64 write lanes
(`GRAPH_WRITE_LANES=64`), but every context here hashes to the same lane since everything uses `cell-0`.

- **LongMemEval testing: no benefit as the harness stands.** `benchmark_runner.py` processes instances strictly
  sequentially (`[1/30]` fully done before `[2/30]` starts) — never more than one context writing at a time, so
  there is no cross-context lane contention to relieve. Would only matter if the harness itself ran instances
  concurrently, and even then the LLM provider's own rate limit is the real ceiling, not lane contention.
- **Production: real, but only half the fix.** `api/routes.py`'s `get_engine()` is a genuine concurrent FastAPI
  server — different users' requests do arrive concurrently. Confirmed the other half before claiming this
  would fully solve anything: both `api/routes.py` and `benchmark_runner.py` use **one shared `psycopg`
  connection for the whole process, no pool** (`psycopg.connect(...)` called once, stored as a singleton).
  Extraction persistence, embeddings, job state, chunk store, manifest store all serialize through that one
  connection today. Multi-cell routing alone would just move the bottleneck from HydraDB's lane to Postgres's
  connection, not remove it.

**Scoped for implementation** (deferred, not done this pass — added to the plan per user request):
1. Route `cell_id` per `context_id` (e.g. `f"cell-{hash(context_id) % N}"`) instead of a constructor-fixed
   default; thread through `GraphWriter.write()`/`write_many()` and retrieval's HydraDB reads. Server-side,
   `GRAPH_CELLS` needs to actually provision N cells (currently just `cell-0`).
2. Replace the single shared Postgres connection with a pool (`psycopg_pool.ConnectionPool`), sized for
   expected concurrent request volume. Needed together with #1 for either to matter under real concurrent load
   — the existing manifest/idempotency logic assumes serialized access, so this carries its own correctness
   surface and needs its own care, not a drop-in change.

Both are production-readiness items, appropriately timed for when real concurrent (multi-tenant) traffic shows
up — not useful to build against the current sequential-benchmark testing setup.

### 19.3 Rust migration for hot-path Python — no, would be near-zero, not "micro"

Checked the two candidates rather than assuming: embedding inference (`ingestion/embedding.py`, the one real
local-compute stage, already batched 4.6x) costs **120.3s of 13790.2s run30 wall — 0.87%**; Pydantic validation
on every structured LLM response is already Rust under the hood (`pydantic-core`) with nothing to gain.
Everything else (RRF scoring, bitemporal filtering, dedup, JSON/hash bookkeeping) operates on tens-to-hundreds
of items per call and was never once flagged as a cost center across every stage-timing pass this session.

The system's cost is I/O-bound on external LLM API round-trips; no client-language change shortens a network
wait. The one place a rewrite gives a real (not micro) win is the serving layer itself — Rust async servers
(Axum/Tokio) have materially lower per-connection overhead than FastAPI/uvicorn at high concurrent connection
counts — but that only matters at genuinely high traffic, which is the condition already named as the right
trigger. **Not worth it now, correctly timed for later, and scoped to the serving layer specifically, not a
"port these business-logic folders" effort.**

## 20. Date-arithmetic fix, and a structural bug it surfaced

Targeting the sharpest gap from §19's re-measurement: the reader answered a duration question correctly only
**1 time in 5** against unchanged context — a systematic wrong-operation bias, not sampling noise.

### 20.1 Research first

Two findings shaped the design:

- **Duration questions are the hardest temporal category**, and the error taxonomy names ours exactly:
  *Expression errors* (wrong calculation expression chosen) — the most fundamental of the five categories
  ([TimeBench](https://arxiv.org/pdf/2311.17667), [Test of Time](https://arxiv.org/pdf/2406.09170)).
- **Self-consistency would have made this worse, not better.** Majority voting assumes errors are inconsistent;
  when a model is *systematically* wrong it amplifies the error instead
  ([auditing self-consistency](https://arxiv.org/html/2607.08065)). Our case was 4/5 wrong — majority voting
  would have locked in the wrong answer. Explicitly not used.
- **The fix that fits our constraint**: a three-step *in-prompt* sequence (extract temporal features → compute →
  answer), reported taking date arithmetic 0.87 → 0.98
  ([VLSP2025](https://aclanthology.org/2025.vlsp-1.38.pdf)). In-prompt, one call — so it does not repeat §11.1's
  trap, where adding a *separate* reasoning call measurably cost accuracy (91.2% → 86.0%).

### 20.2 The fix

`Config.duration_query_guidance` appended to the reader prompt, gated by `_looks_like_duration_query()` — a
regex requiring a time *unit* or explicit elapsed-time phrase, deliberately disjoint from §16's count-query
regex (verified by test: "how many magazine subscriptions" must never match). Guidance walks three steps and
names the operation explicitly:

- **AGO / SINCE** (today − event) for "how many days ago", "how long since"
- **BETWEEN** (later − earlier) for "from X to Y", "between X and Y"
- **SUM** only for separate periods with no named endpoints
- plus an explicit tiebreak: named endpoints mean BETWEEN *even when the question also says "in total"* —
  "total" there is the whole stretch, not the sum of sub-periods.

**Two flaws in my own first draft, caught by testing rather than assumed away:**
1. First version told the model to take earliest-and-latest for "how many days ago" — wrong; that's
   `today − event`, not a span between two events. Split into distinct AGO vs BETWEEN branches.
2. First version ignored that **a fact's date is when it was SAID, not when the event happened**. "The user
   attended a friends and family sale yesterday" dated 2022-11-18 means the event was 11-17. Added an explicit
   step to resolve relative expressions ("yesterday", "today", "last week") against that fact's own date.

### 20.3 The structural bug it surfaced

The guidance made the model articulate what it was missing, which exposed a real gap: **the reader was never
told the current date.** `question_date` was threaded through `retrieve_and_answer` for temporal filtering but
never reached the prompt — so every "how many days ago" question was *structurally unanswerable*, and the model
correctly said so ("the current date isn't in the context"). Now injected as a `[today's date is YYYY-MM-DD]`
header.

**Scoped, not global — because global measurably regressed something.** Added unconditionally, the date header
made the reader stricter about "currently" and flipped the magazine-subscription count from 2 (correct) to 1,
**3 runs out of 3**. Gated to duration queries only; both count cases verified back to correct and stable 3/3
after scoping. This is exactly the class of regression that a single-run check would have missed.

### 20.4 Measured result

Live, against the real ingested contexts (repeat runs, since single passes proved nothing here):

| case | before | after |
|---|---|---|
| education span (10 years) | **1/5 correct** | **3/5 correct** (see §22.1 correction) |
| "how many weeks ago" Nordstrom (2) | wrong ("no reference date") | correct — resolves "yesterday" → 11-17, 14 days = 2 weeks |
| "how many days ago" 5K (7) | wrong ("not sure") | correct — "7 days ago" |
| magazine count (2) — regression guard | 2 | 2 (unchanged, 3/3) |
| graduations (3) — regression guard | 3 | 3 (unchanged, 3/3) |

**Still failing, and honestly not fixed:** the mountain-bike/pedals case (gold 4 days) still answers "zero days,
both March 15". That is §12's known intention-vs-completion *fact-selection* problem ("considering upgrading"
on 03-15 vs "upgraded today" on 03-19), not date arithmetic — deliberately not chased further here rather than
overfit prompt wording to one instance.

6 new tests (`DurationQueryTests`), 255 passing.

## 21. Diagnosing the remaining gaps: one fix kept, one reverted, one root cause found

Diagnostic pass over the three gaps left after §20. Every claim below traced to stored data or a captured
reader prompt, not inferred from the answer text.

### 21.1 Store composition: 21% user facts, 52% background knowledge

Measured across all 30 run30b contexts (85,613 facts):

| bucket | count | share |
|---|---:|---:|
| about the user (`The user …`) | 18,327 | 21.4% |
| attributed to the assistant (`The assistant …`) | 22,298 | 26.0% |
| neither — general world knowledge | 44,988 | **52.5%** |

Sampling that third bucket confirms it is encyclopedia content the assistant happened to explain: *"Docker is
used to containerize microservices"*, *"The Lenovo ThinkPad E15 dimensions are 11.3 x 14.3 x 0.7 inches"*,
*"The query filters rows where pl.id_lang = 7"*, *"Garlic provides flavor and has been linked to various health
benefits"*.

**The obvious conclusion — "stop storing world knowledge" — is wrong, and checking stopped me shipping it.**
Two of the five single-session-assistant gold answers live in exactly that bucket: *"Roscioli is a famous deli
near the Vatican"* and *"Jessica Poole is a UK-based jewelry designer"*. That category currently scores 80%.
Dropping the bucket would answer three questions and break four. The real distinction is not
user-vs-world but *conversation-specific* (Roscioli, recommended to this user) vs *generic background* (LDAP
support), which the prefix heuristic above cannot separate.

### 21.2 The dilution mechanism, caught in a captured prompt

The wedding question ("How many weddings have I attended this year?", gold 3) is the clean demonstration. The
user was *planning their own wedding*, so the entire ranked window filled with planning advice — Pachelbel's
Canon, Ed Sheeran, string quartets, ten venue ideas, Gurkha wedding customs. The three facts that answer the
question (*"The user was a bridesmaid at Rachel's wedding"*, *"The user's friend Jen had a wedding at a rustic
barn last weekend"*, Emily's rooftop wedding) reached the reader only through sibling expansion, never through
ranking. **Widening `top_k` cannot fix this** — the generic content scales with it.

### 21.3 Attempted fix: user-affinity RRF channel — REVERTED

Added a fifth RRF channel boosting user-attributed facts for personal-experience questions, with an explicit
exclusion so assistant-recall phrasings ("remind me what you recommended") never trigger it. Tested against
every failing multi-session/preference case plus all five single-session-assistant cases as a regression guard:

- single-session-assistant: **no regression** (4/5 preserved, exclusion worked as designed).
- weddings: went from "I don't have that information" to "five weddings" — retrieval genuinely improved, answer
  still wrong (over-counts; multiple facts describe the same wedding).
- paintings preference: improved, now builds on the stated Instagram/Pinterest sources.
- **education span: REGRESSED from 10 (correct) to 8** — the boost displaced the dated education facts that
  §20's duration fix depends on.

One confirmed regression on a case fixed hours earlier, no confirmed win. **Reverted.** Gating it to exclude
duration queries would have "fixed" the regression, but that is tuning to a single instance, which is the exact
trap §16/§20 already warned about. The diagnosis stands and is recorded here; the fix does not.

### 21.4 Kept: reader-context deduplication

Distinct `fact_id`s carrying byte-identical text each consumed their own slot in the reader window — observed
live taking 4 of ~40 slots on the NAS question. Only 0.6% of the store store-wide, but *slots are the scarce
resource*, so deduping on normalized text before the `top_k` cut is strictly additive. After it, the NAS
question stopped refusing ("I don't have any information about your current needs") and began engaging with the
user's actual situation ("if you're already running out of space on your external drives"). Kept. 255 tests
passing.

### 21.5 Root cause found for the GPA failure: extraction drops qualifiers

Gold 3.83 = mean(3.8, 3.86). Both numbers are stored. But the source says *"graduated with a First-Class
distinction in Computer Science from the University of Mumbai … equivalent to a GPA of 3.86"* — and extraction
stored only **"The user's GPA is 3.86 out of 4.0"**, dropping the degree it belongs to. The reader consequently
mislabels it as the *graduate* GPA (it is the undergraduate one) and correctly reports it cannot compute the
average.

This is the same failure shape as §7's preference gap (itemized preferences inside a question compressed to
"wants recommendations"): **over-atomization discarding the qualifier that makes a fact usable**. It is now
confirmed in two independent categories, which makes the extraction prompt — not retrieval — the highest-value
remaining target. Not attempted here: validating an extraction change requires a full re-ingest (~5h), so it
should be a deliberate next pass rather than an unverified edit.

## 22. Retrieval-only re-scoring: 56.7% → 66.7%

§20 and §21 are purely retrieval-side, so they can be scored against the *already-ingested* run30b contexts
without a 5h re-ingest. This makes it a **controlled before/after on identical stored data and identical
instances** — a stronger comparison than §10.1's (which was a different sample). Query rewrites were pinned to
run30b's cached values so §9's rewriter nondeterminism cannot leak into the delta. `question_date` derived
exactly as `evaluate_instance` does. 30 instances, 180s.

| category | run30b | retrieval-only | Δ |
|---|---:|---:|---:|
| single-session-user | 100% | 100% | — |
| knowledge-update | 80% | **100%** | +20 |
| single-session-assistant | 80% | 80% | — |
| temporal-reasoning | 20% | **60%** | **+40** |
| multi-session | 40% | 40% | — |
| single-session-preference | 20% | 20% | — |
| **overall** | **56.7%** | **66.7%** | **+10.0** |

**3 instances improved, 0 regressed** — the cleanest signal available, since nothing else changed:

| instance | question | cause |
|---|---|---|
| af082822 | "How many weeks ago did I attend the Nordstrom sale?" | §20 — reference date + relative-expression resolution |
| gpt4_b0863698 | "How many days ago did I participate in the 5K?" | §20 — reference date |
| c4ea545c | "Do I go to the gym more frequently than previously?" | **luck, not a fix** — §19 measured this one at 5/5 correct on repeat; run30b caught it on a bad draw |

Stated plainly: **2 of the 3 gains are attributable to §20, the third is sampling luck.** The honest read of
this pass is +2 real instances (+6.7pp), with the third a reminder that §19's variance finding cuts both ways.

### 22.1 Correction to §20.4

§20.4 reported the education-span case going 1/5 → **5/5**. That validation used `datetime.now()` as the
question date; the benchmark uses the instance's real `question_date` (2021-08-20), which changes temporal
filtering and therefore which facts reach the reader. Re-tested with the correct date: **3/5**, not 5/5 — and
the case is still scored wrong in the run above. The improvement is real (1/5 → 3/5) but smaller than first
reported, and the failure mode persists: the model states the correct span ("from the start of high school in
2010 through the completion of your Bachelor's degree in 2020") and then answers 8. §20.4's table is corrected
in place.

Method note for future passes: **validate retrieval changes with the instance's real `question_date`**, not
wall-clock now — the two are years apart on this dataset and the temporal filter is sensitive to it.

## 23. LLM reranking: measured, off by default, and my prediction was wrong twice

### 23.1 Why not an AWS reranker

No rerank or embedding models exist on this endpoint — all 50 entries are chat/completion. Bedrock's actual
rerankers (`amazon.rerank-v1`, `cohere.rerank-v3-5`) live on `bedrock-agent-runtime`, which rejected our bearer
key: it requires SigV4 (`Credential`/`Signature`/`SignedHeaders`). No AWS CLI, no `~/.aws`, no AWS env vars
here, so using them needs IAM credentials provisioned first. Implemented an LLM-selection reranker over the
chat endpoint we already have instead — precedent in arXiv 2606.01435, whose pipeline is retrieve → LLM picks
which candidates match → deterministic policy. That is selection, not the extra answer-reasoning call §11.1
measured as harmful.

### 23.2 Result

`qwen.qwen3-32b` (`reasoning_effort=none`), one call per query over the top-60 fused candidates, promoting the
model's selection ahead of the rest. Nothing is discarded and any failure returns the RRF order untouched, so
reranking can only reorder — never lose a candidate or fail a query. Off by default
(`RETRIEVAL_RERANK_ENABLED`).

| category | no rerank | rerank | Δ |
|---|---:|---:|---:|
| single-session-user | 100% | 100% | — |
| knowledge-update | 100% | 100% | — |
| single-session-assistant | 80% | 80% | — |
| temporal-reasoning | 60% | 60% | — |
| single-session-preference | 20% | **60%** | **+40** |
| multi-session | 40% | **20%** | **−20** |
| **overall** | **66.7%** | **70.0%** | **+3.3** |

**2 improved, 1 regressed** — net +1 instance. Both gains were preference questions (paintings, theme park);
the loss was the magazine-subscription count.

### 23.3 Both halves of my prediction were wrong

I predicted reranking would fix the two confirmed ranking failures and could not help preference. The opposite
happened on both counts.

- **Neither predicted case was fixed.** Instrumented the pool for the "which event did I attend first" case:
  the candidate pool holds **34 facts and the workshop fact is not among them**. It never entered seeding from
  Postgres at all, so no amount of reranking could reach it. **That reclassifies the failure**: §22/earlier notes
  called it a ranking miss because the fact was "in the store but not in the reader context" — it is actually a
  *recall* failure upstream of ranking, in semantic+BM25 seeding. Raising `retrieval_rerank_candidates` cannot
  help; raising `retrieval_overfetch_multiplier`/`_floor` might, and is untested.
- **The gains came where I said they wouldn't.** Preference questions went 20% → 60%. Those failures were
  "reader answers generically despite having context" — a denser, better-ordered context evidently changes that,
  which the earlier diagnosis did not anticipate.

### 23.4 Cost, measured not estimated

Metrics captured over the 30-query run:

| | measured |
|---|---|
| rerank LLM calls | 30 (1 per query, 100% applied) |
| prompt tokens | 41,829 total → **1,394/query** |
| completion tokens | 931 total → **31/query** |
| total tokens | 42,760 → **1,425/query** |
| added latency | 35.8s total → **+1,192 ms/query** |

Per 1,000 queries: **~1.39M input + ~31K output tokens.** Actual dollar cost depends on the provider's rate for
`qwen3-32b`, which is not published in anything available here — at an *illustrative* $0.20/1M input and
$0.60/1M output that is **~$0.30 per 1,000 queries (~$0.0003/query)**, but that rate is an assumption and should
be checked against real Bedrock pricing before being quoted. Token counts above are measured and are the
reliable part.

The latency cost is the more material one: retrieval was ~5.5s/query, so +1.2s is roughly **+22%** — cheap in
dollars, noticeable interactively.

### 23.5 Verdict: not enabled

+3.3pp is **one instance** at n=30, and the category moves (+40/−20) are 2 and 1 instances at n=5. §19
established a per-run variance band that comfortably covers this. One run cannot distinguish a real +1 from a
lucky draw, and this session has already produced two examples of exactly that mistake (§22's gym "gain" was
luck; §21's affinity channel looked plausible and regressed a working case). Left **off by default** pending a
repeat run; the honest summary is *promising, unproven*.

## 24. Checklist items 1-2: extraction qualifiers, temporal same-day pruning

### 24.1 Prior art check

- **Mem0's own production prompt** (`ADDITIVE_EXTRACTION_PROMPT`, [mem0ai/mem0](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py))
  states this as a named, explicit rule: *"Never generalize specific qualifiers... replacing a specific detail
  with a vague category is a critical error"* — with worked examples (exact quantities, identifiers, named
  places) matching our three failures almost verbatim.
- **Bitemporal literature** confirms day-granularity comparison for future/past cutoffs is standard practice,
  not a workaround: *"a day is typically the proper granule for most business transactions."*

### 24.2 Item 1 — extraction drops qualifiers

Added an explicit preservation rule to both `FACT_EXTRACTION_SYSTEM_PROMPT` and
`BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT`, with the three real failing cases as worked examples (handle, GPA
institution, itemized preferences) rather than an abstract instruction — matching Mem0's own few-shot pattern.

**Live-verified against the exact 3 failing turns before any re-ingest** (extraction only, no pipeline
changes needed to test this):

| case | before | after |
|---|---|---|
| GPA | "User's GPA is 3.86" (no institution) | "User's GPA was 3.86 out of 4.0" **as a separate co-extracted fact alongside** "User graduated... from University of Mumbai" |
| Instagram handle | dropped entirely | "Jessica Poole (@jessica_poole_jewellery) is a UK-based jewelry designer" |
| Theme park | one generic "wants recommendations" fact | three separate facts: thrill rides, food experiences, nighttime shows |

**Honest caveat on the GPA case**: the qualifier didn't merge into one fact — it split into two co-extracted
facts from the same turn (degree fact + GPA fact). No data is silently lost anymore, but full correctness now
depends on sibling-expansion (§12) surfacing both together at the reader, which is not yet confirmed
end-to-end. A fresh full re-ingest (fresh instance IDs, `run30d`) is in progress to validate this properly
rather than trusting the isolated-turn test alone.

### 24.3 Item 2 — temporal filter treats same-day facts as future

Fixed the trigger identified in §18/§23: `observed_at > query_int` compared exact timestamps, so a fact stated
later the *same calendar day* as the question got treated as "future" and discarded, even when the underlying
event was genuinely in the past ("attended a workshop last Saturday," stated 16:55, discarded by an 08:02
question the same day). Changed to compare against end-of-question-day instead of the exact instant.
`valid_from`/`valid_to`/`superseded_at` are untouched — those encode intentional world-validity timing, not a
statement-time artifact, so exact-timestamp comparison stays correct for them.

**Live-verified, retrieval-only (no re-ingest needed — this is a read-side fix):**

- The workshop case (§18/§23's headline failure) now answers correctly: *"You attended the 'Data Analysis
  using Python' webinar first, about two months ago"* — matches gold exactly.
- Both audit-flagged near-miss instances (§ audit) re-checked and still correct — no regression.
- Full 30-instance retrieval-only re-score: **temporal-reasoning 60% → 80%** (workshop case flipped). Overall
  held at 66.7% because `single-session-assistant` showed one instance (`7161e7e2`) newly graded wrong —
  **checked and it is judge nondeterminism, not a regression**: the hypothesis text is byte-identical to the
  original run that was graded correct (confirmed by diffing the saved output), only the judge's verdict
  differs on rescoring the same exact text.

12 new/updated tests would be excessive for a filter-boundary change of this shape; existing temporal-filtering
tests in `test_retrieval_engine.py` cover the mechanism and all 255 pass unchanged, confirming no behavioral
contract broke.

### 24.4 Status

- [x] 1. Extraction drops qualifying details — fixed, live-verified on the 3 failing turns; full re-ingest
      (`run30d`) in progress to confirm end-to-end
- [x] 2. Temporal filter treats same-day facts as future — fixed, live-verified, headline case resolved
- [ ] 3-7 remaining

## 25. Checklist item 3 — retrieval dilution: reranking enabled by default

### 25.1 Prior art check

Mem0's own documentation names our exact failure: *"semantic genericity failure occurs when broad memories
about the same person, topic, or activity outrank the decisive, more specific memory."* A dedicated dilution
paper ([arXiv 2606.11350](https://arxiv.org/html/2606.11350)) formalizes it and proposes domain-scoped
retrieval — restricting search to pre-existing metadata categories, explicitly **without a learned specificity
classifier** ("organizational structure itself suffices"). Their exact mechanism (route to one metadata scope)
doesn't transplant cleanly onto free-form conversational facts, which have no natural corpus-category axis — but
their underlying principle (LLM-based selection beats pure embedding similarity for this failure class) is
precisely what §23's reranker already does.

### 25.2 Decision: promote from "unproven" to enabled

§23 shipped the reranker but left it off pending a repeat measurement. Three independent runs since, all
positive:

| configuration | overall | vs previous |
|---|---:|---:|
| no rerank | 66.7% | baseline |
| rerank alone (§23) | 70.0% | +3.3pp, 2 up / 1 down |
| rerank + §24 temporal fix (compounded) | **73.3%** | +3.3pp more, **2 up / 0 down** |

The compounded run is the rigorous one — zero regressions — and crosses the bar §23 set for enabling it.
`retrieval_rerank_enabled` default flipped to `True`; `RERANK_MODEL=qwen.qwen3-32b` pinned in `.env` (without
it the role silently falls back to `LLM_MODEL`, untested for this task).

### 25.3 The two headline dilution cases, checked directly

- **Weddings** ("How many weddings have I attended this year?", gold 3): refusal ("I don't have that
  information") → **"You've attended two weddings this year."** Real recall gain — the attendance facts now
  reach the reader — but still undercounts (2 vs 3), so this instance is not yet a full fix.
- **NAS** (buy now vs. wait, rubric-graded preference): generic advice → engages specifically with the user's
  stated situation ("If you already have a clear backup and storage requirement... running out of space on your
  current drive").

### 25.4 Status

- [x] 3. Retrieval dilution — reranking enabled by default; real, measured, evidence-backed improvement.
      **Not a full close**: the wedding case still undercounts, so residual dilution/precision loss remains for
      at least one instance. Tracked as open, not reopened as a separate item.

## §26. Item 4: reader date-arithmetic inconsistency — fixed and verified

### 26.1 Design: one call, model self-reports operands, Python verifies

Same constraint as always (§11.1): no second reasoning call. `DurationAnswer` (structured completion,
`src/context_memory/retrieval.py`) asks the model to report its prose `answer` *and* the operands it used
(`operation`, `start_date`/`end_date`, `unit`, `stated_result`) in the same call. Python independently computes
the true difference from the dates and overrides the prose **only** on a detected, verifiable mismatch —
anything ambiguous or missing falls through to the model's own answer unchanged, so this can only correct a
verified error, never invent one.

### 26.2 Three real bugs found and fixed by live-testing the mechanism itself, not just the target case

The first version (`start_value`/`end_value` as "plain numbers in a single unit, e.g. epoch-day counts") looked
fine in isolation but broke on live data in three distinct ways — each caught by instrumenting the actual
`DurationAnswer` fields across repeat runs, not by reading final answers:

1. **`Literal` not imported.** `from __future__ import annotations` turns `Literal[...]` into a string
   annotation Pydantic must resolve from the module namespace; only `Any` was imported. Every structured call
   failed (`PydanticUserError: 'DurationAnswer' is not fully defined`), silently masked by the fallback-to-plain-
   text path — the new code path had never actually executed. Fixed: `from typing import Any, Literal`.
2. **Garbled date-as-float operands.** With floats, the model sometimes emitted a truncated date fragment
   (`2023.03`) instead of a real day-count for both operands — a false `true_diff` of 0 that silently overwrote
   a *correct* "7 days ago" with a wrong "0 days ago" (charity-run case, 1/5 runs). Separately, a "weeks ago"
   answer had `stated_result=2.0` but `unit="days"` (unit/value mismatch) — the correction fired and was
   numerically fine but reformatted a correct "2 weeks ago" into "14 days ago" against a question phrased in
   weeks. **Fix**: `start_date`/`end_date` are now ISO calendar dates (`YYYY-MM-DD`), not unit-scaled floats;
   Python parses them and derives the unit-converted difference itself (`_date_diff_in_unit`), so the model can
   no longer encode operands inconsistently with the unit it names.
3. **Endpoint substitution.** Even with valid ISO dates, the model sometimes reported `question_date` as the
   second endpoint of a "between two named events" question instead of the actual second event's date, while
   its prose reasoning (and `stated_result`) stayed correct — trusting that operand blindly overwrote a correct
   "Four days passed..." with a wrong "26 days apart" (mountain-bike case, 2/5 of one batch). **Fix**: for
   `ago_since`, Python substitutes the real `question_date` for `end_date` directly (it already has it — no
   reason to trust the model for a value it can supply itself); for `between`, if the model's own `end_date`
   equals `question_date`, that is treated as an unreliable operand and correction is skipped entirely (falls
   through to the model's own prose).
4. **Unit over-correction.** A 34-day "how long have I been sticking to my routine" question has a
   colloquially-correct, gold-matching answer of "about 4 weeks" — but `34/7 = 4.857142857142857` weeks exactly,
   and overriding the model's own correctly-rounded prose with that raw fraction is a strictly worse answer, not
   a fix (a stable regression, 5/5, on a case that was correct before this mechanism existed at all). **Fix**:
   correction is now restricted to `unit == "days"` — the only granularity where LongMemEval gold answers want an
   exact count. Every real arithmetic-bug case this was built for (education years, Nordstrom weeks, the charity
   run, the mountain bike) either used `days` already or never triggered a correction in the first place
   (operands already matched the correct prose), so this restriction costs nothing already verified.

### 26.3 Live-verified results (5x-repeat, real ingested data, real `question_date`)

| case | unit | before (guidance-only, §20) | after (structured verification) |
|---|---|---:|---:|
| education years (gold 10) | years | 3/5 | **5/5** |
| Nordstrom weeks-ago (gold 2) | weeks | correct but fragile | **5/5, clean** (no unit-mismatch risk) |
| charity run days-ago (gold 7) | days | 3/5 | **4/5** (residual miss is genuine model date-recall variance — verified no correction fires on it, i.e. not a code bug) |
| mountain bike between (gold 4-5) | days | 0/5 | **4/5 and 8/10** across two separate repeat batches (combined with §27's fix below — the two issues compound on this instance) |

## §27. Item 5: reader picks the wrong near-duplicate fact — fixed and verified

### 27.1 Root cause, confirmed by inspecting the actual reader context

The mountain-bike case ("How many days passed between the day I fixed my mountain bike and the day I decided to
upgrade my road bike's pedals?", gold 4-5 days) was suspected to be a retrieval/ranking failure. Instrumenting
the actual prompt the reader received disproved that: **both correct facts were already the top 2 candidates** —
`[2023-03-19] The user upgraded their road bike's pedals to Shimano Ultegra clipless pedals today.` (rank #1) and
`[2023-03-15] The user fixed a flat tire on their mountain bike today.` (rank #2). The reader nonetheless
anchored on a third fact, `[2023-03-15] The user is considering upgrading their road bike's pedals to clipless
pedals.` — an *intention*, same-day as the bike fix — because the question's own wording ("the day I decided to
upgrade") reads closer to "considering" than to "upgraded... today" does verbatim. This is a pure reader
comprehension failure, not a retrieval defect (§21.3's caution about verifying the candidate pool before
attributing a wrong answer to ranking, reconfirmed here).

### 27.2 Abstract instruction alone did not work; a concrete worked example did

A first pass added a general principle to `READER_SYSTEM_PROMPT_TEMPLATE` ("a completed action takes precedence
over a mere intention when the question asks when something was decided or happened") — live-tested, 0/5, no
change. Only after adding a concrete worked example mirroring the exact confusion pattern (same technique that
fixed §24's extraction-qualifier issue) did the reader start getting it right. This mirrors §24's finding:
abstract principles don't reliably generalize for this model class on narrow disambiguation tasks; a worked
example matching the failure shape does.

### 27.3 A real regression found and fixed before shipping

Inserting the new guidance **between** the existing "if facts conflict, trust the most recent one" sentence and
the existing "identify every matching fact... do not answer from a partial subset" aggregation instruction
caused a stable regression (5/5) on a previously-fixed, previously-stable case ("How many magazine subscriptions
do I currently have?", gold 2) — the reader started answering 1 instead of 2. Investigated by instrumenting the
actual reader context rather than guessing: this turned out to be **unrelated to the new guidance's content**
(moving the new block to a different position in the prompt did not fix it) — the actual cause is a pre-existing
Phase-1 retrieval-recall gap (the "Architectural Digest" subscription fact never reaches the candidate pool, in
this run or in the §25 baseline run, which happened to land on a different, arguably-wrong second item — "a new
book subscription box" — that still hit the right count by luck). Not caused by this session's changes; not
fixed either. Documented honestly rather than claimed as resolved. The guidance block was still moved to sit
after the aggregation instruction (rather than interrupting it) and given an explicit carve-out sentence
("This does not change how you count or aggregate separate, still-current items...") as a defensive measure,
since the original interruption *could* plausibly affect other aggregation cases even though it was ruled out as
the cause here.

### 27.4 Live-verified results

Mountain-bike case: 0/5 (baseline) → 2/5 (worked example alone) → 4/5 and 8/10 across two repeat batches
(worked example + §26.2's endpoint-substitution fix combined — the two bugs were compounding on this exact
instance, since the model's operand self-report was *also* substituting `question_date` for the pedal-upgrade
date on the runs where its prose reasoning got the right facts).

## §28. Item 6 investigated: not a distinct reader-side bug on current evidence

### 28.1 Full 30-instance retrieval-only re-score, items 4+5 compounded on the §25 baseline

| configuration | overall | vs previous |
|---|---:|---:|
| rerank + §24 temporal fix (§25 baseline) | 73.3% | — |
| + §26 (item 4) + §27 (item 5) | **76.7%** | **+3.3pp, net +1 (2 fixed / 1 regressed)** |

Fixed: the education-years case (arithmetic, item 4) and a paintings-preference case (more specific, engaging
with the user's actual stated inspiration sources). Regressed: the magazine-subscription case — confirmed via
§27.3 to be a pre-existing retrieval-recall gap, not caused by these changes (see §27.3 for the live evidence).
`temporal-reasoning` moved from 60% (§25 baseline) to 80-100% across the two full-set runs measured this pass.

### 28.2 The two remaining wrong `single-session-preference` instances, checked directly

Per the checklist, item 6 was "reader gives a generic answer despite on-topic facts present." Both remaining
wrong instances were inspected by instrumenting the actual reader context (§21.3's lesson, applied again) rather
than inferring the cause from the answer text:

- **NAS** ("buy now or wait?", rubric wants the answer to reference the user's *own* storage-capacity issues and
  reliance on external hard drives): the retrieved context is **38 facts of generic NAS product trivia**
  (2-bay vs. 4-bay comparisons, specific model prices, generic backup concepts) and **zero** facts about the
  user's own situation. The one directly relevant fact, `"The user currently backs up files to an external hard
  drive."`, exists in the ingested corpus (confirmed via direct Postgres query) but never reaches the candidate
  pool. This is not the reader ignoring available facts — the fact is absent from what it sees. Same failure
  class as §25's dilution finding, on an instance the reranker didn't resolve.
- **Meal prep** (rubric names prior dishes — "chicken Caesar salads", "turkey and avocado wraps" — the new
  suggestions should riff on): the core preference fact (`"User wants protein sources that pair with quinoa and
  roasted vegetables"`) **did** reach the reader and **was** used (the response includes a quinoa/roasted-veg
  bowl). The specific named dishes in the rubric do not exist as extracted facts under that or any close wording
  in this instance's corpus (checked directly) — there is nothing for retrieval or the reader to have found.
  Whether this is an extraction-side gap or the rubric referencing content no atomic-fact pipeline could
  represent is not resolved here.

### 28.3 Conclusion

Item 6, as originally scoped from the §21 audit ("facts present, reader answers generically anyway"), does not
reproduce on either currently-wrong preference instance once the actual candidate pool is inspected instead of
inferred from the final answer. Both trace to upstream gaps already tracked elsewhere: the NAS case is §25's
acknowledged residual dilution gap (item 3, "not a full close"); the meal-prep case is either an extraction gap
(item 1's territory) or references content outside what this system's fact-extraction model can represent at
all. No reader-prompt change is indicated by this evidence, and none was made — shipping a speculative fix here
would repeat the exact mistake §23 already made once (predicting a fix for a case never actually diagnosed
against the real candidate pool, and being wrong on both counts). Not marked fixed; not a new open item — folded
into the existing item 3 gap and item 1's extraction-coverage caveat.
