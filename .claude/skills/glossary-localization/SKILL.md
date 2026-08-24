---
name: glossary-localization
description: Localize apps and copy with the exonumia.africa multilingual Bitcoin glossary (English, Gĩkũyũ, Kiswahili, Soomaali) so terminology stays consistent and community-vetted. Use when translating or reviewing Bitcoin, Lightning, or mobile-money UI strings, app copy, or documentation in these languages — for example when the user asks to "translate my app to Swahili", "localize my Bitcoin wallet", "review my strings.sw.json", or "check this translation against the glossary". Not for general translation unrelated to Bitcoin, Lightning, or mobile money.
license: MIT
compatibility: Requires Python 3 (stdlib only) for the bundled helper script. Network access is needed only when loading the glossary from the published URL instead of a local checkout.
metadata:
  author: exonumia.africa
  version: 1.1.0
---

# Glossary-driven localization

This skill gives you a community-maintained multilingual glossary of Bitcoin, Lightning
Network, and mobile-money terminology: **359 terms across 14 categories in 4 languages** —
English (`en`), Gĩkũyũ (`ki`), Kiswahili (`sw`), and Soomaali (`so`). Use it whenever you
translate or review app UI, marketing copy, documentation, or user messages so that
terminology stays consistent with what the community already uses.

## Critical

Three rules override everything else in this skill:

1. **Never paste a `term` field verbatim without checking it.** Fields containing `/` are
   *lists of candidate translations* — pick one, say which. Some fields end in a spurious
   sentence period — strip it for UI labels. See "Term fields are data, not paste-ready
   copy".
2. **Never ship a safety-critical translation without human review.** Entries flagged
   `"safety_critical": True` (seed phrases, private keys, address verification) have
   financial consequences if mistranslated — mark your translation as machine-assisted and
   escalate it. See "Safety-critical strings need human review".
3. **Never silently invent a translation for a term the glossary does not cover.** A
   missing entry means no community-vetted translation exists — flag it, or propose a
   coinage clearly marked as new.

## Getting the data

**Local checkout** (the glossary repo): the data lives in `i18n/`.

**Remote** (any other project): the same files are served over HTTP, CORS-open —

```
https://glossary.exonumia.africa/i18n/manifest.json   # language codes, e.g. ["en","ki","sw","so"]
https://glossary.exonumia.africa/i18n/en.json         # one file per language code
```

## The helper: `scripts/glossary.py`

Stdlib-only Python, bundled in this skill's `scripts/` directory. It loads from a local
`i18n/` directory or straight from the published URL. Use it instead of writing your own
parsing — it encodes the data rules in this skill.

```python
import sys; sys.path.insert(0, "<skill-folder>/scripts")
from glossary import Glossary

g = Glossary.load("i18n")                                   # local directory
g = Glossary.load("https://glossary.exonumia.africa/i18n")  # remote, from any project

g.lookup("seed phrase")     # English term -> {category, key, en, ki, sw, so, ...}
g.scan("Never share your seed phrase")  # glossary terms found inside free text
g.reverse("jiganiru", "ki")             # translated term -> its glossary entry
```

- `lookup()` — exact match on an English term or its key. Returns `None` per language for
  entries that language has not translated yet, and adds `"safety_critical": True` when the
  English `notes` flag the entry.
- `scan(text)` — finds glossary terms *inside* a sentence (longest match first, case- and
  diacritic-insensitive). This is the hard first step of any translation job: extracting
  which domain terms the copy actually contains.
- `reverse(term, lang)` — translated term → entry, for reviewing an existing translation
  file. Matches whole fields and single candidates of multi-variant fields; prefers an
  exact case-sensitive match.
- `variants(term)` — splits a multi-variant (`/`) field into its candidate translations.

If you are not in a Python environment, the rules below are enough to work directly with
the JSON.

## Data model

Each `i18n/<code>.json` is an object keyed by category slug (`concepts`, `wallets`,
`security`, `lightning-network`, `mobile-money`, `ui`, `wallet-ui`, …), each holding a list
of entries:

```json
{
  "key": "seed-phrase",
  "term": "Seed Phrase",
  "explanation": "A list of words that stores all the information needed to recover a wallet.",
  "notes": "Extremely safety-critical."
}
```

- `key` — slugified English term; **this is what pairs an entry across languages**. Join
  languages on `(category, key)`, never on the translated `term`.
- `explanation` — a plain-language definition, useful as context when choosing between
  possible translations.
- `notes` — translator guidance. Respect it when translating, but never surface it in
  user-facing copy. Often empty.
- A language may omit an entry it has not translated yet — that is Critical rule 3's
  trigger.

## Term fields are data, not paste-ready copy

Two hygiene issues in the current data mean you must not paste a `term` field verbatim:

