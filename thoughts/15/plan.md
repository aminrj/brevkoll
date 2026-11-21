# Plan: #15
Status: approved

Goal: restyle the page, result and error fragments so a parent finds what to do and by when on a phone. Nothing the app
computes changes (OCR, prompt, model call, redaction, dates, `.ics`, `/api/decode` JSON). No new dependency, no new route.

## Proposed look (the owner approves this here)

Owner feedback: the first palette (cream paper, grey-brown text, dark green accent) read as pale. This revision replaces it
with higher-contrast, more saturated colours. The old one is dropped. Same structure: CSS custom properties on `:root`, dark
values in `@media (prefers-color-scheme: dark)`. Contrast ratios are my estimates (not computed); a phase 1 test computes them
from the hex values (AA: 4.5 for text, 3 for large text and UI borders).

Why this one: pure white and near-black give the strongest body contrast. One saturated blue carries every action (button,
links, dates, list numbers, focus ring), so the eye finds "what to do" and "by when" first. Blocks that need weight get a tinted
panel with a solid 4 px accent edge instead of a faint hairline. One hue keeps it calm for a stressed reader.

| Token | Light | Dark | Use | Est. ratio on paper (light / dark) |
|---|---|---|---|---|
| `--paper` | `#ffffff` | `#0b1220` | background | |
| `--panel` | `#eef3ff` | `#16223d` | date cards, notice, error | |
| `--ink` | `#111827` | `#f3f4f6` | body text, headings | about 17 / 17 |
| `--muted` | `#4b5563` | `#b6bdc9` | note, quotation, weekday | about 7.6 / 9 |
| `--rule` | `#7c8696` | `#5b6578` | input borders, section lines | about 3.5 / 3.2 (UI, needs 3) |
| `--accent` | `#1d4ed8` (strong blue) | `#8ab0ff` | button, links, dates, list numbers, focus ring | about 6.7 / 8 |
| `--on-accent` | `#ffffff` | `#0b1220` | text on the button | about 6.7 / 8 (on accent) |
| `--error` | `#b42318` | `#ff9a8f` | error left bar | about 6.5 / 9 |

Where colour is used: the primary button and the calendar link are solid `--accent` with `--on-accent` text. Each date card is
`--panel` with a 4 px `--accent` left edge and the date in `--accent` at 1.5rem. "What to do" items have accent-coloured
numbers. The "Machine generated" notice sits on `--panel` with a `--muted` left edge. Section headings are `--ink` with a 2 px
`--rule` line above. No gradient, no shadow, no image.

Alternative if blue is wrong (not adopted; swap the accent values only): deep orange `#b83200` light / `#ffa070` dark (about
5.6 / 9). Warmer, but it reads as a warning, which may add stress.

