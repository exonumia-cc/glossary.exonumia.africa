# Bitcoin Glossary

A multilingual dictionary of Bitcoin, Lightning and mobile money terminology, published at
[glossary.exonumia.africa](https://glossary.exonumia.africa). Every term occupies one row, with
a dedicated column per language, so translations can be read and compared side by side.

Currently **359 terms** across **14 categories** in **4 languages** — English, Gĩkũyũ, Kiswahili
and Soomaali.

A collaborative initiative by a collective of Translators, Localization Labs, HRF, and
exonumia.africa. Translations are community contributions and remain a work in progress.

## Running it

Static HTML, CSS and JavaScript — no build step, no dependencies, no framework. It does need to
be served over HTTP, because the page fetches the JSON files under `i18n/` and browsers block
that on `file://` URLs.

```bash
python3 -m http.server 4173
```

Then open <http://localhost:4173>. Deployment is a plain upload of the repository root to any
static host.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Page shell — masthead, toolbar, sidebar, footer |
| `styles.css` | Dictionary theme, light and dark, responsive |
| `app.js` | Loads the JSON, builds the model, renders and filters |
| `i18n/manifest.json` | Lists the language codes, in column order |
| `i18n/<code>.json` | One file per language — the data that changes when a translation lands |
| `conversion-script.py` | Turns the translators' CSV exports into the `i18n/` files |
| `tests/` | Unittest suite asserting the documented data claims and helper behavior |
| `.claude/skills/glossary-localization/` | Self-contained agent skill teaching LLM coding agents to localize with this glossary — `SKILL.md`, the termbase helper in `scripts/glossary.py` (lookup, text scan, reverse lookup), and `references/eval-plan.md` |

## The data

Each language lives in its own file, `i18n/<code>.json`, keyed by category, then a list of
entries. `i18n/manifest.json` holds the language codes in the order the columns should appear:

```json
["en", "ki", "sw", "so"]
```

```json
{
  "concepts": [
    {
      "key": "bitcoin",
      "term": "Bitcoin",
      "explanation": "A decentralized digital money network that works without banks or governments.",
      "notes": "Distinguish network vs currency carefully."
    }
  ]
}
```

`key` is the slugified English term and is what pairs a row across languages — `Two-Factor
Authentication (2FA)` becomes `two-factor-authentication-2fa`. Keys are unique within a category
and, as it happens, across the whole file. `notes` is translator guidance rather than reader-facing
copy; it is frequently empty and always present as a string.

A language may omit an entry it has not translated yet. The page renders "— not yet translated"
in that cell and keeps the row aligned.

## Adding a language

1. **Export the sheet as CSV.** Each language is one sheet from the shared hypertranslation
   drive, with this column layout:

   | | Category | English Term | Explanation | Notes | Term in *lang* | Explanation in *lang* | Notes |
   |---|---|---|---|---|---|---|---|

   The first column is blank, row 1 is blank, row 2 is the header. Columns are read by position,
   so the exact wording of the header does not matter.

2. **Regenerate the JSON**, passing *every* sheet — the files are rebuilt from scratch each time,
   not patched:

   ```bash
   python3 conversion-script.py i18n \
     ki="Glossary - Kikuyu SHARED - All.csv" \
     sw="Glossary - Swahili (Kiswahili) - Complete.csv" \
     so="Glossary - Somali (Af-Soomaali) - Complete.csv" \
     xx="Glossary - Your Language - Complete.csv"
   ```

   Use the [ISO 639-1 code](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) for
   `xx`. English is derived from the first sheet listed; later sheets are checked against it and
   any disagreement in the English columns is reported rather than silently overwritten.

   The script prints a per-language coverage table and warns about duplicate keys, untranslated
   rows, and rows missing a category or English term. **Read the warnings** — a partially filled
   sheet still produces valid output, so nothing forces you to notice the gaps.

   Then run the test suite — it asserts the documented counts and category slugs against the
   regenerated files, so a regeneration that changes them fails loudly instead of letting the
   docs drift:

   ```bash
   python3 -m unittest discover -s tests
   ```

3. **Check the display name.** `LANG_META` at the top of `app.js` maps codes to the names shown
   in the column header and filter chip, and carries `dir: 'rtl'` where needed. It already covers
   `en ki sw so am ha yo ig zu xh st tn sn ln lg wo af fr pt ar`. An unlisted code still renders —
   it just falls back to showing the bare code.

No other change is needed. The page discovers its languages from `i18n/manifest.json` and adds a
column and a filter chip automatically.

## Adding or renaming a category

Category keys are slugified from the CSV's Category column, with `Bitcoin Concepts` collapsed to
`concepts` via `CATEGORY_KEYS` in `conversion-script.py`. Because the JSON stores only the slug,
the human-readable label lives in `CATEGORY_LABELS` in `app.js` — a new category renders with a
title-cased slug until you add a label there.

## How the page works

- **Language filter** — chips toggle columns on and off. The last visible language cannot be
  switched off. The preference records which languages are *hidden*, not which are shown, so a
  language added later appears for returning visitors instead of staying buried.
- **Search** — matches across every visible language's term, explanation and notes at once.
  Diacritic-insensitive with match highlighting, so `gutuma` finds and highlights `gũtũma`.
  Multiple words are ANDed.
- **Categories** — the sidebar and the toolbar select both filter, and show live match counts.
  The sidebar can be collapsed with the toolbar's panel button, which gives the columns more room.
- **Deep links** — `#<category>/<key>`, e.g. `#security/seed-phrase`, jumps to and highlights an
  entry, clearing filters if it is currently hidden. Hovering a row reveals a `§` permalink.
- **Keyboard** — `/` focuses search, `Escape` clears it.
- Theme, language and sidebar choices persist under the `exonumia-` prefix in `localStorage`.

## Tests

```bash
python3 -m unittest discover -s tests
```

Stdlib `unittest`, no dependencies. `tests/test_glossary_data.py` asserts the factual claims
this README and the agent skill make about the data (term count, category slugs, language
alignment, entry shape) and tracks data hygiene — multi-variant (`/`) and trailing-period
term fields may only ever shrink. `tests/test_glossary.py` unit-tests the skill's helper
(`.claude/skills/glossary-localization/scripts/glossary.py`)
against a synthetic fixture that includes a deliberately untranslated entry, a gap the real
data does not currently exercise.

## Deploying

Everything is static, so any host will do. One caveat: `app.js` and `styles.css` are referenced
without a version query, so a host with long cache lifetimes can serve a returning visitor stale
JavaScript against a freshly updated `i18n/` directory. Either keep cache headers short for those
two files or add a cache-busting query when you deploy.
