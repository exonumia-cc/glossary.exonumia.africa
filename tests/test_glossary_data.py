"""Assert the factual claims made in SKILL.md and README.md against i18n/.

Every number hardcoded in the documentation (term count, categories, language
alignment, field shape) goes stale the moment a translation lands. These tests
fail instead of letting the docs drift. Run after every regeneration:

    python3 -m unittest discover -s tests -v
"""

import json
import unittest
from pathlib import Path

I18N = Path(__file__).resolve().parent.parent / "i18n"

# Documented in README.md ("The data") and .claude/skills/glossary-localization/SKILL.md.
CATEGORIES = [
    "concepts", "wallets", "security", "safety", "lightning-network",
    "payments", "privacy", "markets", "mobile-money", "seedsigner",
    "crypto-ecosystem", "ui", "wallet-ui", "advanced-bitcoin",
]
TERM_COUNT = 359

# Data-hygiene baseline: entries whose `term` field holds several candidate
# translations separated by "/", or ends in a sentence period. These are
# candidate lists / unclean strings, not paste-ready copy. The counts may only
# ever shrink — a regeneration that adds one fails here.
MULTI_VARIANT_BASELINE = {"en": 2, "ki": 17, "sw": 14, "so": 2}
TRAILING_PERIOD_BASELINE = {"en": 0, "ki": 0, "sw": 2, "so": 13}


def load(lang):
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


class TestGlossaryClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.langs = json.loads((I18N / "manifest.json").read_text(encoding="utf-8"))
        cls.data = {lang: load(lang) for lang in cls.langs}

    def test_manifest_languages(self):
        self.assertEqual(self.langs, ["en", "ki", "sw", "so"])

    def test_categories(self):
        self.assertEqual(list(self.data["en"]), CATEGORIES)
        self.assertEqual(len(CATEGORIES), 14)

    def test_term_count(self):
        count = sum(len(entries) for entries in self.data["en"].values())
        self.assertEqual(count, TERM_COUNT)

    def test_entry_shape(self):
        for lang, categories in self.data.items():
            for category, entries in categories.items():
                for entry in entries:
                    with self.subTest(lang=lang, category=category, entry=entry):
                        self.assertEqual(set(entry), {"key", "term", "explanation", "notes"})
                        for field in ("key", "term", "explanation", "notes"):
                            self.assertIsInstance(entry[field], str)

    def test_keys_globally_unique(self):
        keys = [e["key"] for entries in self.data["en"].values() for e in entries]
        self.assertEqual(len(keys), len(set(keys)))

    def test_no_empty_terms(self):
        for lang, categories in self.data.items():
            for category, entries in categories.items():
                for entry in entries:
                    with self.subTest(lang=lang, key=entry["key"]):
                        self.assertTrue(entry["term"].strip())

    def test_languages_aligned(self):
        """Every language covers the same (category, key) pairs as English."""
        en_keys = {(c, e["key"]) for c, entries in self.data["en"].items() for e in entries}
        for lang in self.langs[1:]:
            keys = {(c, e["key"]) for c, entries in self.data[lang].items() for e in entries}
            self.assertEqual(keys, en_keys, f"{lang} is out of sync with en")


class TestDataHygiene(unittest.TestCase):
    """Track unclean term fields so the numbers trend to zero, not up."""

    @classmethod
    def setUpClass(cls):
        cls.langs = json.loads((I18N / "manifest.json").read_text(encoding="utf-8"))
        cls.data = {lang: load(lang) for lang in cls.langs}

    def entries(self, lang):
        return [e for entries in self.data[lang].values() for e in entries]

    def test_multi_variant_terms_do_not_grow(self):
        for lang in self.langs:
            flagged = [e["key"] for e in self.entries(lang) if "/" in e["term"]]
            self.assertLessEqual(
                len(flagged), MULTI_VARIANT_BASELINE[lang],
                f"{lang} gained multi-variant ('/') terms: {flagged}",
            )

    def test_trailing_period_terms_do_not_grow(self):
        for lang in self.langs:
            flagged = [e["key"] for e in self.entries(lang) if e["term"].rstrip().endswith(".")]
            self.assertLessEqual(
                len(flagged), TRAILING_PERIOD_BASELINE[lang],
                f"{lang} gained trailing-period terms: {flagged}",
            )


if __name__ == "__main__":
    unittest.main()
