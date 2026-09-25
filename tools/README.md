# Tools

Python lives in the project virtual environment: `.venv/Scripts/python.exe` (Windows).

| Command | Purpose |
|---|---|
| `python tools/verify.py --all` | Full check of registers, chapters and model |
| `python tools/verify.py --claim C-0001` | Check one claim |
| `python tools/verify.py --hook` | Fast check used by the hooks |
| `python tools/verify.py --final` | Strictest check, run by the build |
| `python tools/extract.py S-001 --update-register` | Extract a stored source and record its hash and method |
| `python tools/extract.py --hash FILE` | SHA-256 of a file |
| `python tools/build.py` | Verify (final), assemble chapters, footnotes, DOCX and PDF |
| `python -m unittest discover -s tools/tests -v` | Test suite |

## Conventions the verifier enforces

- **Pages.** Extracted text marks pages with `=== PAGE n ===`. A claim's `page` is the physical page index of the stored file, as an integer or a range such as `"4-5"`. Put the printed page number in an optional `printed_page` field; the footnote uses it when present.
- **Quote matching** ignores differences in whitespace, line breaks, line-end hyphenation, ligatures, curly quotes and dash characters. Nothing else.
- **Equivalent value forms.** Only thousands separators (1,000 and 1000) and scale words of equal magnitude (13.2 billion and 13,200 million) count as the same value. Any rounding in the text must go through a derived claim with a `rounding` field. A claim may list extra display strings in `display`.
- **Table rows.** A claim may carry `quote_context`, a second verbatim string (typically a column header such as "Country fNRB (%)") that must appear on the same page; its units count for the unit checks.
- **Negative values** stated in words ("fell by 2.1 percent") need `sign_in_words: true` on the claim.
- **Sentence labels.** Claims with status `estimate` need "estimat..." in the sentence; `illustrative` needs "illustrative"; basis `projection` needs "projected", "projection" or "forecast"; basis `target` needs "target"; Tier 4 and 5 need attribution ("according to ..."); model outputs need "modelled estimate" or "scenario" plus the scenario name. In a table, the cell, the header row and a caption paragraph starting "Table" count as the sentence.
- **Executive summary** is any chapter whose file name contains `executive_summary`.
- **Chapter order** in the build follows file names, for example `00_executive_summary.md`, `01_part1_why.md`.
- **Final mode** also fails on pending or unconfirmed claims in chapters, on the text "I cannot confirm this", on claims not passed by the fact-checker, and on model outputs that depend on assumptions Hassan has not approved.
- **Hooks.** `.claude/settings.json` runs `tools/hook.py` through `.claude/hooks/run_hook.sh`, which finds a Python with PyYAML. The PostToolUse hook fires on the Write, Edit and MultiEdit tools only. Edits made through shell commands are caught by the Stop hook.
