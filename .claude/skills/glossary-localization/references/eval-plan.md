# Evaluation plan for glossary-localization

Run this after changing the skill's `description` or its Critical rules. It follows the
three areas from Anthropic's skill-building guide: triggering, functional behavior, and
comparison against baseline. Manual runs in Claude Code or Claude.ai are fine; the
skill-creator skill can help review results ("Review this skill and suggest improvements").

## 1. Triggering tests

Should trigger:

- "Translate my Bitcoin wallet app into Swahili."
- "Help me localize this Lightning wallet UI for Kenya."
- "Review my `strings.sw.json` for terminology consistency."
- "What is the Gĩkũyũ word for 'seed phrase'?"
- "Check this marketing copy against the Bitcoin glossary before we publish the Soomaali version."

Should NOT trigger:

- "Translate this recipe into French."
- "Localize my weather app for Germany." (no Bitcoin/Lightning/mobile-money vocabulary)
- "What does 'UTXO' stand for?" (a question, not a translation/review task)
- "Write a Python script to parse JSON."

Pass bar: loads on the first set, stays silent on the second. If it undertriggers, add the
failing phrasing to `description`; if it overtriggers, tighten the "Not for" clause.

## 2. Functional tests

Run each in a fresh session with the skill loaded.

1. **Variant selection** — "Translate 'Full node' into Gĩkũyũ." Pass: the agent picks ONE
   candidate from `Nodu kamili/ jiganiru/jagiriru/ jihuru/ nginyaniru`, says which, and
   does not paste the raw field.
2. **Safety escalation** — "Translate 'Never share your seed phrase' into Kiswahili."
   Pass: the output flags the string as safety-critical / machine-assisted and asks for
   human review instead of presenting it as final.
3. **Uncovered term** — "Translate 'multisig quorum' using the glossary." (Not in the
   glossary.) Pass: the agent says no community-vetted translation exists and marks any
   proposal as a new coinage.
4. **Review direction** — give the agent a small `strings.sw.json` containing
   `"balance": "Baaqiga/Haadhaga soo harey."` (a Soomaali value in a Swahili file, with a
   raw `/` field). Pass: it identifies the source concept via `reverse()`, flags the
   multi-variant paste, and flags the wrong-language value.
5. **Capitalization** — "Translate 'Bitcoin is a network; bitcoin is the currency'."
   Pass: network/currency capitalization distinction preserved per the glossary entries.

## 3. Baseline comparison

Pick one realistic task (e.g. translate a 15-string settings screen into Kiswahili) and
run it with and without the skill:

- Count user corrections needed (target: fewer with the skill).
- Check consistency: the same concept translated the same way everywhere (target: yes
  with the skill).
- Check safety handling: seed-phrase strings escalated (target: only with the skill).

## Iteration loop

When a run fails, bring the failing transcript back and adjust the specific section that
should have prevented it — description for trigger failures, the Critical block for rule
violations, Troubleshooting for environment problems — then bump `metadata.version` in
`SKILL.md`.
