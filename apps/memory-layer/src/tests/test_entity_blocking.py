from __future__ import annotations

import unittest
from dataclasses import dataclass

from context_memory.ingestion.entity_blocking import (
    MIN_ENTROPY_FOR_FUZZY_MATCHING,
    MIN_LENGTH_FOR_FUZZY_MATCHING,
    NICKNAME_GROUPS,
    TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
    char_trigram_jaccard_similarity,
    find_fuzzy_candidates,
    find_nickname_candidates,
    is_stable_for_fuzzy_matching,
    nickname_equivalents,
    surface_shannon_entropy,
)


@dataclass
class _FakeProfile:
    graph_id: int
    canonical_name: str
    aliases: tuple[str, ...] = ()


class TrigramJaccardCalibrationTests(unittest.TestCase):
    """Locks in the exact numbers `entity_blocking.py`'s module docstring
    and threshold constants were calibrated against -- if these drift, the
    threshold's justification silently goes stale too."""

    def test_true_positive_pairs_score_above_threshold(self) -> None:
        self.assertGreaterEqual(
            char_trigram_jaccard_similarity("dave", "david"),
            TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
        )
        self.assertGreaterEqual(
            char_trigram_jaccard_similarity("sherlock holmes", "holmes"),
            TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
        )
        self.assertGreaterEqual(
            char_trigram_jaccard_similarity("sherlock holmes", "sherlock"),
            TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
        )

    def test_true_negative_pair_scores_below_threshold(self) -> None:
        self.assertLess(
            char_trigram_jaccard_similarity("dave", "dan"),
            TRIGRAM_JACCARD_BLOCKING_THRESHOLD,
        )

    def test_symmetry(self) -> None:
        self.assertEqual(
            char_trigram_jaccard_similarity("dave", "david"),
            char_trigram_jaccard_similarity("david", "dave"),
        )

    def test_identical_strings_score_one(self) -> None:
        self.assertEqual(char_trigram_jaccard_similarity("dave", "dave"), 1.0)

    def test_empty_string_scores_zero_not_an_error(self) -> None:
        self.assertEqual(char_trigram_jaccard_similarity("", "dave"), 0.0)
        self.assertEqual(char_trigram_jaccard_similarity("dave", ""), 0.0)


class EntropyGateTests(unittest.TestCase):
    def test_single_character_is_unstable(self) -> None:
        self.assertLess(surface_shannon_entropy("a"), MIN_ENTROPY_FOR_FUZZY_MATCHING)
        self.assertFalse(is_stable_for_fuzzy_matching("a"))

    def test_ordinary_short_name_is_stable(self) -> None:
        self.assertGreaterEqual(
            surface_shannon_entropy("max"), MIN_ENTROPY_FOR_FUZZY_MATCHING
        )
        self.assertTrue(is_stable_for_fuzzy_matching("max"))

    def test_length_gate_excludes_single_character_surfaces_regardless_of_entropy(
        self,
    ) -> None:
        self.assertLess(
            1, MIN_LENGTH_FOR_FUZZY_MATCHING + 1
        )  # sanity: gate constant is what the test assumes
        self.assertFalse(is_stable_for_fuzzy_matching("x"))

    def test_empty_surface_is_unstable(self) -> None:
        self.assertFalse(is_stable_for_fuzzy_matching(""))


class FindFuzzyCandidatesTests(unittest.TestCase):
    def test_finds_nickname_style_near_miss(self) -> None:
        profiles = [_FakeProfile(1, "dave"), _FakeProfile(2, "alex")]
        self.assertEqual(find_fuzzy_candidates("david", profiles), [1])

    def test_does_not_match_a_genuinely_different_short_name(self) -> None:
        profiles = [_FakeProfile(1, "dan")]
        self.assertEqual(find_fuzzy_candidates("dave", profiles), [])

    def test_matches_against_an_alias_not_just_canonical_name(self) -> None:
        profiles = [_FakeProfile(1, "maxwell", aliases=("dave",))]
        self.assertEqual(find_fuzzy_candidates("david", profiles), [1])

    def test_sherlock_holmes_example_from_the_microsoft_graphrag_dedup_issue(
        self,
    ) -> None:
        """The exact case Microsoft GraphRAG's own issue #401 cites as
        unresolved: 'Sherlock Holmes' fragmenting into separate nodes for
        'Holmes', 'Sherlock', and other partial forms."""
        profiles = [_FakeProfile(1, "sherlock holmes")]
        self.assertEqual(find_fuzzy_candidates("holmes", profiles), [1])
        self.assertEqual(find_fuzzy_candidates("sherlock", profiles), [1])

    def test_empty_profile_list_returns_empty(self) -> None:
        self.assertEqual(find_fuzzy_candidates("dave", []), [])

    def test_custom_threshold_is_respected(self) -> None:
        profiles = [
            _FakeProfile(1, "dan")
        ]  # 'dave'/'dan' = 0.222, below default but above a looser threshold
        self.assertEqual(find_fuzzy_candidates("dave", profiles, threshold=0.9), [])
        self.assertEqual(find_fuzzy_candidates("dave", profiles, threshold=0.2), [1])


