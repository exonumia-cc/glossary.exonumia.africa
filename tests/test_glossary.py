"""Unit tests for scripts/glossary.py against a synthetic fixture.

The fixture deliberately includes an entry one language has not translated —
the real data currently has zero gaps, so the missing-entry path the skill
tells agents to respect is exercised nowhere else. It also mirrors two real
ambiguities: two concepts sharing one Kiswahili translation, and a Soomaali
value that a Kiswahili reverse lookup cannot resolve.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent
        / ".claude" / "skills" / "glossary-localization" / "scripts"),
)

from glossary import Glossary, variants  # noqa: E402


def build_fixture(root: Path) -> None:
    (root / "manifest.json").write_text(
        json.dumps(["en", "sw", "so"]), encoding="utf-8")
    (root / "en.json").write_text(json.dumps({
        "concepts": [
            {"key": "bitcoin", "term": "Bitcoin",
             "explanation": "A decentralized digital money network.", "notes": ""},
            {"key": "bitcoin-btc", "term": "bitcoin (BTC)",
             "explanation": "The currency unit.", "notes": ""},
            {"key": "seed-phrase", "term": "Seed Phrase",
             "explanation": "Words that recover a wallet.",
             "notes": "Extremely safety-critical."},
            {"key": "session-timeout", "term": "Session Timeout",
             "explanation": "The session expired.",
             "notes": "Critical for feature phones; must be very brief."},
        ],
        "wallets": [
            {"key": "full-node", "term": "Full Node",
             "explanation": "Verifies all rules.", "notes": ""},
            {"key": "remaining-balance", "term": "Remaining Balance",
             "explanation": "What is left.", "notes": ""},
        ],
        "ui": [
            {"key": "retry", "term": "Retry", "explanation": "Try once more.",
             "notes": ""},
            {"key": "try-again", "term": "Try Again",
             "explanation": "Try once more.", "notes": ""},
        ],
    }), encoding="utf-8")
    (root / "sw.json").write_text(json.dumps({
        "concepts": [
            {"key": "bitcoin", "term": "Bitcoin",
             "explanation": "Mtandao wa pesa.", "notes": ""},
            {"key": "bitcoin-btc", "term": "bitcoin",
             "explanation": "Sarafu ya bitcoin.", "notes": ""},
            {"key": "session-timeout", "term": "Muda umeisha",
             "explanation": "Kipindi kimeisha.", "notes": ""},
            # "seed-phrase" deliberately omitted: not yet translated.
        ],
        "wallets": [
            {"key": "full-node", "term": "Nodu kamili/ jiganiru/ jihuru.",
             "explanation": "Inathibitisha sheria zote.", "notes": ""},
            {"key": "remaining-balance", "term": "Salio lililobaki",
             "explanation": "Kilichobaki.", "notes": ""},
        ],
        # Both concepts share one translation, as they do in the real data.
        "ui": [
            {"key": "retry", "term": "Jaribu tena", "explanation": "Jaribu tena.",
             "notes": ""},
            {"key": "try-again", "term": "Jaribu tena",
             "explanation": "Jaribu tena.", "notes": ""},
        ],
    }), encoding="utf-8")
    (root / "so.json").write_text(json.dumps({
        "concepts": [
            {"key": "bitcoin", "term": "Bitcoin", "explanation": "Shabakad.",
             "notes": ""},
            {"key": "bitcoin-btc", "term": "bitcoin", "explanation": "Lacag.",
             "notes": ""},
            {"key": "seed-phrase", "term": "Seed phrase",
             "explanation": "Erayada.", "notes": ""},
            {"key": "session-timeout", "term": "Waqtigu wuu dhamaaday",
             "explanation": "Waqtigu dhamaaday.", "notes": ""},
        ],
        "wallets": [
            {"key": "full-node", "term": "Nood buuxa", "explanation": "Hubi.",
             "notes": ""},
            {"key": "remaining-balance", "term": "Baaqiga/Haadhaga soo harey.",
             "explanation": "Waxa harey.", "notes": ""},
        ],
        "ui": [
            {"key": "retry", "term": "Isku day mar kale",
             "explanation": "Isku day.", "notes": ""},
            {"key": "try-again", "term": "Mar kale isku day",
             "explanation": "Isku day.", "notes": ""},
        ],
    }), encoding="utf-8")


class TestGlossaryHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        build_fixture(root)
        cls.g = Glossary.load(root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_loads_languages_in_manifest_order(self):
        self.assertEqual(self.g.langs, ["en", "sw", "so"])

    def test_load_accepts_a_timeout(self):
        """The kwarg exists and is inert for local loads."""
        g = Glossary.load(Path(self.tmp.name), timeout=1)
        self.assertEqual(g.langs, ["en", "sw", "so"])

    def test_lookup_by_term_and_key(self):
        self.assertEqual(self.g.lookup("seed phrase")["key"], "seed-phrase")
        self.assertEqual(self.g.lookup("Bitcoin")["key"], "bitcoin")
        self.assertEqual(self.g.lookup("nonexistent term"), None)

    def test_lookup_returns_none_for_untranslated_entry(self):
        result = self.g.lookup("seed phrase")
        self.assertEqual(result["sw"], None)
        self.assertEqual(result["en"], "Seed Phrase")
        self.assertEqual(result["so"], "Seed phrase")

    def test_lookup_flags_safety_critical_entries(self):
        self.assertTrue(self.g.lookup("seed phrase")["safety_critical"])
        self.assertNotIn("safety_critical", self.g.lookup("bitcoin"))

    def test_safety_flag_ignores_presentation_notes(self):
        """"Critical for feature phones" is a screen-width note, not a money risk."""
        self.assertNotIn("safety_critical", self.g.lookup("Session Timeout"))

    def test_lookup_keeps_capitalization_distinct(self):
        self.assertEqual(self.g.lookup("Bitcoin")["key"], "bitcoin")
        self.assertEqual(self.g.lookup("bitcoin (BTC)")["key"], "bitcoin-btc")

    def test_scan_finds_terms_inside_a_sentence(self):
        found = {r["key"] for r in self.g.scan("Never share your Seed Phrase, ever")}
        self.assertEqual(found, {"seed-phrase"})

    def test_scan_prefers_the_longest_match(self):
        # "Full Node" must win over a hypothetical shorter overlapping term.
        found = self.g.scan("Run a full node to verify")
        self.assertEqual([r["key"] for r in found], ["full-node"])

    def test_scan_is_case_and_diacritic_insensitive(self):
        found = {r["key"] for r in self.g.scan("BITCOIN is a network")}
        self.assertIn("bitcoin", found)

    def test_scan_reports_the_category_of_each_hit(self):
        found = self.g.scan("Retry the payment")
        self.assertEqual([(r["key"], r["category"]) for r in found],
                         [("retry", "ui")])

    def test_scan_can_be_restricted_to_categories(self):
        self.assertEqual(self.g.scan("Retry the payment", categories=("concepts",)), [])
        self.assertEqual(
            [r["key"] for r in self.g.scan("Retry the payment", categories=("ui",))],
            ["retry"],
        )

    def test_reverse_matches_a_translated_term(self):
        result = self.g.reverse("bitcoin", "sw")
        self.assertEqual(result["key"], "bitcoin-btc")

    def test_reverse_matches_one_candidate_of_a_multi_variant_field(self):
        result = self.g.reverse("jiganiru", "sw")
        self.assertEqual(result["key"], "full-node")

    def test_reverse_ignores_trailing_period(self):
        result = self.g.reverse("Nodu kamili.", "sw")
        self.assertEqual(result["key"], "full-node")

    def test_reverse_flags_an_ambiguous_match(self):
        """Two concepts share this Kiswahili string; the caller must be told."""
        result = self.g.reverse("Jaribu tena", "sw")
        self.assertEqual(result["key"], "retry")
        self.assertEqual(result["ambiguous"], ["try-again"])

    def test_reverse_omits_the_flag_when_unambiguous(self):
        self.assertNotIn("ambiguous", self.g.reverse("Salio lililobaki", "sw"))

    def test_reverse_all_returns_every_candidate_concept(self):
        keys = [r["key"] for r in self.g.reverse_all("Jaribu tena", "sw")]
        self.assertEqual(sorted(keys), ["retry", "try-again"])

    def test_reverse_all_is_empty_when_nothing_matches(self):
        self.assertEqual(self.g.reverse_all("nothing at all", "sw"), [])

    def test_reverse_any_finds_a_value_in_the_wrong_language(self):
        """A Soomaali value sitting in a Kiswahili file: sw finds nothing, so does."""
        value = "Baaqiga/Haadhaga soo harey."
        self.assertIsNone(self.g.reverse(value, "sw"))
        hits = self.g.reverse_any(value)
        self.assertEqual([(h["key"], h["matched_lang"]) for h in hits],
                         [("remaining-balance", "so")])

    def test_variants_splits_candidate_lists(self):
        self.assertEqual(
            variants("Nodu kamili/ jiganiru/ jihuru."),
            ["Nodu kamili", "jiganiru", "jihuru."],
        )
        self.assertEqual(variants("Bitcoin"), ["Bitcoin"])


if __name__ == "__main__":
    unittest.main()
