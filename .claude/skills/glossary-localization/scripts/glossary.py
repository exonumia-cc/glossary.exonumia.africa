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
    g.reverse_any("Baaqiga")                # ...when you do not know the language

Everything is stdlib-only; no dependencies to install. Python 3.9+.
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

#: Seconds to wait on a remote load before giving up. Without this urllib
#: inherits the default socket timeout, which is ``None`` — an unreachable
#: host would hang an agent indefinitely rather than failing.
DEFAULT_TIMEOUT = 30

#: English ``notes`` matching this pattern flag strings where a mistranslation
#: can cost the user money ("Extremely safety-critical.", "High-risk action.",
#: "Never mistranslate. Extremely high risk."). Route those to a human
#: reviewer instead of shipping them silently.
#:
#: Deliberately phrase-scoped rather than matching bare "critical": some notes
#: use that word for presentation constraints, not risk — ``session-timeout``
#: is "Critical for feature phones ... must be very brief", which is a
#: screen-width note, not a financial one. Widen this only with a phrase that
#: actually denotes risk, and update ``tests/test_glossary_data.py``.
SAFETY_RE = re.compile(
    r"safety|high[- ]risk|never mistranslate"
    r"|extremely critical|critical educational|high[- ]priority ui warning",
    re.IGNORECASE,
)

#: Categories that hold generic interface chrome ("Back", "Next", "Save")
#: rather than domain vocabulary. ``scan`` still reports them — you do want
#: button labels translated consistently — but they match ordinary English
#: prose freely, so weigh them differently from a ``concepts`` hit.
CHROME_CATEGORIES = ("ui", "wallet-ui")


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
        # (category, key) -> {lang: entry}; a language missing from the slot
        # has not translated the entry yet.
        self._entries: dict[tuple[str, str], dict] = {}
        for lang, categories in data.items():
            for category, entries in categories.items():
                for entry in entries:
                    slot = self._entries.setdefault((category, entry["key"]), {})
                    slot[lang] = entry

    @classmethod
    def load(cls, source: str | Path = "i18n",
             timeout: float = DEFAULT_TIMEOUT) -> "Glossary":
        """Load from a local ``i18n/`` directory or an HTTP base URL.

        ``timeout`` applies to remote loads only, and defaults to
        ``DEFAULT_TIMEOUT`` so a blocked network fails fast.
        """
        source = str(source)
        if source.startswith(("http://", "https://")):
            def read(name: str) -> dict:
                url = f"{source.rstrip('/')}/{name}"
                with urllib.request.urlopen(url, timeout=timeout) as r:
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

    def scan(self, text: str, lang: str = "en",
             categories: tuple[str, ...] | None = None) -> list[dict]:
        """Find glossary terms inside free text, longest match first.

        Returns one ``lookup``-style dict per distinct term found, so you can
        extract the domain vocabulary of a screen or paragraph before
        translating it. Matching is case- and diacritic-insensitive on word
        boundaries; overlapping matches keep the longest term.

        Every result carries its ``category``. Short entries in the
        ``CHROME_CATEGORIES`` — "Back", "Next", "Save" — match ordinary
        English freely, so check the category before treating a hit as
        domain terminology. Pass ``categories`` to restrict the scan.
        """
        haystack = _normalize(text)
        needles = []  # (normalized term, category, key), longest first
        for (category, key), slot in self._entries.items():
            if categories is not None and category not in categories:
                continue
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

    def reverse_all(self, term: str, lang: str) -> list[dict]:
        """Every glossary concept a translated term could belong to.

        Distinct concepts genuinely share a translation — Soomaali
        ``Erey dib usoocelin`` is both ``passphrase`` and ``recovery-words``,
        Gĩkũyũ ``Kugura`` is both ``limit-order`` and ``market-order``. When
        reviewing a translation file you need to see the whole set, not one
        arbitrary pick.

        Matches the whole ``term`` field or any single candidate of a
        multi-variant (``/``) field, ignoring trailing sentence punctuation.
        Case-sensitive matches win outright (so ``Bitcoin`` the network and
        ``bitcoin`` the currency stay distinct); only if none exist does it
        fall back to case- and diacritic-insensitive matching.
        """
        query = term.strip().rstrip(".")
        for match in (lambda c: c == query,
                      lambda c: _normalize(c) == _normalize(query)):
            hits = []
            for (category, key), slot in self._entries.items():
                entry = slot.get(lang)
                if not entry:
                    continue
                candidates = [entry["term"], *variants(entry["term"])]
                if any(match(c.rstrip(".")) for c in candidates):
                    hits.append(self._translations(category, key))
            if hits:
                return hits
        return []

    def reverse(self, term: str, lang: str) -> dict | None:
        """Match a translated term back to its glossary entry.

        The direction needed when reviewing an existing translation file:
        given e.g. a Kiswahili string from an app's ``strings.sw.json``, find
        the concept it belongs to. Returns the first match, and when the
        string is genuinely ambiguous adds an ``"ambiguous"`` key listing the
        other concepts it could equally be — confirm those with the user
        rather than guessing. Use ``reverse_all`` to get the full set.
        """
        hits = self.reverse_all(term, lang)
        if not hits:
            return None
        first = dict(hits[0])
        if len(hits) > 1:
            first["ambiguous"] = [h["key"] for h in hits[1:]]
        return first

    def reverse_any(self, term: str) -> list[dict]:
        """Reverse-look a term up across every language.

        Use when you do not know which language a string is in — including
        the case that proves it: a value in the wrong language for the file
        it sits in. ``reverse(value, "sw")`` returning ``None`` while
        ``reverse_any(value)`` matches under ``so`` is exactly that finding.
        Each result carries ``matched_lang``.
        """
        return [
            {**hit, "matched_lang": lang}
            for lang in self.langs
            for hit in self.reverse_all(term, lang)
        ]


if __name__ == "__main__":
    import sys

    # Default to a repo-local i18n/ when present, else the published site.
    default = "i18n" if Path("i18n").is_dir() else BASE_URL
    glossary = Glossary.load(sys.argv[1] if len(sys.argv) > 1 else default)
    for query in sys.argv[2:] or ["seed phrase"]:
        print(json.dumps(glossary.lookup(query), ensure_ascii=False, indent=2))
