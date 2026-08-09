#!/usr/bin/env python3
"""Build glossary.json from one hypertranslation sheet per language.

Each sheet is a CSV exported from the shared drive with the layout:

    ['', Category, English Term, Explanation, Notes,
     Term in <lang>, Explanation in <lang>, Notes]

The English side is taken from the first sheet listed; later sheets are checked
against it and any disagreement is reported rather than silently overwritten.

Usage:
    conversion-script.py OUTPUT.json CODE=SHEET.csv [CODE=SHEET.csv ...]

Example:
    conversion-script.py glossary.json \\
        ki="Glossary - Kikuyu SHARED - All.csv" \\
        sw="Glossary - Swahili (Kiswahili) - Complete.csv"
"""

import csv
import json
import re
import sys
from collections import OrderedDict

COL_CATEGORY, COL_EN_TERM, COL_EN_EXP, COL_EN_NOTES = 1, 2, 3, 4
COL_TERM, COL_EXP, COL_NOTES = 5, 6, 7

# Category label -> JSON key. "Bitcoin Concepts" collapses to "concepts";
# everything else is slugified from the label.
CATEGORY_KEYS = {"Bitcoin Concepts": "concepts"}

warnings = []


def warn(message):
    warnings.append(message)


def clean(value):
    """Trim, collapse whitespace runs (incl. embedded newlines), normalise quotes."""
    if value is None:
        return ""
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def slug(text):
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def read_sheet(code, path):
    """Return [{category, key, en:{...}, tr:{...}}] in sheet order."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))

    if len(rows) < 3 or clean(rows[1][COL_EN_TERM]) != "English Term":
        warn("%s: unexpected header %r — column positions assumed anyway"
             % (code, rows[1] if len(rows) > 1 else rows))

    records, seen = [], {}
    for lineno, row in enumerate(rows, start=1):
        if lineno <= 2:  # leading blank line, then the header
            continue
        row = row + [""] * (8 - len(row))

        category = clean(row[COL_CATEGORY])
        en_term = clean(row[COL_EN_TERM])
        if not category and not en_term:
            continue
        if not category or not en_term:
            warn("%s line %d: missing category or English term — skipped" % (code, lineno))
            continue

        cat = CATEGORY_KEYS.get(category, slug(category))
        key = slug(en_term)
        if (cat, key) in seen:
            warn("%s line %d: duplicate key '%s.%s' (first seen line %d) — suffixed"
                 % (code, lineno, cat, key, seen[(cat, key)]))
            n = 2
            while (cat, "%s-%d" % (key, n)) in seen:
                n += 1
            key = "%s-%d" % (key, n)
        seen[(cat, key)] = lineno

        term = clean(row[COL_TERM])
        if not term:
            warn("%s line %d: '%s' has no %s term — entry omitted from %s"
                 % (code, lineno, en_term, code, code))

        records.append({
            "category": cat,
            "category_label": category,
            "key": key,
            "en": {
                "key": key,
                "term": en_term,
                "explanation": clean(row[COL_EN_EXP]),
                "notes": clean(row[COL_EN_NOTES]),
            },
            "tr": {
                "key": key,
                "term": term,
                "explanation": clean(row[COL_EXP]),
                "notes": clean(row[COL_NOTES]),
            } if term else None,
        })

    return records


def main(argv):
    if len(argv) < 3 or "=" not in "".join(argv[2:]):
        sys.exit(__doc__)

    dest = argv[1]
    sheets = []
    for arg in argv[2:]:
        code, _, path = arg.partition("=")
        if not code or not path:
            sys.exit("expected CODE=SHEET.csv, got %r" % arg)
        sheets.append((code, path))

    languages = OrderedDict([("en", OrderedDict())])
    category_labels = OrderedDict()
    base = OrderedDict()   # (cat, key) -> English entry, from the first sheet

    for code, path in sheets:
        languages[code] = OrderedDict()
        for record in read_sheet(code, path):
            cat, key = record["category"], record["key"]
            category_labels.setdefault(cat, record["category_label"])

            if (cat, key) not in base:
                base[(cat, key)] = record["en"]
                languages["en"].setdefault(cat, []).append(record["en"])
            else:
                for field in ("term", "explanation", "notes"):
                    if base[(cat, key)][field] != record["en"][field]:
                        warn("%s: English %s differs for '%s.%s' — kept the first sheet's\n"
                             "      kept: %s\n      %*s: %s"
                             % (code, field, cat, key, base[(cat, key)][field],
                                4, code, record["en"][field]))

            if record["tr"]:
                languages[code].setdefault(cat, []).append(record["tr"])

    # Keep every language's categories in the English order.
    order = list(languages["en"].keys())
    for code in languages:
        languages[code] = OrderedDict(
            (cat, languages[code][cat]) for cat in order if cat in languages[code]
        )

    for code in languages:
        if code == "en":
            continue
        missing = len(base) - sum(len(v) for v in languages[code].values())
        if missing:
            warn("%s: %d of %d entries untranslated" % (code, missing, len(base)))

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(languages, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print("wrote %s: %d entries across %d categories in %d languages (%s)"
          % (dest, len(base), len(order), len(languages), ", ".join(languages)))
    header = "  %-20s %s" % ("category", "  ".join("%4s" % c for c in languages))
    print(header)
    for cat in order:
        counts = "  ".join("%4d" % len(languages[c].get(cat, [])) for c in languages)
        print("  %-20s %s   (%s)" % (cat, counts, category_labels[cat]))

    if warnings:
        print("\n%d warning(s):" % len(warnings))
        for w in warnings:
            print("  " + w)


if __name__ == "__main__":
    main(sys.argv)
