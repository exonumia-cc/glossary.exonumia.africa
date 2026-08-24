"""Assert the factual claims made in SKILL.md and README.md against i18n/.

Every number hardcoded in the documentation (term count, categories, language
alignment, field shape) goes stale the moment a translation lands. These tests
fail instead of letting the docs drift. Run after every regeneration:

    python3 -m unittest discover -s tests -v

The baselines below are exact, not upper bounds: fixing data is supposed to
fail here too, so the improvement gets written down instead of leaving room
for a silent regression back to the old number.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "i18n"

sys.path.insert(
    0, str(ROOT / ".claude" / "skills" / "glossary-localization" / "scripts"))

from glossary import SAFETY_RE, Glossary  # noqa: E402

# Documented in README.md ("The data") and .claude/skills/glossary-localization/SKILL.md.
CATEGORIES = [
    "concepts", "wallets", "security", "safety", "lightning-network",
    "payments", "privacy", "markets", "mobile-money", "seedsigner",
    "crypto-ecosystem", "ui", "wallet-ui", "advanced-bitcoin",
]
TERM_COUNT = 359

# Data-hygiene baseline: entries whose `term` field holds several candidate
# translations separated by "/", or ends in a sentence period. These are
# candidate lists / unclean strings, not paste-ready copy. Lower the number
# here when you clean entries up; raising it needs a deliberate decision.
MULTI_VARIANT_BASELINE = {"en": 2, "ki": 17, "sw": 14, "so": 2}
TRAILING_PERIOD_BASELINE = {"en": 0, "ki": 0, "sw": 2, "so": 13}

# Strings where one translation serves two distinct concepts, so a reverse
# lookup cannot tell them apart on its own. `Glossary.reverse` reports these
# via its "ambiguous" key; the skill tells agents to confirm rather than guess.
AMBIGUOUS_BASELINE = {"en": 0, "ki": 2, "sw": 1, "so": 2}

# Entries whose English `notes` mark them as money-risk strings. Locked as a
# set, not a count: SAFETY_RE is deliberately phrase-scoped, and this is what
# stops it silently widening or narrowing when notes are edited.
SAFETY_CRITICAL = {
    "anyone-with-these-words-can-steal-your-funds",
    "bitcoin-address",
    "custodial-wallet",
    "delete",
    "enter-seed-phrase",
    "never-share-your-private-key",
    "never-share-your-seed-phrase",
    "phishing",
    "private-key",
    "rug-pull",
    "seed-phrase",
    "verify-address",
    "verify-amount",
    "wallet-backup",
}


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


class TestSafetyFlags(unittest.TestCase):
    """Lock which entries SAFETY_RE treats as money-risk strings."""

    @classmethod
    def setUpClass(cls):
        cls.en = load("en")

    def flagged(self):
        return {e["key"] for entries in self.en.values() for e in entries
                if SAFETY_RE.search(e["notes"])}

    def test_safety_critical_set_is_locked(self):
        self.assertEqual(
            self.flagged(), SAFETY_CRITICAL,
            "SAFETY_RE now flags a different set — confirm the change is intended "
            "and update SAFETY_CRITICAL",
        )

    def test_presentation_notes_are_not_safety_critical(self):
        """`session-timeout` says "Critical for feature phones ... very brief".

        That is a screen-width constraint, not a financial risk. It is the
        reason SAFETY_RE does not match bare "critical".
        """
        self.assertNotIn("session-timeout", self.flagged())

    def test_the_highest_risk_entries_are_flagged(self):
        for key in ("seed-phrase", "private-key", "bitcoin-address"):
            with self.subTest(key=key):
                self.assertIn(key, self.flagged())


class TestDataHygiene(unittest.TestCase):
    """Track unclean and ambiguous term fields so the numbers only move deliberately."""

    @classmethod
    def setUpClass(cls):
        cls.langs = json.loads((I18N / "manifest.json").read_text(encoding="utf-8"))
        cls.data = {lang: load(lang) for lang in cls.langs}
        cls.g = Glossary.load(I18N)

    def entries(self, lang):
        return [e for entries in self.data[lang].values() for e in entries]

    def test_multi_variant_terms_match_baseline(self):
        for lang in self.langs:
            flagged = [e["key"] for e in self.entries(lang) if "/" in e["term"]]
            with self.subTest(lang=lang):
                self.assertEqual(
                    len(flagged), MULTI_VARIANT_BASELINE[lang],
                    f"{lang} multi-variant ('/') terms changed — lower "
                    f"MULTI_VARIANT_BASELINE if you cleaned these up: {flagged}",
                )

    def test_trailing_period_terms_match_baseline(self):
        for lang in self.langs:
            flagged = [e["key"] for e in self.entries(lang)
                       if e["term"].rstrip().endswith(".")]
            with self.subTest(lang=lang):
                self.assertEqual(
                    len(flagged), TRAILING_PERIOD_BASELINE[lang],
                    f"{lang} trailing-period terms changed — lower "
                    f"TRAILING_PERIOD_BASELINE if you cleaned these up: {flagged}",
                )

    def test_ambiguous_reverse_lookups_match_baseline(self):
        for lang in self.langs:
            # Distinct strings, not entries: both concepts sharing "Jaribu tena"
            # are one ambiguous string, not two.
            ambiguous = {e["term"] for e in self.entries(lang)
                         if "ambiguous" in (self.g.reverse(e["term"], lang) or {})}
            with self.subTest(lang=lang):
                self.assertEqual(
                    len(ambiguous), AMBIGUOUS_BASELINE[lang],
                    f"{lang} strings serving two concepts changed: {ambiguous}",
                )


if __name__ == "__main__":
    unittest.main()
