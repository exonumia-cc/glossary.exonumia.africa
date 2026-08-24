---
name: glossary-localization
description: Use the exonumia.africa multilingual Bitcoin glossary (English, Gĩkũyũ, Kiswahili, Soomaali) to localize app UI, translations, and copy with consistent, community-vetted terminology. Use when translating or reviewing text involving Bitcoin, Lightning, or mobile-money terms in these languages.
---

# Glossary-driven localization

This repository holds a community-maintained multilingual glossary of Bitcoin, Lightning
Network, and mobile-money terminology: **359 terms across 14 categories in 4 languages** —
English (`en`), Gĩkũyũ (`ki`), Kiswahili (`sw`), and Soomaali (`so`). Use it whenever you
translate or review app UI, marketing copy, documentation, or user messages so that
terminology stays consistent with what the community already uses.

## Getting the data

**Local checkout** (this repo): the data lives in `i18n/`.

**Remote** (any other project): fetch the same files over HTTP —

```
https://glossary.exonumia.africa/i18n/manifest.json   # language codes, e.g. ["en","ki","sw","so"]
https://glossary.exonumia.africa/i18n/en.json         # one file per language code
```

## Data model

Each `i18n/<code>.json` is an object keyed by category slug (`concepts`, `wallets`,
`security`, `lightning-network`, `mobile-money`, `ui`, `wallet-ui`, …), each holding a list
of entries:

```json
{
  "key": "seed-phrase",
  "term": "Seed Phrase",
  "explanation": "A list of words that stores all the information needed to recover a wallet.",
  "notes": "Translator guidance, not reader-facing copy."
}
```

- `key` — slugified English term; **this is what pairs an entry across languages**. Join
  languages on `(category, key)`, never on the translated `term`.
- `explanation` — a plain-language definition, useful as context when choosing between
  possible translations.
- `notes` — translator guidance (e.g. "Avoid misleading 'database' metaphors"). Respect it
  when translating, but never surface it in user-facing copy. Often empty.
- A language may omit an entry it has not translated yet. Treat a missing `(category, key)`
  as "no established translation exists" — do not silently invent one; flag it for the user
  or propose a coinage clearly marked as new.

## Workflows

### 1. Look up terminology before translating

Before translating copy, extract the domain terms it contains (Bitcoin, wallet, seed phrase,
fee, Lightning invoice, …) and pull their established translations:

```python
import json

langs = ["en", "ki", "sw", "so"]
data = {l: json.load(open(f"i18n/{l}.json")) for l in langs}

def lookup(english_term):
    """Return all translations for an English term (case-insensitive)."""
    q = english_term.strip().lower()
    for cat, entries in data["en"].items():
        for e in entries:
            if e["term"].lower() == q or e["key"] == q.replace(" ", "-"):
                out = {"category": cat, "key": e["key"], "en": e["term"]}
                for l in langs[1:]:
                    match = next(
                        (x for x in data[l].get(cat, []) if x["key"] == e["key"]), None
                    )
                    out[l] = match["term"] if match else None  # None = not yet translated
                return out
    return None
```

Then use those exact terms in your translation instead of improvising equivalents.

### 2. Review existing translations for consistency

Given a translated file (e.g. an app's `strings.sw.json`), check that every glossary term
appearing in the source text uses the glossary's translation. Mismatches usually mean either
an inconsistency to fix or a deliberate choice to confirm with the user.

### 3. Translate with the glossary as a termbase

When producing a new translation:

1. Load the glossary for the target language.
2. Translate the copy, using glossary `term` values verbatim for covered concepts.
3. Read each matched entry's `explanation` and `notes` first — several terms have subtle
   distinctions (e.g. `bitcoin` the network vs `bitcoin (BTC)` the currency; "avoid
   'database' metaphors" for blockchain).
4. For terms the glossary does not cover, translate naturally and list them separately so
   the user knows they are new coinages, not community-vetted.
5. Preserve untranslatables the glossary itself keeps in English (e.g. `Blockchain`,
   `Block` stay English in Kiswahili).

## Conventions to respect

- Keep the glossary's capitalization habits — e.g. `Bitcoin` (network) vs lowercase
  `bitcoin` (currency) is meaningful and is reflected in the translations.
- This glossary covers African-language Bitcoin vocabulary; for general non-technical words,
  translate normally — the glossary is a termbase, not a dictionary.
- Translations are community contributions and a work in progress. If the user is a
  glossary contributor, suggest feeding genuinely new coinages back via the CSV →
  `conversion-script.py` pipeline described in the repo's `README.md` rather than letting
  app copies drift from the glossary.
