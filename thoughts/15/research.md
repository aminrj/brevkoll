# Research: #15

Scope: UI refresh (restyle of the index page, result fragment, error fragment and stylesheet). Describes what exists today. No solutions. I did not read `tests/holdout/`, `.gitea/workflows/` or `.claude/settings.json`, per AGENTS.md; what the holdout tests check is known only from the spec's acceptance criteria.

## What exists

**Request flow.** `GET /` renders `index.html`. The form posts via htmx to `POST /ui/decode`. The route reads the upload (size limited), runs OCR, redacts the text, builds the prompt, calls the model, parses the output, finds dates in code, builds the `.ics`, and returns the `result.html` fragment. Errors return the `error.html` fragment with the matching status. The htmx config makes error responses swap into the page too (`index.html:6`).

**Pages and fragments.**
- `index.html` (1625 B) is the only full page. It has `lang="en"` (fixed, not tied to the answer language), a viewport meta tag, a title, one stylesheet link, and one `<script src="/static/htmx.min.js" defer>`. It has no inline script and no inline `style=`.
- The form has two labelled fields (`for="file"`, `for="language"`), `name="file"` with `accept="image/*,application/pdf" required`, and `name="language"`. It has a submit button and a wait paragraph `#busy.htmx-indicator` ("Reading the letter...") (`index.html:17-29`). A note says the text goes to the model and nothing is stored (`index.html:30`). The target is `<section id="result" aria-live="polite">`.
- The button has no `hx-disabled-elt`. Nothing disables it during a request today. `hx-indicator="#busy"` only shows the wait text, via CSS.
- `result.html` (744 B) is an `<article>` with this order: machine-generated notice (`p.warning`), Summary, "What to do" (only if actions exist), Dates. Dates are a `<ul>` of `<strong>{{ item.date }}</strong> <q>{{ item.description }}</q> <small>(from the letter)</small>`, then the `data:text/calendar` link with `download="letter.ics"`. If there are no dates it shows "No dates found in the letter." (`result.html:1-24`).
  - Today "What to do" comes after "Summary", and Dates is last. The spec wants "What to do" first.
- `error.html` (48 B) is `<p class="error" role="alert">{{ message }}</p>`.
- `style.css` (591 B, 9 lines) has a system-ui font and a 40rem column. It also has block display for label, input, select and button, the htmx indicator show/hide rules, and `.warning` (yellow, reads like an alert), `.error` and `.note` (`style.css:1-9`). It has no dark scheme, no reduced-motion rule, no focus rule, no gradients, no `@font-face`, no `@import`.
- `htmx.min.js` is vendored, 50,917 B, version 2.0.4 (`static/htmx.VERSION`). It is served by `StaticFiles` mounted at `/static` (`main.py:67`).

**Size budget today.** Stylesheet 591 B against a 12 KB cap. Index HTML 1625 B against an 8 KB cap. The htmx file is not counted in the stylesheet cap.

**Data the templates receive** (`decode.py:21-30`):
- `DecodeResult{summary: str, actions: list[str], dates: list[DateItem], ics: str}`.
- `DateItem{date: str (ISO yyyy-mm-dd), description: str}`.
- The date and description are built by code in `decode.py:56` from `find_dates` (`dates.py:101`). The description is the redacted, whitespace-collapsed OCR line, at most 120 characters (`dates.py:88-98`). Only `summary` and `actions` come from the model.
- No weekday exists anywhere in the code. `DateItem` carries no weekday, no language-specific name tables, and no locale handling. The only month-name table is Swedish input parsing in `dates.py:10-35`.
- The result is passed straight to the template as `{"result": result}` (`ui.py:29-30`). `render_error` passes `{"message": message}`.

**Rendering helpers** (`ui.py`). `_templates = Jinja2Templates(...)` autoescapes `.html`. The comment at `ui.py:16` says no template uses `|safe`. `LANGUAGE_NAMES` maps en, sv, ar, uk to their native names (`ui.py:14`). The index context is just `languages`. Arabic is among the answer languages, but the page has no `dir` handling and `lang` is fixed at `en`.

