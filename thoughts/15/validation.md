# Validation: #15

Re-run after the theme-switch rework (b3453a4, implement 0799030), on top of the two earlier reworks (c2f96d0, 66a7970).
Checks on `agent/issue-15`: `uv run pytest` 204 passed, 1 skipped; `ruff check` and `ruff format --check` clean; `pyright` 0 errors;
`scripts/quality.sh origin/main`: import contracts 6 kept, traceability 8 criteria found in tests, context size OK.
The skip is `tests/integration/test_tesseract.py` (no tesseract binary on this host), not added by this branch.
I read only the tail of the quality output.

## New since the last validation (theme switch)

- `index.html` gets a CSS-only checkbox `#theme` labelled "Switch dark / light" (no script). `style.css` inverts the palette with
  `:root:has(#theme:checked)` inside both `prefers-color-scheme` blocks. One test added: `test_theme_switch_is_script_free_checkbox`.
- Not in the approved plan, which says only "follows the system dark setting". It is a third rework on top of the palette deviation below.
- **The contrast test is weaker than it looks.** `schemes()` (`tests/unit/test_ui_static.py:156`) splits the CSS at the first
  `prefers-color-scheme: dark` and builds one dict per half with `re.findall`, so later duplicates overwrite earlier ones. The "dark" half
  resolves to the last block (`@media light` with `:checked`, which holds the dark palette). The light-valued override inside the dark
  media block and the `:not(:has(...))` dark block are never checked on their own. The values are identical copies today, so the ratios
  hold, but an edit to one copy would not be caught. The palette now appears three times in `style.css`.
- The new test checks only that the checkbox exists and one selector string is in the CSS. Nothing tests that checking it flips the
  scheme, and no browser check was run.
- Behaviour to look at: the choice is not remembered (resets on reload); `:has()` is required (browsers without it ignore the toggle but
  keep the system scheme); the checkbox is visually hidden but focusable, with the focus ring on the label; the label does not say which
  mode is active. The checkbox is outside the form and has no `name`, so it sends nothing.
- No new request, script, URL or dependency, so the LLM02 and CSP controls are unaffected. The toggle label is about 1.75 rem tall, under
  the plan's 44 px control height; it is a secondary control, but it is a small tap target on a phone.

## Phases complete

- Phase 1 (shell, stylesheet, busy state): done in code and tests. Manual box unchecked.
- Phase 2 (result, weekday, answer language): done. Manual box unchecked.
- Phase 3 (CSP header): done. Manual box unchecked.
- The rework commits are not a plan phase; see deviations.

## Deviations from the plan

- **Palette replaced.** The plan's "Proposed look" table (white/blue, `#1d4ed8`) was approved. The rework switched `style.css` to a warm
  cream and teal palette (`--paper #fbf6ee`, `--accent #0b5d5a`, dark `--accent #72d3ca`) and added a `--card` token. The plan was not updated.
  The contrast test still passes with the new values (I did not read how it treats `--card`).
- **Plan says "No gradient, no shadow, no image" and "No icon anywhere".** `.card` now has `box-shadow: 0 2px 0 var(--rule)` (a hard
  offset, not a blur). A `.mark` brand badge (a letter "b" in a circle, `aria-hidden`) was added. It is text, not an image, but is a visual
  mark the plan excluded.
- **Plan layout rules changed:** date cards now stack weekday above date (plan: date then weekday on one line); the date has a 6 px edge
  (plan: 4 px); headings are accent-coloured with no top rule (plan: `--ink` with a 2 px `--rule` line); controls are taller (3.25 rem button).
- **Copy changed** (not specified in the plan): hero text ("Not sure what that letter says?"), tagline "Swedish letters, made clear", button
  "Read my letter" (was "Decode letter"), calendar link "Add the dates to my calendar (.ics)", numbered step labels, a longer privacy note.
  "Machine generated" notice text is kept. The size text "up to 10 MB" is kept, now in a separate hint paragraph rather than the label.
- The hero says "No account, no waiting room" and the note says "Private by design". These are claims in user-facing copy; the first is
  true of the code I saw, the second is stronger than the plan's wording ("Nothing is stored on the server"). The human should approve the wording.
- ADR 0002 now exists; the plan's implementation note saying it was not written is stale. I did not review the ADR text.
- Proposed `ui-not-model-path` contract is not in `.importlinter` (human-owned), so it is not enforced by a guard.
- Plan status is `approved`, but the threat model is still `Status: DRAFT`; I cannot confirm from the repo that Q1 (CSP) was approved.
- `tests/holdout/test_ui.py` is in the branch diff from the Gate 1 commit; I did not read it.
- `thoughts/15/issue.md` has an uncommitted modification; I left it alone (treated as data).

## Threat-model controls without an enforcing test

I checked by plan and test names, not by reading every test body.

- LLM01, LLM02, LLM05, LLM06, LLM07, LLM10, upload fields and CSP each map to a named test in `test_ui_static.py`, `test_ui_result.py`
  or `test_csp.py`. Those tests still pass after the rework, so the new markup keeps: only code-parsed dates in `ul.dates`, escaping, visible
  notice, unchanged `.ics` link, same-origin resources.
- Gap: the threat model says `hx-disabled-elt="this"` on the button; the plan moved it to the form pointing at `#submit`. A test checks the attribute; nothing proves in a browser that the button disables.
- Gap: the same-origin URL scan runs on `/` only, not on the result or error fragments.
- Gap: the `data:` `.ics` link under CSP is browser-only and untested.
- Existing rate limit, budget, CSRF, SSRF and route-allowlist controls rely on tests from #1.

## Weakened checks

None found. A search of `src/` and `tests/unit/` for `type: ignore`, `cast(`, `noqa`, `xfail`, `skip`, bare `except` and `except Exception`
found only an unrelated test name (`test_yearless_leap_day_skips_to_leap_year`). No test file changed in the rework commits.

## Docs

- `README.md` describes brevkoll, has no template text or placeholder, and its run command (`LLM_PROVIDER=fake uv run fastapi dev src/app/main.py`) matches AGENTS.md.
  The rework did not touch README; it does not mention the new look, which is fine.
- Env vars read in `src/app/config.py` are all in the README table with matching defaults (carried from the first validation; config was not changed since).
- README points to `thoughts/1/` for the spec, threat model and plan; this issue's are in `thoughts/15/`. Minor.
- `AGENTS.md` "What this repo is" is a real paragraph. Python 3.12 matches `requires-python >=3.12` and pyright `pythonVersion = "3.12"`
  (the local venv runs 3.13, which is fine).

## Needs human attention

1. Decide whether the rework palette, look and theme switch replace the approved plan table. If yes, update the plan; if no, revert the rework commits.
   If the switch stays, consider a test that parses each palette copy separately, and a way to remember the choice.
2. Approve the new user-facing copy, especially "No account, no waiting room" and "Private by design".
3. Manual browser checks are still not run: 360 px light and dark, focus ring, busy state, `ar` right-to-left (the new `inset-inline-start` list numbers and the stacked date cards), and the CSP with the `data:` download. If the `data:` link is blocked, do not add a source without a decision.
4. Confirm Q1 (CSP) approval and update the threat-model status.
5. Commit the `ui-not-model-path` contract to `.importlinter` if wanted.
6. Native check of the Arabic and Ukrainian weekday names.
7. Summary now comes after "What to do" and "Dates"; a parent may want the gist first.
