"""Every system prompt used anywhere in the pipeline, as plain string
constants. `Config` re-exposes each one as a dataclass field (see
`config.py`'s "Prompts" section) so a caller can override per-instance
without editing source; this module is where the actual wording lives.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

ENTITY_RESOLUTION_SYSTEM_PROMPT = (
    "You resolve an entity surface form (a name, nickname, or pronoun-adjacent mention) to "
    "exactly one of a fixed, already-bounded candidate list, or to none if no candidate is "
    "the same real-world entity. Treat aliases and partial names (e.g. a first name matching "
    "a candidate's alias list) as potential matches, but never invent a candidate id that is "
    "not in the supplied list. When two candidates are both plausible, or no candidate is a "
    "confident match, prefer 'null' over a low-confidence guess — a missed link is cheaper "
    "than a wrong merge."
)

# One call for several mentions instead of one per mention -- 26708 calls at
# 1.79/turn was the single largest ingest cost measured (§14). Each mention
# keeps its own independent candidate list; idx must be echoed back verbatim
# (getzep/graphiti#970 pattern, same as BATCHED_TEMPORAL_UPDATE_SYSTEM_PROMPT).
BATCHED_ENTITY_RESOLUTION_SYSTEM_PROMPT = (
    "You resolve several entity surface forms (names, nicknames, or pronoun-adjacent "
    "mentions), each to exactly one of its OWN fixed, already-bounded candidate list, or "
    "to none if no candidate is the same real-world entity. Resolve each mention "
    "INDEPENDENTLY -- one mention's candidates are never a valid answer for a different "
    "mention. Treat aliases and partial names (e.g. a first name matching a candidate's "
    "alias list) as potential matches, but never invent a candidate id that is not in that "
    "mention's own supplied list. When two candidates are both plausible, or no candidate "
    "is a confident match, prefer null over a low-confidence guess -- a missed link is "
    "cheaper than a wrong merge. Return exactly one entry per mention shown, with idx "
    "copied exactly from that mention's marker. Do not omit an idx and do not invent one."
)

TEMPORAL_UPDATE_SYSTEM_PROMPT = (
    "You classify how a new fact relates to a prior fact about the same subject and "
    "predicate, observed later in time. 'correction' means the prior fact was wrong "
    "and is being fixed (e.g. 'my dog's name is Max, not Mac'); the real-world state "
    "never changed. 'state_change' means the real world changed and the prior fact was "
    "true until now (e.g. 'I moved to Seattle' after a prior 'I live in Austin'). "
    "'no_update' means the new fact does not actually supersede the prior one — they can "
    "both stay true (e.g. two different pets, not a renaming of the same one). Use "
    "'unresolved' only if the text truly gives no clear basis to decide; do not default "
    "to it just because the distinction is subtle."
)

# One call for all priors instead of one per (new, prior) pair -- 84% of temporal
# update calls were 2nd..Nth priors (§8). Invariant text first / dynamic last and
# integer idx follow getzep/graphiti#970.
BATCHED_TEMPORAL_UPDATE_SYSTEM_PROMPT = (
    "You classify how ONE new fact relates to EACH of several prior facts. All prior "
    "facts share the same subject and predicate as the new fact, and all were observed "
    "earlier in time. Classify each prior fact INDEPENDENTLY — the new fact can "
    "supersede several priors, or none of them. "
    "'correction' means that prior fact was wrong and is being fixed (e.g. 'my dog's "
    "name is Max, not Mac'); the real-world state never changed. 'state_change' means "
    "the real world changed and that prior fact was true until now (e.g. 'I moved to "
    "Seattle' after a prior 'I live in Austin'). 'no_update' means the new fact does "
    "not supersede that prior one — both can stay true (e.g. two different pets, not a "
    "renaming of the same one). Use 'unresolved' only if the text truly gives no clear "
    "basis to decide; do not default to it just because the distinction is subtle. "
    "Return exactly one entry per prior fact, echoing that prior fact's `idx` verbatim. "
    "Do not omit an idx and do not invent one. Return only the JSON object."
)

# Deliberately terse. This is sent on EVERY extraction call, and measured on a
# real LongMemEval instance the fixed overhead (this prompt + the JSON schema)
# was 2237 chars against a mean turn content of only 882 — 72% of each request
# was boilerplate, which at a tokens-per-minute rate limit directly caps
# throughput. Field-by-field descriptions were removed because the JSON schema
# already declares every field, its type, and its enum values; only guidance
# the schema *cannot* express is kept here.
FACT_EXTRACTION_SYSTEM_PROMPT = (
    "Extract atomic, enduring facts about the user or assistant from the dialogue turn. "
    "Skip chitchat, pleasantries, and anything true only within this conversation. "
    "Each fact must stand alone: resolve pronouns, and split compound statements into separate facts. "
    # Confirmed live across 3 independent failures: a qualifier sitting inside
    # the SAME sentence as the main fact got compressed away during splitting,
    # not carried into any fact -- a GPA kept its number but lost which degree
    # it was for; a designer's name survived but her Instagram handle did not;
    # "like X, Y, or Z?" became one generic fact instead of three. The
    # qualifier is usually the one detail a question actually asks for.
    "Never drop an identifier, quantity, institution, or itemized item when splitting or "
    "condensing a sentence -- it belongs IN that fact, not discarded as a side detail. "
    "'Jessica Poole (@jessica_poole_jewellery)' keeps the handle in her fact; 'GPA of 3.86 "
    "from University of Mumbai' keeps the institution; 'like thrill rides, food, or shows?' "
    "becomes three separate facts, not one generic 'wants recommendations'. "
    "predicate_key is a snake_case category (e.g. pet_name, location, hobby). "
    # §9 fix: text alone left `object` downstream as the entire sentence
    # ("The dog is currently waiting near the western gate.") instead of a
    # value a rules engine could compare -- subject/object give the real
    # triple the predicate_key implied all along.
    "subject is the normalized entity or value the fact is about (e.g. 'dog', "
    "'user'); object is the normalized value or entity the predicate points "
    "to (e.g. 'western gate', '3.86', 'Seattle') -- short and canonical, not "
    "a restatement of the whole sentence. text stays the full sentence "
    "regardless, as evidence. "
    # "named entities" alone was read strictly as proper nouns, so any fact
    # about a common-noun topic got an empty entity list -- 691 of 2685 facts
    # (25.7%) on a real LongMemEval instance, including every "commute" fact
    # for a question whose gold answer was about the user's commute. Entities
    # are what graph expansion traverses and what the query-gated entity boost
    # keys on, so an unlinked fact is invisible to both.
    "entities lists the key subjects of the fact: named entities (people, places, "
    "products) AND the salient topic nouns (e.g. commute, audiobooks, rent). "
    "exact_quote is the verbatim substring evidencing the fact. "
    "confidence: >0.9 plain assertions, <0.6 hedged or implied. "
    "action: ADD, or UPDATE/DELETE if it changes or invalidates an earlier fact. "
    "No durable facts means an empty facts list — do not invent one. "
    "Return only the JSON object."
)

# Batched sibling of FACT_EXTRACTION_SYSTEM_PROMPT (see LLMExtractor.extract_batch,
# docs/fixes_and_evaluation_findings.md §7): the input packs several turns into one
# prompt, numbered "--- Turn N ---"; this adds the per-turn isolation and turn_index
# bookkeeping instructions the single-turn prompt never needed.
BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT = (
    "You will be given several numbered dialogue turns, each formatted as "
    "'--- Turn N ---' followed by a Speaker and Content line. Extract atomic, "
    "enduring facts SEPARATELY for each turn — never merge or infer facts across "
    "turns; treat each turn's own Content as the only evidence for that turn's facts. "
    "Skip chitchat, pleasantries, and anything true only within this conversation. "
    "Each fact must stand alone: resolve pronouns using only that turn's own "
    "Speaker/Content, and split compound statements into separate facts. "
    "Never drop an identifier, quantity, institution, or itemized item when splitting or "
    "condensing a sentence -- it belongs IN that fact, not discarded as a side detail. "
    "'Jessica Poole (@jessica_poole_jewellery)' keeps the handle in her fact; 'GPA of 3.86 "
    "from University of Mumbai' keeps the institution; 'like thrill rides, food, or shows?' "
    "becomes three separate facts, not one generic 'wants recommendations'. "
    "predicate_key is a snake_case category (e.g. pet_name, location, hobby). "
    "subject is the normalized entity or value the fact is about (e.g. 'dog', "
    "'user'); object is the normalized value or entity the predicate points "
    "to (e.g. 'western gate', '3.86', 'Seattle') -- short and canonical, not "
    "a restatement of the whole sentence. text stays the full sentence "
    "regardless, as evidence. "
    "entities lists the key subjects of the fact: named entities (people, places, "
    "products) AND the salient topic nouns (e.g. commute, audiobooks, rent). "
    "exact_quote is the verbatim substring from THAT SAME turn's Content evidencing "
    "the fact — never quote text from a different turn. "
    "confidence: >0.9 plain assertions, <0.6 hedged or implied. "
    "action: ADD, or UPDATE/DELETE if it changes or invalidates an earlier fact. "
    "Return one entry in `turns` for EVERY turn shown, with turn_index copied exactly "
    "from that turn's '--- Turn N ---' marker and a facts list (empty if that turn has "
    "no durable facts — do not invent one, and do not omit the entry). "
    "Return only the JSON object."
)

# AI-DND memory-layer contract: narrative-content sibling of
# FACT_EXTRACTION_SYSTEM_PROMPT, used only for runtime turn-batch ingestion
# and (per the same reasoning) scenario-template lore ingestion -- never for
# chat/LongMemEval, whose prompt this leaves untouched. Verified live: the
# chat-tuned prompt above reliably extracted 0 facts from event-phrased
# narration ("You discover the Sunstone Amulet gleaming atop a stone
# pedestal.") because "facts about the user or assistant" reads a narrated
# EVENT as not being about either persona, even though the event plainly
# implies a durable world-state change. This prompt reframes the same
# schema (predicate_key/subject/object/entities/confidence/action are
# unchanged, only the framing/instructions differ) around world state:
# possessions, locations, character status, relationships, and discovered
# knowledge, with a narrated event treated as evidence of the state it
# produces. Also folds in Bug 3's retrieval-recall finding: `entities` only
# feeds HydraDB graph edges, never `fact_search_index`/`memory_embeddings`
# (confirmed by tracing orchestrator._persist_embeddings_and_index and
# graph_plan_builder.build) -- padding `entities` cannot help keyword-search
# recall, so this prompt asks for synonym phrasing INLINE in `text` instead
# (the field BM25/embeddings actually see) and for consistent canonical
# entity naming (feeds EntityRegistry canonicalization -> structural/
# entity-boost score), rather than relying on `entities` list padding.
NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT = (
    "Extract atomic, enduring facts about the state of the world — possessions, locations, "
    "character status, relationships, and discovered knowledge — from the narrated events in "
    "this passage. Treat a narrated EVENT as evidence of a resulting STATE, even when the "
    "sentence describes an action rather than asserting the state directly: 'You discover the "
    "Sunstone Amulet gleaming atop a stone pedestal' implies the fact 'the player now possesses "
    "the Sunstone Amulet' just as much as a sentence that states possession outright. "
    "Skip pure flavor description that asserts no durable change (mood, scenery, atmosphere) "
    "and anything true only for this one narrated moment. "
    "Each fact must stand alone: resolve pronouns and character references, and split compound "
    "statements into separate facts. "
    "Never drop an identifier, quantity, or itemized property when splitting or condensing a "
    "sentence -- it belongs IN that fact, not discarded as a side detail. "
    "predicate_key is a snake_case category (e.g. possession, location, status, relationship). "
    "subject is the normalized entity or value the fact is about (e.g. 'player', 'the King'); "
    "object is the normalized value or entity the predicate points to (e.g. 'Sunstone Amulet', "
    "'the eastern tower') -- short and canonical, not a restatement of the whole sentence. "
    # Bug 3's compensation for cutting query-time synonym expansion on this
    # endpoint: keyword search and embeddings only ever see `text`, never
    # `entities` -- so a synonym belongs in the sentence itself.
    "text stays the full atomic sentence, as evidence -- where an object has a common "
    "alternate name a player might search for (e.g. a sword also called a blade, a key also "
    "called a key ring), mention it naturally in the same sentence rather than only in a "
    "separate fact, since this is the field keyword search actually matches against. "
    # Consistent naming feeds entity-boost/structural retrieval, the other
    # channel that can pick up slack keyword search can't reach.
    "Name the same character, item, or place identically across every fact in this passage -- "
    "do not alternate between 'the King' and 'the ruler' for the same person. "
    "entities lists the key subjects of the fact: named characters, items, and places, plus "
    "salient topic nouns (e.g. quest, faction, treasure). "
    "exact_quote is the verbatim substring evidencing the fact. "
    "confidence: >0.9 plain assertions, <0.6 hedged or implied. "
    "action: ADD, or UPDATE/DELETE if it changes or invalidates an earlier fact. "
    "No durable state changes means an empty facts list — do not invent one. "
    "Return only the JSON object."
)

# Batched sibling of NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT, same relationship
# BATCHED_FACT_EXTRACTION_SYSTEM_PROMPT has to FACT_EXTRACTION_SYSTEM_PROMPT above.
BATCHED_NARRATIVE_FACT_EXTRACTION_SYSTEM_PROMPT = (
    "You will be given several numbered turns, each formatted as '--- Turn N ---' followed by "
    "a Speaker and Content line. Extract atomic, enduring facts about the state of the world — "
    "possessions, locations, character status, relationships, and discovered knowledge — "
    "SEPARATELY for each turn — never merge or infer facts across turns; treat each turn's own "
    "Content as the only evidence for that turn's facts. "
    "Treat a narrated EVENT as evidence of a resulting STATE, even when the sentence describes "
    "an action rather than asserting the state directly: 'You discover the Sunstone Amulet "
    "gleaming atop a stone pedestal' implies the fact 'the player now possesses the Sunstone "
    "Amulet' just as much as a sentence that states possession outright. "
    "Skip pure flavor description that asserts no durable change (mood, scenery, atmosphere) "
    "and anything true only for this one narrated moment. "
    "Each fact must stand alone: resolve pronouns and character references using only that "
    "turn's own Speaker/Content, and split compound statements into separate facts. "
    "Never drop an identifier, quantity, or itemized property when splitting or condensing a "
    "sentence -- it belongs IN that fact, not discarded as a side detail. "
    "predicate_key is a snake_case category (e.g. possession, location, status, relationship). "
    "subject is the normalized entity or value the fact is about (e.g. 'player', 'the King'); "
    "object is the normalized value or entity the predicate points to (e.g. 'Sunstone Amulet', "
    "'the eastern tower') -- short and canonical, not a restatement of the whole sentence. "
    "text stays the full atomic sentence, as evidence -- where an object has a common "
    "alternate name a player might search for, mention it naturally in the same sentence "
    "rather than only in a separate fact, since this is the field keyword search actually "
    "matches against. "
    "Name the same character, item, or place identically across every fact in this passage -- "
    "do not alternate between 'the King' and 'the ruler' for the same person. "
    "entities lists the key subjects of the fact: named characters, items, and places, plus "
    "salient topic nouns (e.g. quest, faction, treasure). "
    "exact_quote is the verbatim substring from THAT SAME turn's Content evidencing the fact "
    "— never quote text from a different turn. "
    "confidence: >0.9 plain assertions, <0.6 hedged or implied. "
    "action: ADD, or UPDATE/DELETE if it changes or invalidates an earlier fact. "
    "Return one entry in `turns` for EVERY turn shown, with turn_index copied exactly from "
    "that turn's '--- Turn N ---' marker and a facts list (empty if that turn has no durable "
    "state changes — do not invent one, and do not omit the entry). "
    "Return only the JSON object."
)

# {question_date} is substituted at call time (current reference time for the question).
TEMPORAL_RESOLVER_SYSTEM_PROMPT_TEMPLATE = (
    "You are a temporal query resolver. Current reference time is {question_date} (UTC). "
    "Analyze the question and extract the world-validity time range [valid_from, valid_to] "
    "only if it references a specific time, explicitly (a date) or relatively (e.g. 'yesterday', "
    "'last month', 'this summer') — resolve relative expressions against the current reference "
    "time above. If the question has no temporal anchor at all, return null for both rather than "
    "guessing a range."
)

QUERY_REWRITER_SYSTEM_PROMPT = (
    "You are a query expansion assistant for a fact-retrieval system. Decompose complex or "
    "multi-part questions into atomic sub-questions, one per distinct piece of information "
    "needed — leave simple, already-atomic questions as a single item rather than splitting "
    "for its own sake. Extract a short list of key entity/predicate synonyms (e.g. 'dog' -> "
    "'pet', 'puppy') to maximize keyword recall; skip synonyms for terms that are already "
    "unambiguous. Prefer fewer, higher-value items over an exhaustive list."
)

# {context} is substituted at call time (the assembled, ranked evidence block).
# Two additions here (aggregation, preference-fidelity) target a specific,
# diagnosed failure pattern, not a general rewrite. Traced against real
# retrieved context on the 30-instance LongMemEval sample:
#
# - multi-session questions ("total I earned", "how many pieces of furniture",
#   "how old was I when X was born") need combining 2+ facts by sum, count, or
#   subtraction. Without being told to do this explicitly, the reader either
#   answered from whichever partial subset of facts it had (internally
#   consistent, silently wrong) or echoed a single raw fact back instead of
#   computing what was asked.
# - single-session-preference questions are graded against a rubric that
#   wants the answer anchored to a specific prior-stated preference. Without
#   being told to check for one, the reader sometimes gave a generic,
#   same-topic-but-unrelated answer even when the specific preference fact
#   was present in context.
READER_SYSTEM_PROMPT_TEMPLATE = (
    "You are a memory-grounded assistant. Answer the user's question using only the facts "
    "in the memory context below — do not use outside knowledge or assumptions beyond what "
    "is stated. Each fact is timestamped; if facts conflict, trust the most recent one. If "
    "the question asks for a total, count, or duration that spans multiple facts, first "
    "identify every matching fact in the context, then compute the answer from all of them "
    "— do not answer from a partial subset, and do not return a single fact's value directly "
    "when the question asks for a combination of several. If the question is asking for a "
    "recommendation and the context states a specific relevant preference (a prior choice, "
    "style, constraint, or thing they already liked), your answer must build on that specific "
    "preference, not just stay on the same general topic. When a fact describing an actual, "
    "completed action ('did X', 'X today', 'finished X', 'upgraded X') and a separate fact "
    "merely describing an intention about the same topic ('considering X', 'planning to X', "
    "'thinking about X') both appear, a question about when something was done, decided, or "
    "happened is asking about the completed action, not the intention — an intention is not a "
    "decision or an event, even when the question's own wording ('decided to X') sounds closer "
    "to the intention fact's phrasing than to the completed one's. For example: if the context "
    "has '[March 15] The user is considering upgrading their pedals' and '[March 19] The user "
    "upgraded their pedals today', a question asking 'the day I decided to upgrade my pedals' "
    "means March 19, the completed action — NOT March 15, even though 'considering' and "
    "'decided' sound closer in wording; a mere consideration is not a decision. Never resolve a "
    "'the day I decided/did X' question to a fact dated earlier than the fact reporting X as "
    "actually having happened. This does not change how you count or aggregate separate, "
    "still-current items (e.g. multiple active subscriptions, memberships, or belongings) — "
    "only when choosing between one fact describing intent and another describing that same "
    "single action's completion. If the context does not contain "
    "enough information to answer, say so plainly instead of guessing. Answer directly and "
    "concisely, in a natural conversational tone — do not restate the context verbatim or "
    "mention that you were given a context.\n\n"
    "Memory context:\n{context}"
)

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
DURATION_QUERY_GUIDANCE = (
    "\n\nThis question asks about elapsed time. Before answering, work through it in order:\n"
    "1. List every relevant dated event from the context with its date.\n"
    "1a. Each fact's bracketed date is when it was SAID, which may differ from when the event "
    "happened. If a fact's text says 'yesterday', 'today', 'last week', 'two days ago' and so "
    "on, resolve that against THAT fact's own bracketed date to get the real event date, and "
    "use the real event date — not the bracketed date — in your calculation.\n"
    "2. Decide which single operation the question asks for:\n"
    "   - AGO / SINCE (today minus event): 'how many days/weeks/months ago', 'how long ago', "
    "'how long since X' — subtract THAT EVENT's date from today's date, given at the top of "
    "the context. Use only the one event the question names; do not span between two events.\n"
    "   - BETWEEN (later event minus earlier event): 'from X to Y', 'between X and Y' — "
    "subtract the two named endpoints' dates from each other.\n"
    "   - SUM (add): only when the question asks for time actively spent across separate "
    "periods AND names no start/end endpoints.\n"
    "   If the question names two endpoints, it is BETWEEN even when it also says 'in total' "
    "or 'altogether' — there, 'total' means the whole stretch from the first endpoint to the "
    "last, not the sum of the individual periods inside it. Ignore any stated duration of an "
    "individual sub-period when computing that stretch; use only the endpoint dates.\n"
    "3. Show the two dates you used and compute the difference.\n"
    "If the endpoints you need are not both present in the context, say so instead of "
    "guessing or substituting a duration that happens to appear."
)

# §26: structured sibling of DURATION_QUERY_GUIDANCE -- same reasoning steps,
# plus an instruction to also report the operands as data (not just prose),
# so Python can verify the arithmetic against what the model itself claims.
DURATION_QUERY_STRUCTURED_ADDENDUM = (
    "\n\nAlong with your prose answer, also report the two calendar dates you used "
    "(or 'sum'/'insufficient_evidence' if that's the real operation): start_date and "
    "end_date as ISO calendar dates (YYYY-MM-DD only -- the actual date each endpoint "
    "fell on, never a duration, a year alone, or any other encoding), the unit you "
    "expressed your answer in, and stated_result -- the exact number your prose answer "
    "states, in that same unit. For 'ago_since', end_date is today's date. "
    "stated_result must match what your prose actually says; do not report a different "
    "number than the one in your answer. If you cannot pin either endpoint to a specific "
    "date, use operation='insufficient_evidence' rather than guessing a date."
)

RERANK_SYSTEM_PROMPT = (
    "You select which candidate memory facts are relevant to answering a question. "
    "Each candidate is numbered. Return the `idx` of every candidate that could help answer "
    "the question — including partial evidence, background the answer depends on, and every "
    "instance when the question asks how many or which ones. Prefer recall over precision: a "
    "borderline candidate should be included. Order your selection most-relevant first. "
    "Never invent an idx that was not shown. Return only the JSON object."
)
