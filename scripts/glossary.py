#!/usr/bin/env python3
"""Termbase access to the exonumia.africa multilingual Bitcoin glossary.

Load the glossary from a local checkout of the ``i18n/`` directory or
straight from the published site, then look terms up in either direction
or scan free text for covered terms::

    from glossary import Glossary

    g = Glossary.load("i18n")                                   # local directory
    g = Glossary.load("https://glossary.exonumia.africa/i18n")  # or base URL

    g.lookup("seed phrase")                 # English term -> entry + translations
    g.scan("Send bitcoin to this address")  # glossary terms found in free text
    g.reverse("Orodha ya maneno", "sw")     # translated term -> entry

Everything is stdlib-only; no dependencies to install.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from pathlib import Path

#: Where the glossary is published. Pass this to ``Glossary.load`` when you
#: are working outside the glossary repository.
BASE_URL = "https://glossary.exonumia.africa/i18n"

#: English ``notes`` matching this pattern flag strings where a mistranslation
#: can cost the user money ("Extremely safety-critical.", "High-priority UI
#: warning.", "Never mistranslate. Extremely high risk."). Route those to a
#: human reviewer instead of shipping them silently.
SAFETY_RE = re.compile(
    r"safety|critical|warning|high.risk|never mistranslate", re.IGNORECASE
)


def _normalize(text: str) -> str:
    """Casefold and strip diacritics, so ``gutuma`` matches ``gũtũma``."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def variants(term: str) -> list[str]:
    """Split a ``term`` field into its candidate translations.

    Several glossary entries hold more than one candidate translation in a
    single field, separated by ``/`` — e.g. Gĩkũyũ ``full-node`` is
    ``"Nodu kamili/ jiganiru/jagiriru/ jihuru/ nginyaniru"``. Such a field is
    a *list of options*, not a string to paste: pick one candidate using the
    entry's ``explanation`` and ``notes``, and say which one you picked.
    """
    return [v.strip() for v in term.split("/") if v.strip()]


class Glossary:
    """The loaded glossary: all languages, joined on ``(category, key)``."""

    def __init__(self, data: dict[str, dict[str, list[dict]]]):
        self.data = data
        self.langs = list(data)
        # (category, key) -> {lang: entry}; None for a language that has not
        # translated the entry yet.
        self._entries: dict[tuple[str, str], dict] = {}
        for lang, categories in data.items():
            for category, entries in categories.items():
                for entry in entries:
                    slot = self._entries.setdefault((category, entry["key"]), {})
                    slot[lang] = entry

    @classmethod
    def load(cls, source: str | Path = "i18n") -> "Glossary":
        """Load from a local ``i18n/`` directory or an HTTP base URL."""
        source = str(source)
        if source.startswith(("http://", "https://")):
            def read(name: str) -> dict:
                with urllib.request.urlopen(f"{source.rstrip('/')}/{name}") as r:
                    return json.loads(r.read().decode("utf-8"))
        else:
            base = Path(source)

            def read(name: str) -> dict:
                return json.loads((base / name).read_text(encoding="utf-8"))

        langs = read("manifest.json")
        return cls({lang: read(f"{lang}.json") for lang in langs})

    def get(self, category: str, key: str) -> dict[str, dict | None]:
        """All language entries for one ``(category, key)`` pair."""
        return self._entries[(category, key)]

    def _translations(self, category: str, key: str) -> dict:
        slot = self._entries[(category, key)]
        en = slot.get("en", {})
        out = {"category": category, "key": key, "en": en.get("term")}
        if SAFETY_RE.search(en.get("notes", "")):
            out["safety_critical"] = True
        for lang in self.langs:
            if lang == "en":
                continue
            entry = slot.get(lang)
            # None means the language has not translated this entry yet:
            # no established translation exists — flag it, do not coin one.
            out[lang] = entry["term"] if entry else None
        return out

    def lookup(self, english_term: str) -> dict | None:
        """Exact-match an English term (or its key) and return translations."""
        query = _normalize(english_term.strip())
        slug = re.sub(r"[^a-z0-9]+", "-", query).strip("-")
        for (category, key), slot in self._entries.items():
            en = slot.get("en")
            if en and (key == slug or _normalize(en["term"]) == query):
                return self._translations(category, key)
        return None

    def scan(self, text: str, lang: str = "en") -> list[dict]:
        """Find glossary terms inside free text, longest match first.

        Returns one ``lookup``-style dict per distinct term found, so you can
        extract the domain vocabulary of a screen or paragraph before
        translating it. Matching is case- and diacritic-insensitive on word
        boundaries; overlapping matches keep the longest term.
        """
        haystack = _normalize(text)
        needles = []  # (normalized term, category, key), longest first
        for (category, key), slot in self._entries.items():
            entry = slot.get(lang)
            if entry:
                needles.append((_normalize(entry["term"]), category, key))
        needles.sort(key=lambda n: len(n[0]), reverse=True)

        found, claimed = [], [False] * len(haystack)
        for needle, category, key in needles:
            if not needle:
                continue
            for m in re.finditer(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack):
                span = range(m.start(), m.end())
                if not any(claimed[i] for i in span):
                    for i in span:
                        claimed[i] = True
                    found.append(self._translations(category, key))
                    break
        return found

    def reverse(self, term: str, lang: str) -> dict | None:
        """Match a translated term back to its glossary entry.

        The direction needed when reviewing an existing translation file:
        given e.g. a Kiswahili string from an app's ``strings.sw.json``, find
        the concept it belongs to. Matches the whole ``term`` field or any
        single candidate of a multi-variant (``/``) field, ignoring trailing
        sentence punctuation. Prefers an exact case-sensitive match (so
        ``Bitcoin`` and ``bitcoin`` stay distinct); falls back to case- and
        diacritic-insensitive matching.
        """
        query = term.strip().rstrip(".")
        for match in (lambda c: c == query,
                      lambda c: _normalize(c) == _normalize(query)):
            for (category, key), slot in self._entries.items():
                entry = slot.get(lang)
                if not entry:
                    continue
                candidates = [entry["term"], *variants(entry["term"])]
                if any(match(c.rstrip(".")) for c in candidates):
                    return self._translations(category, key)
        return None


if __name__ == "__main__":
    import sys

    glossary = Glossary.load(sys.argv[1] if len(sys.argv) > 1 else "i18n")
    for query in sys.argv[2:] or ["seed phrase"]:
        print(json.dumps(glossary.lookup(query), ensure_ascii=False, indent=2))
