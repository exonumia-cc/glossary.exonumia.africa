"""Unit tests for scripts/glossary.py against a synthetic fixture.

The fixture deliberately includes an entry one language has not translated —
the real data currently has zero gaps, so the missing-entry path the skill
tells agents to respect is exercised nowhere else.
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
    (root / "manifest.json").write_text(json.dumps(["en", "sw"]), encoding="utf-8")
    (root / "en.json").write_text(json.dumps({
        "concepts": [
            {"key": "bitcoin", "term": "Bitcoin",
             "explanation": "A decentralized digital money network.", "notes": ""},
            {"key": "bitcoin-btc", "term": "bitcoin (BTC)",
             "explanation": "The currency unit.", "notes": ""},
            {"key": "seed-phrase", "term": "Seed Phrase",
             "explanation": "Words that recover a wallet.",
             "notes": "Extremely safety-critical."},
        ],
        "wallets": [
            {"key": "full-node", "term": "Full Node",
             "explanation": "Verifies all rules.", "notes": ""},
        ],
    }), encoding="utf-8")
    (root / "sw.json").write_text(json.dumps({
        "concepts": [
            {"key": "bitcoin", "term": "Bitcoin",
             "explanation": "Mtandao wa pesa.", "notes": ""},
            {"key": "bitcoin-btc", "term": "bitcoin",
             "explanation": "Sarafu ya bitcoin.", "notes": ""},
            # "seed-phrase" deliberately omitted: not yet translated.
        ],
        "wallets": [
            {"key": "full-node", "term": "Nodu kamili/ jiganiru/ jihuru.",
             "explanation": "Inathibitisha sheria zote.", "notes": ""},
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
        self.assertEqual(self.g.langs, ["en", "sw"])

    def test_lookup_by_term_and_key(self):
        self.assertEqual(self.g.lookup("seed phrase")["key"], "seed-phrase")
        self.assertEqual(self.g.lookup("Bitcoin")["key"], "bitcoin")
        self.assertEqual(self.g.lookup("nonexistent term"), None)

    def test_lookup_returns_none_for_untranslated_entry(self):
        result = self.g.lookup("seed phrase")
        self.assertEqual(result["sw"], None)
        self.assertEqual(result["en"], "Seed Phrase")

    def test_lookup_flags_safety_critical_entries(self):
        self.assertTrue(self.g.lookup("seed phrase")["safety_critical"])
        self.assertNotIn("safety_critical", self.g.lookup("bitcoin"))

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

    def test_reverse_matches_a_translated_term(self):
        result = self.g.reverse("bitcoin", "sw")
        self.assertEqual(result["key"], "bitcoin-btc")

    def test_reverse_matches_one_candidate_of_a_multi_variant_field(self):
        result = self.g.reverse("jiganiru", "sw")
        self.assertEqual(result["key"], "full-node")

    def test_reverse_ignores_trailing_period(self):
        result = self.g.reverse("Nodu kamili.", "sw")
        self.assertEqual(result["key"], "full-node")

    def test_variants_splits_candidate_lists(self):
        self.assertEqual(
            variants("Nodu kamili/ jiganiru/ jihuru."),
            ["Nodu kamili", "jiganiru", "jihuru."],
        )
        self.assertEqual(variants("Bitcoin"), ["Bitcoin"])


if __name__ == "__main__":
    unittest.main()