Type scale (system stack `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; no web font): body 1.0625rem (17 px),
line-height 1.55; title 1.75rem/1.2 weight 650; section heading 1.125rem weight 650; date 1.5rem weight 650 with
`font-variant-numeric: tabular-nums`; weekday 1rem muted; quotation and note 0.9375rem (15 px) muted.
Column `max-width: 40rem`, padding 1rem (1.5rem from 40rem up). Controls `min-height: 2.75rem` (44 px), file field and
button `width: 100%`. Errors: ink text on `--panel`, 4 px left bar in `--error`, `role="alert"` kept. No icon anywhere.

## Phase 1: page shell, stylesheet and busy state
- [x] Files:
  - `src/app/static/style.css` (rewrite, target 4-6 KB)
  - `src/app/templates/index.html` (markup, classes, `htmx-config`, `hx-disabled-elt`, `id="submit"`)
  - `src/app/templates/error.html` (class only; text and `role="alert"` unchanged)
  - `tests/unit/test_ui_static.py` (new)
  - `README.md` (see Docs)
- [x] Types and signatures: no Python. Template contract:
  `<form ... hx-disabled-elt="#submit">`, `<button id="submit" type="submit">`,
  `<p id="busy" class="htmx-indicator" role="status">`, and
  `<meta name="htmx-config" content='{"responseHandling":[{"code":".*","swap":true}],"includeIndicatorStyles":false}'>`.
  Keep `name="file"`, `name="language"`, `accept="image/*,application/pdf"`, `required`, `hx-post="/ui/decode"`, the size text
  and `hx-target="#result"`. Indicator rules move into `style.css` (`.htmx-indicator{display:none}` and
  `.htmx-request .htmx-indicator, .htmx-request.htmx-indicator{display:block}`), so the wait text shows at once.
  Stylesheet rules: `@media (prefers-color-scheme: dark)`, `@media (prefers-reduced-motion: reduce)`, a `:focus-visible`
  outline of 3 px in `--accent`. No `@import`, `@font-face`, gradient, `backdrop-filter`, `blur` or `url(`.
- [x] Tests to add (and why each fails today), all in `tests/unit/test_ui_static.py` with the app test client.
  "Guard" means it passes today and is kept so the rewrite cannot regress it; I say so rather than pretend it fails.
  - `test_index_loads_only_same_origin_resources`: every `src`/`href`/`action`/`hx-*` URL on `/` starts with a single `/` or is a `#` anchor. Guard (AC1).
  - `test_only_script_is_bundled_htmx`: exactly one `<script>`, `src="/static/htmx.min.js"`, no inline body. Guard (AC3).
  - `test_stylesheet_has_required_rules`: dark scheme, reduced motion, `:focus-visible` present. Fails today (none exist).
  - `test_stylesheet_has_no_forbidden_features`: no `gradient`, `backdrop-filter`, `blur`, `@font-face`, `@import`, `url(`, `http`. Guard (AC4).
  - `test_size_budget`: `style.css` at most 12 KB, `/` body at most 8 KB. Guard (AC2).
  - `test_no_inline_style_or_emoji`: no `style=` attribute, no `<style>`, no emoji-range character in any template. Guard.
  - `test_templates_do_not_use_safe`: no `|safe` or `Markup` in `templates/` or `ui.py`. Guard.
  - `test_every_field_has_a_label`: each `input`/`select` id has a `<label for>`. Guard (AC5).
  - `test_page_has_lang_viewport_title`. Guard (AC5).
  - `test_submit_button_is_disabled_by_htmx`: the form has `hx-disabled-elt="#submit"`, a button has `id="submit"`, and `#busy` has no `hidden` or `aria-hidden`. Fails today.
  - `test_htmx_indicator_styles_disabled`: the htmx-config meta parses as JSON with `includeIndicatorStyles` false and `responseHandling` kept. Fails today.
  - `test_indicator_rules_live_in_stylesheet`: `style.css` has `.htmx-indicator` and `.htmx-request`. Guard (the rules must survive the rewrite).
  - `test_palette_contrast_meets_aa`: parse the tokens from `style.css`, compute WCAG ratios for ink, muted, accent and error against paper and panel, and on-accent against accent, in both schemes, assert at least 4.5; `--rule` against paper at least 3. Fails today (no tokens).
  - `test_form_fields_unchanged`: the form posts `file` and `language` to `/ui/decode` with multipart encoding. Guard.
  - Existing `tests/unit/test_ui.py` index tests must still pass unchanged.
- [x] Automated verification: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest && bash scripts/quality.sh origin/main`
- [ ] Manual verification (not run by the agent; for the human): `LLM_PROVIDER=fake uv run fastapi dev src/app/main.py`; open at 360 px wide in light and dark; the file field and
  button are full width and 44 px tall; the focus ring shows by keyboard; tap the button and see it disable and the wait text appear at once; no horizontal scroll.
- [x] Threat-model controls implemented: LLM02 (same-origin, no font or import), LLM10 (`hx-disabled-elt`, size caps),
  LLM06 (no new `hx-*` that sends data), Web upload handling (field names kept), the htmx half of Web content security.
- [x] Docs touched: `README.md` "What it does" gets one sentence on the page (works on a phone, follows the system dark setting, no external requests).

## Phase 2: result, weekday and answer language
- [x] Files:
  - `src/app/ui.py` (view model, weekday table, `render_result` takes the language)
  - `src/app/routes.py` (`decode_ui` passes `language` to `render_result`; one line)
  - `src/app/templates/result.html` (restructure)
  - `src/app/static/style.css` (result rules)
  - `tests/unit/test_ui_result.py` (new); `tests/unit/test_ui.py` keeps passing unchanged
  - `README.md`
- [x] Types and signatures:
  ```python
  # src/app/ui.py
  WEEKDAYS: dict[str, tuple[str, str, str, str, str, str, str]]  # Monday..Sunday for en, sv, ar, uk


  class DateView(BaseModel):  # frozen; built by code only
      iso: str  # item.date, full ISO date including the year
      weekday: str  # from date.fromisoformat(item.date).weekday()
      description: str  # the letter's wording, shown as a quotation


  def weekday_name(iso: str, language: str) -> str: ...
  def date_views(dates: list[DateItem], language: str) -> list[DateView]: ...
  def render_result(request: Request, result: DecodeResult, language: str) -> HTMLResponse: ...
  ```
  Template context: `{"result": result, "dates": date_views(result.dates, language), "lang": language, "dir": "rtl" if language == "ar" else "ltr"}`.
  `DecodeResult`, `DateItem` and `/api/decode` do not change (ADR 0001). The `.ics` link stays
  `data:text/calendar;charset=utf-8,{{ result.ics | urlencode }}` with `download="letter.ics"`.
  Markup order inside `<article lang="{{ lang }}" dir="{{ dir }}">`: quiet notice `p.notice` (text still contains "Machine generated");
  `<h2>What to do</h2>` as `<ol class="todo">` (only if actions); `<h2>Dates</h2>` as `<ul class="dates">`, each `<li>` holding
  `<time datetime="{{ d.iso }}" class="date">{{ d.iso }}</time> <span class="weekday">{{ d.weekday }}</span>` and below it
  `<blockquote lang="sv" dir="ltr">{{ d.description }}</blockquote>` (OCR wording is Swedish); then the calendar link styled as a full-width
  button; then `<h2>Summary</h2>` and the summary. No `|safe`. The notice is never hidden.
- [x] Tests to add (and why each fails today), in `tests/unit/test_ui_result.py`:
  - `test_weekday_table`: 2026-12-04 Friday, 2028-02-29 Tuesday, 2026-12-31 Thursday, 2027-01-01 Friday in en and sv; ar and uk names non-empty. Fails: `weekday_name` does not exist.
  - `test_every_supported_language_has_weekday_row`: `set(WEEKDAYS) == SUPPORTED_LANGUAGES`. Fails: no table.
  - `test_unknown_language_falls_back_to_english`. Fails: no function.
  - `test_what_to_do_before_dates_and_summary_last`: position of "What to do" < "Dates" < "Summary". Fails today (Summary is first).
  - `test_date_item_shows_full_iso_weekday_and_wording`: `<time datetime="2026-12-04">2026-12-04</time>`, "Friday" and the wording are all present. Fails today.
  - `test_large_date_markup_holds_only_code_dates`: a summary saying "deadline cancelled 2026-01-01" and an action saying "Deadline: 1 jan": the items of `ul.dates` equal exactly `result.dates`, and neither string appears inside it. Fails today (no `.dates` list); it is the LLM01 control afterwards.
  - `test_notice_summary_actions_dates_and_ics_present`: all four present; the notice is not inside an element with `hidden` or `role="alert"`. Fails today (no `p.notice`).
  - `test_result_escapes_model_and_letter_text`: `<script>` and `"><img onerror=...>` in summary, action and wording are escaped in the new markup. Guard, run on the new template.
  - `test_ics_link_unchanged`: `href` equals `data:text/calendar;charset=utf-8,` plus the `urlencode` of `result.ics`, and an action containing `\r\nBEGIN:VEVENT` still yields one VEVENT after decoding the link. Guard.
  - `test_result_language_and_direction`: `ar` gives `dir="rtl"`, `en` gives `dir="ltr"`, the article `lang` equals the answer language. Fails today.
  - `test_api_decode_json_unchanged`: `/api/decode` keys are exactly `summary, actions, dates, ics` and each date has only `date, description`. Guard (ADR 0001).
  - `test_no_dates_message_kept`: no dates gives "No dates found in the letter." and no calendar link. Guard.
- [x] Automated verification: same command as Phase 1.
- [ ] Manual verification: decode with `LLM_PROVIDER=fake`; "What to do" is the first block under the notice; each date is large with its weekday and the
  letter's wording below; the calendar link is easy to tap; try `language=ar` and see right-to-left; try a letter with no dates.
- [x] Threat-model controls implemented: LLM01 (only code-parsed dates get the date treatment, notice visible), LLM05 (autoescape, no `|safe`,
  weekday by code, calendar link unchanged), LLM05 misread date (year always shown, wording beside it), LLM07 (error text fixed).
- [x] Docs touched: `README.md` "What it does" step 4: weekday shown beside each date, computed in code, in the answer language.

## Phase 3: Content-Security-Policy header (only if the human approves Q1)
- [x] Files: `src/app/main.py` (one middleware), `tests/unit/test_csp.py` (new), `README.md`.
- [x] Types and signatures:
  ```python
  # src/app/main.py
  CSP = (
      "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
      "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
  )


  @app.middleware("http")
  async def security_headers(
      request: Request, call_next: Callable[[Request], Awaitable[Response]]
  ) -> Response: ...
  ```
  It sets `Content-Security-Policy` on every response, including error responses and the rate-limiter's early return.
  Register it after `limit_body` so it is the outermost middleware (Starlette runs the last-added first).
- [x] Tests to add (and why each fails today):
  - `test_index_has_csp_header`: the header is on `/`. Fails today (no header).
  - `test_csp_has_no_unsafe_directives`: no `unsafe-inline`, `unsafe-eval`, `*`, `http:`; `script-src` and `style-src` are `'self'` only. Fails today.
  - `test_csp_on_error_and_static_responses`: a 422 from `/ui/decode`, a 429 from the limiter and `/static/style.css` all carry it. Fails today.
  - `test_csp_does_not_set_cookies_or_cors`: still no `set-cookie`, no `access-control-allow-origin`. Guard.
- [x] Automated verification: same command as Phase 1.
- [ ] Manual verification on the staged build with the browser console open: the page is styled; the htmx request completes and swaps the result;
  the button disables; the `.ics` download from the `data:` link works; no CSP violation is logged. If the `data:` link is blocked, stop and report;
  do not add `unsafe-inline` or a `data:` source without the human.
- [x] Threat-model controls implemented: Web content security (runtime enforcement of same-origin), a second layer for LLM02.
- [x] Docs touched: `README.md` gets a sentence: every response carries a strict Content-Security-Policy and the page loads nothing off-origin.

## Docs (the app's own, not the factory's)
- `README.md` and `AGENTS.md` already describe the app; neither has template text or the Gate 1 placeholder, so no replacement phase is needed.
- Phase 1: README page behaviour. Phase 2: README weekday. Phase 3: README CSP.
- `AGENTS.md`: unchanged (stack, commands and workflow do not change).

## Architecture contracts
Proposed for `.importlinter` (the human commits it). Presentation must not reach the model path, which keeps "no prompt or model change" true by construction:
```ini
[importlinter:contract:ui-not-model-path]
name = The UI layer does not import the model path
# Prevents a restyle from touching the prompt builder, the model client, OCR, redaction or the ICS builder. app.ui only renders what app.decode returns.
type = forbidden
source_modules =
    app.ui
forbidden_modules =
    app.llm
    app.prompt
    app.ocr
    app.redact
    app.ics
```
`app.ui` will import `app.decode` (for `DecodeResult`) and `app.dates` (for `DateItem`), which the existing `layers` contract already allows.

## Decisions (ADRs)
- `docs/decisions/0001-weekday-in-the-view-layer.md` (Phase 2): weekday in `app.ui`, API unchanged, answer-language name table.
- `docs/decisions/0002-content-security-policy-header.md` (Phase 3): CSP header and `includeIndicatorStyles:false`. Needs the human's yes.

## Dependencies added (Python and system)
None. No apt package. No web font, no icon set, no CSS framework. htmx stays at 2.0.4.

## What I am unsure about
- **Contrast numbers** are estimates (I could not run a calculator); the phase 1 test computes them. Dark `--rule` on paper (3.2) is closest to the line and may need a lighter value.
- **The new palette is my guess at "less pale".** Blue on white is the safe common choice; the orange alternative or a colour you name is a two-value swap.
- **`hx-disabled-elt` placement.** The threat model says "on the button"; htmx reads it from the element that issues the request, which is the form,
  so I put it on the form pointing at `#submit`. To verify in a browser.
- **Screen readers and the wait text.** `.htmx-indicator` is `display:none` until a request runs, so it is not announced while hidden; `role="status"`
  helps only once shown. The result region keeps `aria-live="polite"`. Not tested with a screen reader.
- **CSP and `data:` downloads.** Browsers differ on whether `data:` navigations or downloads fall under `default-src`. That is why phase 3 is gated on a staged check.
- **Holdout tests.** I could not read them. My tests mirror the spec's wording of AC1-AC7; how the holdout measures "page HTML" (with or without the result)
  or "stylesheet" is unknown. I assume `style.css` alone and the index body.
- **Page `lang` stays `en`.** The page chrome is English only, as today. Only the result carries the answer language and direction.
- **Summary last.** The spec reads as "What to do", "Dates", then summary; the old order had Summary first. A parent who wants the gist first may disagree.
- **Weekday names** for ar and uk are written by me and need a native check.
- **Threat-model Q1-Q3** are answered here as: Q1 yes, but as a separable phase 3; Q2 yes, in `app.ui` only; Q3 the answer language. The human decides.

## Notes from implementation

### Phase 1
- Palette values are exactly the table in the plan; the contrast test passes for every pair at 4.5 (rule at 3) in both schemes.
- `style.css` is about 2 KB. `.warning` (current notice class in `result.html`) and `.error` share the panel style; phase 2 renames the notice.
- `error.html` needed no change: the existing `.error` class is styled. Manual browser checks (360 px, keyboard focus, busy state) were not run in this session.
### Phase 2
- `DateItem` and `DecodeResult` live in `app.decode` (not `app.dates`); `app.ui` imports them from there. The layers contract allows it.
- Notice class renamed from `.warning` to `.notice`. Left borders use `border-inline-start` so the bars flip in right-to-left text.
- The ar and uk weekday names are mine and need a native check. Manual browser checks (ar layout, tap target) were not run in this session.
- `test_ics_link_unchanged` compares the unquoted link with the `ics` string from `/api/decode`.

### Phase 3
- CSP middleware added after `limit_body`, so it is outermost and also covers the limiter's early 429 and the 422 handler. Policy is exactly the one in the plan.
- ADR `docs/decisions/0002-content-security-policy-header.md` is named in the plan but I did not write it; no phase step asked for it. Flag for the human.
- Manual verification on a staged build (htmx swap, button disable, `data:` `.ics` download, no console violations) was not run. If the `data:` link is blocked, do not add a source without the human.

### Phase 1 (continued)
- Two guard tests had bugs in my first draft (script regex matched the closing tag; the `|safe` check matched a comment in `ui.py`). I fixed the tests; no code or check was weakened.