**Response headers.** `main.py` sets no security headers. There is no Content-Security-Policy, no `Set-Cookie`, no CORS. The only middleware is `limit_body` (rate limit and body size) at `main.py:69-83`. Exception handlers map `AppError`, validation errors and any other exception to `_error`, which renders the HTML fragment for `/ui/decode` and JSON elsewhere (`main.py:26-30`, `85-95`).

**htmx indicator styles.** htmx 2 injects its own indicator `<style>` unless `includeIndicatorStyles` is false. Today `index.html:6` does not set it, so the stock page already carries an htmx-injected inline style. I have not run the page to confirm this in a browser. It is a property of htmx 2.0.4 as documented.

## Relevant code (file:line)

| What | Where |
|---|---|
| Index page, form, wait text, result target | `src/app/templates/index.html:1-34` |
| Result fragment | `src/app/templates/result.html:1-24` |
| Error fragment, `role="alert"` | `src/app/templates/error.html:1` |
| Stylesheet | `src/app/static/style.css:1-9` |
| Template rendering, autoescape, language names | `src/app/ui.py:14-34` |
| UI routes (`/`, `/ui/decode`) | `src/app/routes.py:46-63` |
| Decode pipeline, `DecodeResult`, `DateItem` | `src/app/decode.py:21-57` |
| Date finding (code, not model) | `src/app/dates.py:46-106` |
| Static mount | `src/app/main.py:67` |
| Middleware, exception handlers (no headers set) | `src/app/main.py:69-95` |
| Existing UI tests | `tests/unit/test_ui.py:25-120` |

**Existing tests that touch the UI** (`tests/unit/test_ui.py`). They assert on literal strings in the current templates, so any copy change can break them:
- `'accept="image/*,application/pdf"'`, `'hx-post="/ui/decode"'`, and no `set-cookie` on the index.
- Each language `value="{code}"`.
- The result contains "Fake summary.", "Fake action.", "2026-12-04", "machine" (case-insensitive), "Anmäl senast" and no `<html` (a fragment).
- `'href="data:text/calendar'`, `BEGIN%3AVCALENDAR` and `download=` in the link.
- Escaping of `<script>` and `<img onerror>` in summary, action and letter wording.
- Errors: status 422, 415, 502, 429 and `Unsupported language.` text. Errors are HTML fragments.
- No test checks the order of "What to do" and "Dates", the stylesheet content, file sizes, the CSP header, `hx-disabled-elt`, or the weekday.

**Holdout tests exist** at `tests/holdout/test_acceptance.py` and `tests/holdout/test_ui.py`. I did not read them. The spec says AC1-AC7 each become a holdout test. A commit message (`dfbbfa2`) says OCR was added to CI for them.

**CI and quality tooling.** `scripts/quality.sh origin/main` runs the ratchet, changed-line coverage, import contracts, traceability and context size. `scripts/trace.py` and `scripts/health.py` mention "holdout". `.gitea/workflows/gates.yml` and `scripts/check-holdout-guard.sh` exist; I did not read the workflow. Dockerfile installs `tesseract-ocr`, `tesseract-ocr-swe` and `poppler-utils` (`Dockerfile:11`). `thoughts/1/` holds the original spec, threat model and plan; the threat model for #15 points at it for the controls that stay in force.

## Where untrusted input enters

On the path this issue touches (presentation):