1. **Multi-variant fields.** Dozens of entries hold several candidate translations in one
   field, separated by `/` — e.g. Gĩkũyũ `full-node` is
   `Nodu kamili/ jiganiru/jagiriru/ jihuru/ nginyaniru`. Such a field is a *list of
   options*: pick **one** candidate using the entry's `explanation` and `notes`, use it
   consistently, and tell the user which one you picked. `variants()` does the split.
2. **Trailing sentence periods.** Some fields end in a spurious period
   (e.g. Soomaali `remaining-balance` → `Baaqiga/Haadhaga soo harey.`). Strip trailing
   sentence punctuation for labels and short UI strings; keep it only when the target
   string is genuinely a full sentence.

## Safety-critical strings need human review

A number of English entries carry `notes` like "Extremely safety-critical." (`seed-phrase`),
"High-priority UI warning." (`never-share-your-seed-phrase`), "Safety-critical."
(`bitcoin-address`, `verify-address`, `verify-amount`), or "Never mistranslate. Extremely
high risk." (`private-key`). For a Bitcoin wallet, a mistranslated seed-phrase warning has
direct financial consequences. Produce your best translation, mark it as machine-assisted,
and route it to a human reviewer — Critical rule 2. `lookup()` surfaces these as
`"safety_critical": True`.

## Workflows

### 1. Translate new copy

1. `g.scan(copy_text)` to extract every glossary-covered term in the source text.
2. Translate the copy, using one chosen variant per matched term (Critical rule 1).
3. Read each matched entry's `explanation` and `notes` first — several terms have subtle
   distinctions (e.g. `Bitcoin` the network vs `bitcoin (BTC)` the currency; "avoid
   misleading 'database' metaphors" for blockchain).
4. Escalate any `safety_critical` entries for human review (Critical rule 2).
5. For terms the glossary does not cover, translate naturally and list them separately so
   the user knows they are new coinages, not community-vetted (Critical rule 3).

### 2. Review an existing translation file

Given e.g. an app's `strings.sw.json`: for each value, `g.reverse(value, "sw")` to find the
concept it claims to translate. Then check:

- the value uses one of the glossary's variants for that concept (a mismatch is either an
  inconsistency to fix or a deliberate choice to confirm with the user);
- the same concept is translated the same way everywhere in the file;
- no value pastes a raw multi-variant (`/`) field;
- every `safety_critical` concept has had human review.

Stop when every value either matches a glossary variant or has a user-confirmed deviation —
do not keep re-translating entries that are already consistent.

## Examples

**Example 1 — translate a screen.**
User says: "Translate my wallet's settings screen into Kiswahili."

1. `Glossary.load(...)`, then `g.scan(...)` the English source strings → finds
   `seed-phrase` (`safety_critical`), `wallet-backup`, `session-timeout`.
2. Translate each string, using one chosen variant per matched term.
3. Result delivered to the user: the translated strings, a note that the `seed-phrase`
   string is machine-assisted and needs human review, and a short list of any terms the
   glossary did not cover.

**Example 2 — review an existing translation.**
User says: "Review my `strings.sw.json` against the glossary."

1. For each value, `g.reverse(value, "sw")` → concept key.
2. Flag values that match no entry (uncovered or divergent), values that paste a raw `/`
   field, and concepts translated two different ways in the same file.
3. Result: a mismatch report keyed by concept, plus the list of `safety_critical` strings
   requiring human sign-off.

## Troubleshooting

- **Remote load fails** (`URLError`, network blocked): use a local checkout's `i18n/`
  directory instead, or attach the JSON files to the conversation and load them from disk.
  The data is identical.
- **`lookup()` returns `None`**: the term is not covered — apply Critical rule 3. Try the
  key slug form (`"seed-phrase"`) if the display-term form found nothing.
- **`reverse()` matches the wrong entry**: it prefers case-sensitive matches, so pass the
  string with its original casing; if a match still looks wrong, confirm with the user
  rather than rewriting the string.
- **Skill folder uploaded to Claude.ai**: the folder must contain `SKILL.md` at its root
  (it does); the `scripts/` and `references/` subfolders go along with it.

## Conventions to respect

- Keep the glossary's capitalization habits — `Bitcoin` (the network, key `bitcoin`) vs
  lowercase `bitcoin (BTC)` (the currency) is meaningful and is reflected in the
  translations.
- This glossary covers Bitcoin / Lightning / mobile-money vocabulary; for general
  non-technical words, translate normally — it is a termbase, not a dictionary.
- Preserve untranslatables the glossary itself keeps in English (e.g. `Blockchain`,
  `Block` stay English in Kiswahili).
- Translations are community contributions and a work in progress. If the user is a
  glossary contributor, suggest feeding genuinely new coinages back via the CSV →
  `conversion-script.py` pipeline described in the repo's `README.md` rather than letting
  app copies drift from the glossary.

## Testing this skill

`references/eval-plan.md` holds the trigger and functional test set for this skill —
run it after changing the description or the Critical rules.