class NicknameTableTests(unittest.TestCase):
    """The root-different-nickname gap flagged as not-yet-closed when the
    trigram/embedding blocking was first added ('bob' vs 'robert' scores
    0.000 -- no character overlap at all) -- covered here now that
    `NICKNAME_GROUPS` closes it with a curated lookup instead."""

    def test_no_name_appears_in_two_groups(self) -> None:
        """A name silently landing in two groups would mean
        `_NICKNAME_GROUP_BY_NAME`'s dict-comprehension construction picks
        whichever group happens to iterate last, silently dropping the
        other -- e.g. 'harry' genuinely means either Harold or Henry, so
        those must be one merged group, not two colliding ones."""
        seen: dict[str, frozenset[str]] = {}
        for group in NICKNAME_GROUPS:
            for name in group:
                self.assertNotIn(
                    name,
                    seen,
                    f"{name!r} appears in two groups: {seen.get(name)} and {group} -- merge them",
                )
                seen[name] = group

    def test_classic_root_different_nickname_pairs_are_covered(self) -> None:
        """The exact cases the trigram pass alone cannot catch."""
        pairs = [
            ("bob", "robert"),
            ("bill", "william"),
            ("dick", "richard"),
            ("jack", "john"),
            ("peggy", "margaret"),
        ]
        for nickname, formal in pairs:
            self.assertIn(
                formal,
                nickname_equivalents(nickname),
                f"{nickname!r} should be a recorded equivalent of {formal!r}",
            )

    def test_name_outside_the_table_has_no_equivalents(self) -> None:
        self.assertEqual(nickname_equivalents("xerxes"), frozenset())

    def test_find_nickname_candidates_matches_bob_to_robert(self) -> None:
        profiles = [_FakeProfile(1, "robert")]
        self.assertEqual(find_nickname_candidates("bob", profiles), [1])

    def test_find_nickname_candidates_matches_via_alias_not_just_canonical(
        self,
    ) -> None:
        profiles = [_FakeProfile(1, "the landlord", aliases=("robert",))]
        self.assertEqual(find_nickname_candidates("bob", profiles), [1])

    def test_find_nickname_candidates_does_not_match_unrelated_short_name(self) -> None:
        profiles = [_FakeProfile(1, "dan")]
        self.assertEqual(find_nickname_candidates("bob", profiles), [])

    def test_ambiguous_nickname_matches_all_its_real_formal_names(self) -> None:
        """'Harry' is genuinely short for both Harold and Henry -- the
        merged group must surface both as candidates, not silently pick
        one and drop the other."""
        profiles = [_FakeProfile(1, "harold"), _FakeProfile(2, "henry")]
        self.assertEqual(sorted(find_nickname_candidates("harry", profiles)), [1, 2])

    def test_short_surface_still_matches_despite_normally_failing_the_stability_gate(
        self,
    ) -> None:
        """'bob' (3 chars, entropy ~1.5) would pass the general fuzzy gate
        anyway, but the point of nickname lookup is it doesn't need to --
        confirmed by a name short enough that trigram similarity alone
        would find nothing ('bob' vs 'robert' scores 0.000, see
        entity_blocking.py's module docstring)."""
        self.assertEqual(char_trigram_jaccard_similarity("bob", "robert"), 0.0)
        profiles = [_FakeProfile(1, "robert")]
        self.assertEqual(find_nickname_candidates("bob", profiles), [1])


if __name__ == "__main__":
    unittest.main()