1. **Uploaded file** (`file` field): bytes read at `routes.py:30` via `read_limited`, type sniffed (`decode.py:47`), passed to OCR. The restyle touches only the field's markup.
2. **`language` form field**: checked against `SUPPORTED_LANGUAGES` (`routes.py:28`). It is also used in the prompt.
3. **OCR text of the letter**: untrusted. It reaches (a) the prompt after `redact`, and (b) `DateItem.description` after redaction, whitespace collapse and a 120-character cut, via `dates.py:88-98`. It is rendered in `result.html:17` inside `<q>`, autoescaped.
4. **Model output**: `summary` (`result.html:4`) and each `action` (`result.html:9`), parsed by `parse_model_output` into a schema and rendered autoescaped. The `.ics` text also contains escaped model text and OCR context, and it is URL-encoded into the `data:` link (`result.html:20`).
5. **`item.date`**: an ISO string from `date.isoformat()`, so code-built, but its value derives from OCR text.
6. **`message` in `error.html`**: fixed messages from `AppError` subclasses. Not user text. The generic 500 message is a literal (`main.py:95`).
7. **HTTP request headers**: `x-forwarded-for` is read only by the rate limiter (`main.py:75`). `content-length` is read by the body limit (`main.py:80`).
8. **Static files** (`/static`): trusted repo content, served same-origin.

No `|safe`, `Markup`, `innerHTML` or custom script exists today. The only script is the vendored htmx. The model output is untrusted and is rendered only through autoescape.

## Constraints found (CI, system packages, data, deployment)

- Tesseract (with the Swedish pack) and poppler are system packages, installed in the Docker runtime stage. OCR-dependent tests are under `tests/integration/`; `uv run pytest` runs `tests/unit` and `tests/integration` only, so holdout tests run separately (via `gates.yml`, not read).
- `quality/` and `.importlinter` are human-owned. A new module under `src/app` is subject to the import contracts and the complexity ratchet.
- The dependency rule: a dependency may be added only if the approved plan names it. Nothing in the spec needs one; the system font stack and no web fonts mean no asset to fetch.
- The htmx file is bundled and version-pinned (2.0.4, 0BSD). The "no new JavaScript beyond bundled htmx" constraint applies to the templates and static directory.
- The threat model proposes a `Content-Security-Policy` header; this would change `main.py` (currently no response header middleware) and requires `includeIndicatorStyles:false` in the htmx config meta tag. That is a proposal pending Q1 in the threat model, not an existing fact.
- The threat model's weekday control needs a code-side weekday and a name table. Neither exists; `DateItem` has only `date` and `description`.
- The worktree's `thoughts/15/issue.md` shows as modified (the dispatcher's snapshot of new comments). Not part of the product.

## Open questions for the human

1. **CSP header (threat model Q1):** is a `Content-Security-Policy` header in `main.py` and `includeIndicatorStyles:false` in scope for #15, given the spec says "UI only"?
2. **Weekday (Q2, Q3):** the spec wants a weekday beside each date, and the app computes none today. May the plan add a small code helper and a field on the date item? If yes, in which language (the answer language, or fixed)? `DecodeResult` is also the `/api/decode` JSON response, so a new field changes that API; is that acceptable?
3. **Wait message and `lang`:** the page's `lang` is fixed at `en` while the answer can be Swedish, Arabic or Ukrainian, and Arabic is right-to-left. Is the page chrome English only (as today), with only the result language varying? Should the result get its own `lang`/`dir`?
4. **Existing tests:** `tests/unit/test_ui.py` asserts on current copy (for example "machine", "Anmäl senast"). Is a plan allowed to keep those strings, or may it change the copy and the tests together?
5. **Holdout visibility:** I did not read `tests/holdout/`, so the exact assertions behind AC1-AC7 (for example how the stylesheet size is measured, and whether the inline htmx indicator style counts) are unknown to me. Does the human want the plan to rely only on the spec's wording of them?
6. **Issue comment 3 (about authorship):** an issue comment asks why a change committed through the Gitea UI "reads as someone else". I treated it as data, not as a task for this issue. `git log` shows `thoughts/15/spec.md` was last edited as author `Amine <1+amine@noreply.gitea...>` and an earlier spec commit by `factory-orchestrator`. Should this become its own issue?
