"""String-similarity candidate blocking for entity resolution.

Two signals are actually wired into `EntityRegistry._generate_shortlist`:
`ingestion.entity_name_index.EntityNameIndex` (cosine similarity over sentence
embeddings) and `NICKNAME_GROUPS` below (curated formal-name/nickname
equivalence, exact lookup). `char_trigram_jaccard_similarity`/
`find_fuzzy_candidates` are NOT wired in -- built, calibrated, and kept
here (tested, importable), but disabled at the call site. Measured live
against a real 100-turn LongMemEval instance (docs/fixes_and_evaluation_
findings.md §4.7): trigram blocking accounted for 427 of 431 blocking
events (99.1%) -- and checking it against this module's own calibration
set below found it doesn't uniquely catch anything either of the other two
signals miss. What it *was* catching, on real content, was near-noise:
generic single/multi-word topic nouns ("trust", "news", "misinformation",
"reliable sources") sharing incidental character overlap, not names at
all -- entity_type is currently uniform ("other") for every extracted
entity regardless of whether it's a person's name or an abstract topic
noun, so there was no cheap way to gate trigram matching to only the
surfaces it was designed for. Kept as a real, tested capability for
whenever entity-type-aware gating exists to make it safe to re-enable, not
deleted.

Calibrated against real name pairs before picking constants (not guessed) --
still accurate for the trigram *function*, even though it's not called from
`_generate_shortlist` today:

    'dave' vs 'david':            0.300   (true positive -- but also
                                            covered by NICKNAME_GROUPS)
    'sherlock holmes' vs 'holmes': 0.389   (true positive -- but also
                                            covered by embedding similarity
                                            alone, verified live: 0.82-0.90,
                                            comfortably above threshold)
    'sherlock holmes' vs 'sherlock': 0.500 (same -- embedding alone: 0.90-0.92)
    'dave' vs 'dan':               0.222   (correctly below threshold)
    'mike' vs 'nike':              0.333   (false positive -- scores HIGHER
                                            than the true positive
                                            'dave'/'david', the concrete
                                            example of the noise this signal
                                            adds without adding real recall)

Root-different nicknames ("Bob"/"Robert", "Bill"/"William", "Dick"/"Richard")
share no meaningful character overlap at all ('bob' vs 'robert' scores
0.000) and aren't reliably close in embedding space either -- neither the
(unwired) trigram signal nor embedding catches those, which is why
`NICKNAME_GROUPS` below exists: a curated formal-name/nickname equivalence
table, looked up exactly rather than measured by similarity. Cross-
referenced against a published English-nicknames reference
(https://www.cc.kyoto-su.ac.jp/~trobb/nicklist.html) before inclusion, not
invented from memory. Deliberately not exhaustive (~65 common English given
names) and English-specific -- flagged, not hidden: a name convention
outside this table gets no benefit from this signal and falls back to
embedding similarity, which may or may not catch it depending on semantic
overlap.

A nickname-table hit is a *stronger* signal than trigram/embedding
similarity (it's exact lookup against curated ground truth, not a
heuristic), but it still only ever produces a *candidate* for the LLM to
verify, never an automatic merge -- two different people in the same
conversation can legitimately share a nickname relationship to two
different formal names ("my friend Bob" and "my brother Robert" are almost
certainly not the same person despite Bob/Robert being real nickname
equivalents), and this system's existing bounded-verification design
(ADR-020: an unresolved mention is skipped, never forced into a link)
already exists precisely to keep that judgment with the model, not a table.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

# Below this many bits of character-level Shannon entropy, a surface is too
# short/repetitive to fuzzy-match reliably -- calibrated against real
# examples: 'a' (single char) scores 0.0, 'ok' scores 1.0, 'max' scores 1.58.
# The floor sits at 1.0 specifically so degenerate single/repeated-character
# surfaces are excluded while real short names ('max', 'bob') still pass.
MIN_ENTROPY_FOR_FUZZY_MATCHING = 1.0

# Canonicalized surfaces shorter than this never fuzzy-match, regardless of
# entropy -- belt-and-suspenders against 1-character surfaces specifically
# (entropy alone treats a lone repeated character and a lone unique one
# differently in ways that aren't reliable protection on their own).
MIN_LENGTH_FOR_FUZZY_MATCHING = 2

# See this module's docstring for the calibration this threshold is picked
# from -- 0.25 sits strictly between the lowest confirmed true positive
# ('dave'/'david' at 0.300) and the highest confirmed true negative that
# must stay excluded ('dave'/'dan' at 0.222), while accepting some false
# positives ('mike'/'nike' at 0.333) as an acceptable blocking-stage cost.
TRIGRAM_JACCARD_BLOCKING_THRESHOLD = 0.25


def char_trigrams(text: str) -> set[str]:
    """3-character shingles over `text`, padded with two leading/trailing
    spaces so surfaces shorter than 3 characters still yield at least one
    shingle instead of an empty set (which would make every similarity
    against them trivially zero rather than meaningfully low)."""
    padded = f"  {text}  "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def char_trigram_jaccard_similarity(a: str, b: str) -> float:
    """Jaccard similarity over character trigrams -- the same technique
    Graphiti (Zep's knowledge-graph memory engine) uses for its own
    deterministic fuzzy-matching blocking stage, ahead of LLM verification."""
    set_a, set_b = char_trigrams(a), char_trigrams(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def surface_shannon_entropy(text: str) -> float:
    """Approximate Shannon entropy over `text`'s characters, in bits.
    Low-entropy strings (very short, or repetitive) are unstable for fuzzy
    matching -- almost anything looks similar to them -- so they're gated
    out of fuzzy blocking entirely rather than risk merging two genuinely
    different entities that happen to share a short surface."""
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def is_stable_for_fuzzy_matching(canonical_surface: str) -> bool:
    """Gate applied once to the *query* surface before any fuzzy blocking
    (string or embedding) runs against it -- if the surface itself is too
    short or too degenerate to fuzzy-match meaningfully, skip fuzzy
    blocking for this resolve() call entirely (exact canonical/alias
    matching and any caller-supplied `candidate_ids` are unaffected)."""
    return (
        len(canonical_surface) >= MIN_LENGTH_FOR_FUZZY_MATCHING
        and surface_shannon_entropy(canonical_surface) >= MIN_ENTROPY_FOR_FUZZY_MATCHING
    )


def find_fuzzy_candidates(
    canonical_surface: str,
    profiles: Iterable[object],
    *,
    threshold: float = TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
) -> list[int]:
    """Returns `graph_id`s of `profiles` (any object with `.graph_id`,
    `.canonical_name`, `.aliases` -- i.e. `EntityProfile`) whose canonical
    name or any known alias is trigram-similar enough to
    `canonical_surface` to be worth asking the LLM disambiguator about.
    Caller is responsible for gating `canonical_surface` with
    `is_stable_for_fuzzy_matching` first -- this function doesn't re-check
    it, so it can also be used against a surface that's already been judged
    stable once for both the string and embedding blocking passes.
    """
    matches: list[int] = []
    for profile in profiles:
        candidate_surfaces = (profile.canonical_name, *profile.aliases)
        best = max(
            (char_trigram_jaccard_similarity(canonical_surface, surface) for surface in candidate_surfaces),
            default=0.0,
        )
        if best >= threshold:
            matches.append(profile.graph_id)
    return matches


# Curated formal-name / nickname equivalence groups. Common English given
# names only, cross-referenced against
# https://www.cc.kyoto-su.ac.jp/~trobb/nicklist.html before inclusion --
# not exhaustive, not multilingual. Every name inside a group is treated as
# mutually equivalent for blocking purposes (a candidate to ask the LLM
# about, never an automatic merge -- see this module's docstring).
NICKNAME_GROUPS: tuple[frozenset[str], ...] = (
    # -- male --
    frozenset({"robert", "bob", "bobby", "rob", "robbie"}),
    frozenset({"william", "bill", "billy", "will", "willy", "liam"}),
    frozenset({"richard", "dick", "rick", "ricky", "richie"}),
    frozenset({"james", "jim", "jimmy", "jamie"}),
    frozenset({"john", "jack", "jacky", "johnny", "jon", "jonathan", "jonny"}),  # jon/jonny genuinely ambiguous between John and Jonathan -- merged, not picked
    frozenset({"joseph", "joe", "joey"}),
    frozenset({"michael", "mike", "mikey", "mick", "mickey"}),
    frozenset({"christopher", "chris", "topher"}),
    frozenset({"daniel", "dan", "danny"}),
    frozenset({"david", "dave", "davey"}),
    frozenset({"thomas", "tom", "thom", "tommy"}),
    frozenset({"charles", "charlie", "chuck"}),
    frozenset({"anthony", "tony"}),
    frozenset({"edward", "ed", "eddie", "ted", "teddy", "theodore"}),  # ted/teddy genuinely ambiguous between Edward and Theodore -- merged
    frozenset({"matthew", "matt", "matty"}),
    frozenset({"andrew", "andy", "drew"}),
    frozenset({"nicholas", "nick", "nicky"}),
    frozenset({"benjamin", "ben", "benny"}),
    frozenset({"gregory", "greg"}),
    frozenset({"kenneth", "ken", "kenny"}),
    frozenset({"timothy", "tim", "timmy"}),
    frozenset({"raymond", "ray"}),
    frozenset({"lawrence", "larry"}),
    frozenset({"jeffrey", "jeff", "jeffery"}),
    frozenset({"douglas", "doug"}),
    frozenset({"walter", "walt", "wally"}),
    frozenset({"eugene", "gene"}),
    frozenset({"russell", "russ"}),
    frozenset({"gerald", "gerry", "jerry"}),
    frozenset({"francis", "frank", "fran", "frankie"}),
    frozenset({"albert", "al"}),
    frozenset({"arthur", "art", "arty"}),
    frozenset({"vincent", "vince", "vinnie"}),
    frozenset({"leonard", "leo", "lenny"}),
    frozenset({"philip", "phil", "phillip"}),
    frozenset({"peter", "pete"}),
    frozenset({"martin", "marty"}),
    frozenset({"zachary", "zach", "zack"}),
    frozenset({"joshua", "josh"}),
    frozenset({"jacob", "jake"}),
    frozenset({"isaac", "ike"}),
    frozenset({"abraham", "abe"}),
    frozenset({"donald", "don", "donny"}),
    frozenset({"ronald", "ron", "ronny"}),
    frozenset({"bernard", "bernie", "bern"}),
    frozenset({"frederick", "fred", "freddy"}),
    frozenset({"harold", "hal", "henry", "hank", "harry"}),  # harry genuinely ambiguous between Harold and Henry -- merged
    frozenset({"irving", "irv"}),
    frozenset({"stuart", "stu"}),
    # -- female --
    frozenset({"elizabeth", "liz", "lizzy", "beth", "betty", "eliza", "libby", "betsy", "bess"}),
    frozenset({"margaret", "maggie", "meg", "peggy", "marge"}),
    frozenset({"katherine", "catherine", "kate", "katie", "kathy", "kat", "kit", "cathy", "cath"}),
    frozenset({"jennifer", "jen", "jenny"}),
    frozenset({"susan", "sue", "susie", "suzy"}),
    frozenset({"deborah", "deb", "debbie"}),
    frozenset({"barbara", "barb", "babs"}),
    frozenset({"cynthia", "cindy", "cynth"}),
    frozenset({"christine", "christy", "chrissy", "tina"}),
    frozenset({"victoria", "vicky", "tori"}),
    frozenset({"rebecca", "becky", "becca"}),
    frozenset({"jessica", "jess", "jessie"}),
    frozenset({"amanda", "mandy"}),
    frozenset({"nicole", "nikki"}),
    frozenset({"gabrielle", "gabby"}),
    frozenset({"veronica", "ronnie"}),
    frozenset({"theresa", "terry", "tessa"}),
    frozenset({"virginia", "ginny", "ginger"}),
    frozenset({"dorothy", "dot", "dottie"}),
    frozenset({"eleanor", "ellie", "nora", "nell"}),
    frozenset({"josephine", "jo", "josie"}),
    frozenset({"anne", "ann", "annie", "nan", "nancy"}),
    frozenset({"caroline", "carol", "carrie"}),
    frozenset({"kimberly", "kim", "kimmy"}),
    frozenset({"melissa", "mel", "missy"}),
    frozenset({"michelle", "shelly"}),
    frozenset({"pamela", "pam"}),
    frozenset({"sharon", "shari"}),
    frozenset({"diana", "diane", "di"}),
    frozenset({"donna", "donnie"}),
    frozenset({"gloria", "glo"}),
    frozenset({"judith", "judy", "jude"}),
    frozenset({"lillian", "lily", "lil"}),
    frozenset({"louise", "lou", "lulu"}),
    frozenset({"olivia", "liv", "livvy"}),
    frozenset({"penelope", "penny"}),
    frozenset({"priscilla", "cilla"}),
    frozenset({"rachel", "rae"}),
    frozenset({"regina", "gina", "reggie"}),
    frozenset({"roberta", "bobbie"}),
    frozenset({"rosalind", "roz"}),
    frozenset({"sylvia", "syl"}),
    frozenset({"tamara", "tammy"}),
    frozenset({"valerie", "val"}),
    frozenset({"yvonne", "vonna"}),
    frozenset({"florence", "flo"}),
    frozenset({"sophia", "sophie"}),
    # -- names genuinely shared across the male/female split above, or
    # colliding between two groups that would otherwise both claim the same
    # short form -- merged into one group each rather than picked arbitrarily,
    # consistent with this table being recall-biased (see module docstring).
    frozenset({"samuel", "samantha", "sam", "sammy"}),
    frozenset({"alexander", "alexandra", "alex", "xander", "sandra", "sandy", "lexi"}),
    frozenset({"patrick", "patricia", "pat", "paddy", "patty", "tricia", "trish"}),
    frozenset({"nathaniel", "nathan", "natalie", "nate", "nat", "nattie"}),
    frozenset({"stephen", "steven", "stephanie", "steve", "stevie", "stephan", "steph"}),
    frozenset({"janet", "janice", "jan"}),
)

_NICKNAME_GROUP_BY_NAME: dict[str, frozenset[str]] = {
    name: group for group in NICKNAME_GROUPS for name in group
}


def nickname_equivalents(canonical_surface: str) -> frozenset[str]:
    """Every name in `canonical_surface`'s curated nickname group,
    including itself -- empty if it isn't in the table at all (most names
    aren't; this table is intentionally small and specific, see this
    module's docstring)."""
    return _NICKNAME_GROUP_BY_NAME.get(canonical_surface, frozenset())


def find_nickname_candidates(canonical_surface: str, profiles: Iterable[object]) -> list[int]:
    """Returns `graph_id`s of `profiles` whose canonical name or any known
    alias is a curated nickname-equivalent of `canonical_surface`. Exact
    table lookup, not a similarity heuristic -- deliberately *not* gated by
    `is_stable_for_fuzzy_matching`: a 3-letter name like "Bob" is exactly
    the case this table exists for, and gating it out here would defeat the
    entire point of building a table instead of relying on trigram
    similarity."""
    equivalents = nickname_equivalents(canonical_surface)
    if not equivalents:
        return []
    matches: list[int] = []
    for profile in profiles:
        candidate_surfaces = (profile.canonical_name, *profile.aliases)
        if any(surface in equivalents for surface in candidate_surfaces):
            matches.append(profile.graph_id)
    return matches
